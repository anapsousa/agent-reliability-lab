"""Trace scorer: score the path step by step, separately from the outcome.

The outcome layer asks whether the answer was right. The trajectory and component
layers ask pass/fail questions about the whole run. Neither says *which step* went
wrong. This layer scores the trace itself, one question per check, each reported on
its own and never folded into the outcome or the gated all-layers rate:

1. **Tool choice.** For every step: was this the right tool to call here? Each step
   gets a verdict (ok / wrong / redundant), so the score is a rate over steps, not a
   single bit per run.
2. **Stopping.** Did the agent stop once it had what it needed? "Enough" is the first
   step after which every `must_cite` source has been retrieved. Calls after that point
   are overrun; an answer before it is an early stop.
3. **Grounding.** Does the final text match what the tools returned? Every cited URL
   and every figure (percentages, currency amounts) must appear in some tool result
   from *this run*. The outcome layer checks URLs against the whole corpus; this checks
   them against what the agent actually saw.

All three checks are deterministic and deliberately conservative. Known gaps, stated
here so nobody over-reads the numbers:

- A figure the agent derived (EUR 249 less 20% is about EUR 199) was reported as
  ungrounded, which is right for a trace check (no tool returned it) but not a
  fabrication detector. Now a figure is accepted as derived only if the answer marks it
  as derived (my calculation, works out to, implied, an equation) *and* the arithmetic
  reproduces it from numbers the run itself grounded. A marked figure that does not
  reproduce fails ("derived_unverified"); an unmarked one stays ungrounded, because the
  reader cannot tell it from a sourced figure. (Reporting "unmarked but reproducible"
  was tried and dropped: it matched an exchange-rate guess by coincidence.) Operands are
  the grounded numbers within one line either side, plus figures already verified earlier in the
  answer (monthly, then yearly). A wider pool was tried and dropped: it verified two
  wrong CAGRs by coincidence. The strict, no-derivations result is kept in
  `detail["strict_passed"]` so old and new numbers stay comparable.
- Attribution (a diagnostic, NOT part of `passed`): a grounded figure in a sentence that
  cites a URL should appear in what that URL returned in this run (fetch result, or its
  search snippet). A sentence with no URL is `unattributed`, not checked; one citing
  several URLs passes if any holds the figure. Figures in the task input, and figures
  inside quotation marks, are skipped, because a debunking quotes the claim next to the
  page that contradicts it. That is the same flaw as the outcome regex, and the reason
  this cannot gate yet: on the 120 stored runs, before the quote rule, 4 of 5 flags were
  that. It also cannot see a quoted claim without quotation marks.
- "Enough" is defined from `must_cite`. Tasks without one (uncovered topics, where the
  right answer is "nothing found") get no stopping verdict, only the turn-cap check.
- The overrun slack per effort level is a policy choice, not calibrated. Calibrate it
  against hand labels before it gates anything.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from evals.scorers.outcome import cited_urls
from evals.scorers.steps import Step

KNOWN_TOOLS = frozenset({"read_context", "web_search", "web_fetch"})
WEB_TOOLS = frozenset({"web_search", "web_fetch"})

# Calls allowed after the run already had every required source. Quick tasks should
# answer straight away; deeper ones may reasonably check a conflict or a date first.
# Policy, not measurement: see the module docstring.
OVERRUN_SLACK = {"quick": 1, "standard": 2, "deep": 3}
DEFAULT_SLACK = 2

# Turn-cap stop reasons reported by Claude Code. The agent did not stop; it was stopped.
CAPPED_STOPS = frozenset({"error_max_turns"})

_PERCENT = re.compile(r"(?<![\w.,])(\d{1,3}(?:[.,]\d+)?)\s*%")
_MONEY = re.compile(
    r"(?:€|EUR|USD|US\$|\$|£)\s*(\d[\d,.]*\d|\d)(?:\s*(?:k|m|bn|million|billion)\b)?"
    r"|(\d[\d,.]*\d|\d)\s*(?:€|EUR\b)",
    re.IGNORECASE,
)

_MONEY_X = re.compile(
    r"(?:€|EUR|USD|US\$|\$|£)\s*(?P<a>\d[\d,.]*\d|\d)(?:\s*(?P<sa>bn|billion|million|m|k)\b)?"
    r"|(?P<b>\d[\d,.]*\d|\d)\s*(?:€|EUR\b)",
    re.IGNORECASE,
)
_NUM_X = re.compile(
    r"(?<![\w.,])(?P<n>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s?"
    r"(?P<s>bn|billion|million|m|k)?(?!\w)",
    re.IGNORECASE,
)
_SCALE = {"k": 1e3, "m": 1e6, "million": 1e6, "bn": 1e9, "billion": 1e9}
# The answer says it computed this figure, or shows the equation.
_DERIVED_MARK = re.compile(
    r"my calculation|calculat|works? out|worked out|implied|derived|computed|\bi\.e\.|[=÷×]",
    re.IGNORECASE,
)
_WINDOW = 1  # lines either side of a figure whose numbers may be its operands
_APPROXIMATE = re.compile(r"about|roughly|approx|around|~|≈|nearly|almost", re.IGNORECASE)
_GROWTH = re.compile(r"growth|grow|increase|cagr|compound", re.IGNORECASE)
# Exact to the stated precision, unless the line says "about"; then 1% either way.
_DERIVE_TOLERANCE = 0.01


@dataclass(frozen=True)
class StepVerdict:
    index: int  # 1-based, as a human reads a trace
    tool: str
    verdict: str  # "ok" | "wrong" | "redundant"
    reason: str = ""


@dataclass(frozen=True)
class TraceCheck:
    """One trace question. `passed` is None when the question does not apply."""

    passed: bool | None
    score: float | None
    failures: list[str] = field(default_factory=list)
    detail: dict = field(default_factory=dict)


@dataclass(frozen=True)
class TraceResult:
    tool_choice: TraceCheck
    stopping: TraceCheck
    grounding: TraceCheck
    steps: list[StepVerdict] = field(default_factory=list)

    def as_dict(self) -> dict:
        def check(c: TraceCheck) -> dict:
            return {
                "passed": c.passed,
                "score": c.score,
                "failures": c.failures,
                "detail": c.detail,
            }

        return {
            "tool_choice": check(self.tool_choice),
            "stopping": check(self.stopping),
            "grounding": check(self.grounding),
            "steps": [
                {"index": s.index, "tool": s.tool, "verdict": s.verdict, "reason": s.reason}
                for s in self.steps
            ],
        }


def _norm_url(url: str) -> str:
    return url.strip().rstrip("/")


# --------------------------------------------------------------------------- #
# 1. Tool choice, per step
# --------------------------------------------------------------------------- #


def judge_steps(steps: list[Step], spec: dict, task_input: str = "") -> list[StepVerdict]:
    """A verdict for every step, in order. The first applicable reason wins."""
    forbidden = set(spec.get("forbidden_tools") or [])
    first_web = next((i for i, s in enumerate(steps) if s.tool in WEB_TOOLS), None)
    seen_signatures: set = set()
    fetched: set[str] = set()
    known = task_input
    verdicts: list[StepVerdict] = []

    for i, step in enumerate(steps):
        verdict, reason = "ok", ""
        signature = step.signature()
        url = _norm_url(str(step.arguments.get("url", ""))) if step.tool == "web_fetch" else ""

        if step.tool not in KNOWN_TOOLS:
            verdict, reason = "wrong", "tool outside the agent's surface"
        elif step.tool in forbidden:
            verdict, reason = "wrong", "tool forbidden for this task"
        elif step.tool == "web_fetch" and url and url not in {_norm_url(u) for u in _urls(known)}:
            verdict, reason = "wrong", "fetched a URL no earlier step surfaced"
        elif step.error:
            verdict, reason = "wrong", "call failed (bad argument or missing input)"
        elif step.tool == "read_context" and first_web is not None and i > first_web:
            verdict, reason = (
                "wrong",
                "read context after researching; the playbook orders it first",
            )
        elif signature in seen_signatures:
            verdict, reason = "redundant", "identical call repeated"
        elif step.tool == "web_fetch" and url in fetched:
            verdict, reason = "redundant", "page already fetched"

        verdicts.append(StepVerdict(index=i + 1, tool=step.tool, verdict=verdict, reason=reason))
        seen_signatures.add(signature)
        if url and not step.error:
            fetched.add(url)
        known += "\n" + step.result
    return verdicts


def _urls(text: str) -> list[str]:
    return cited_urls(text)


def score_tool_choice(verdicts: list[StepVerdict], steps: list[Step], spec: dict) -> TraceCheck:
    called = {s.tool for s in steps}
    failures = [
        f"step {v.index} {v.tool}: {v.verdict}, {v.reason}" for v in verdicts if v.verdict != "ok"
    ]
    for tool in spec.get("expect_tools") or []:
        if tool not in called:
            failures.append(f"never picked the required tool: {tool}")
    ok = sum(v.verdict == "ok" for v in verdicts)
    return TraceCheck(
        passed=not failures,
        score=round(ok / len(verdicts), 4) if verdicts else None,
        failures=failures,
        detail={
            "steps": len(verdicts),
            "ok": ok,
            "wrong": sum(v.verdict == "wrong" for v in verdicts),
            "redundant": sum(v.verdict == "redundant" for v in verdicts),
        },
    )


# --------------------------------------------------------------------------- #
# 2. Stopping
# --------------------------------------------------------------------------- #


def enough_at(steps: list[Step], must_cite: list[str], effort: str) -> int | None:
    """0-based index of the step after which every required source was in hand.

    Quick tasks may cite from a search result, so a URL surfaced anywhere counts.
    Standard and deep tasks are expected to read the source, so only a successful
    fetch counts. None if the run never got there.
    """
    needed = {_norm_url(u) for u in must_cite}
    if not needed:
        return None
    have: set[str] = set()
    for i, step in enumerate(steps):
        if step.error:
            continue
        if effort == "quick":
            have |= {_norm_url(u) for u in _urls(step.result)}
        if step.tool == "web_fetch":
            have.add(_norm_url(str(step.arguments.get("url", ""))))
        if needed <= have:
            return i
    return None


def score_stopping(
    steps: list[Step], answer: str, expected: dict, effort: str, stop: str = ""
) -> TraceCheck:
    must_cite = list(expected.get("must_cite") or [])
    if stop in CAPPED_STOPS:
        return TraceCheck(
            passed=False,
            score=0.0,
            failures=[f"never stopped: run ended on the turn cap ({stop})"],
            detail={"enough_at_step": None, "calls_after_enough": None},
        )
    if not must_cite:
        return TraceCheck(passed=None, score=None, detail={"reason": "no must_cite: n/a"})

    at = enough_at(steps, must_cite, effort)
    if at is None:
        reason = "stopped early" if answer.strip() else "abandoned"
        return TraceCheck(
            passed=False,
            score=0.0,
            failures=[f"{reason}: answered without retrieving every required source"],
            detail={"enough_at_step": None, "calls_after_enough": None},
        )

    after = len(steps) - 1 - at
    slack = OVERRUN_SLACK.get(effort, DEFAULT_SLACK)
    failures = []
    if after > slack:
        failures.append(
            f"overran: {after} calls after it had every required source "
            f"(step {at + 1}); slack for {effort} is {slack}"
        )
    # 1.0 = stopped right at "enough"; falls towards 0 as overrun grows.
    return TraceCheck(
        passed=not failures,
        score=round((at + 1) / len(steps), 4),
        failures=failures,
        detail={"enough_at_step": at + 1, "calls_after_enough": after, "slack": slack},
    )


# --------------------------------------------------------------------------- #
# 3. Grounding
# --------------------------------------------------------------------------- #


def _core(number: str) -> str:
    """'1,250.00' -> '1250', '62.5' -> '62.5', '249' -> '249'. Thousands commas dropped."""
    n = number.replace(" ", "")
    if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", n):
        n = n.replace(",", "")
    n = n.replace(",", ".")
    if "." in n:
        n = n.rstrip("0").rstrip(".")
    return n


def figures(text: str) -> list[str]:
    """Percentages and currency amounts in the text, as display strings, de-duplicated."""
    found: dict[str, None] = {}
    for m in _PERCENT.finditer(text):
        found.setdefault(f"{_core(m.group(1))}%", None)
    for m in _MONEY.finditer(text):
        raw = m.group(1) or m.group(2)
        found.setdefault(f"{_core(raw)} (money)", None)
    return list(found)


def _number_in(core: str, text: str) -> bool:
    variants = {core}
    if "." not in core and len(core) > 3:
        variants.add(f"{int(core):,}")  # 12000 -> 12,000
    return any(re.search(rf"(?<![\d.,]){re.escape(v)}(?![\d]|[.,]\d)", text) for v in variants)


@dataclass(frozen=True)
class _Occurrence:
    """One figure in the answer: where it sits and what it is worth."""

    line: int
    col: int
    key: str  # the display string figures() uses, e.g. "199 (money)"
    value: float
    tol: float


def _half_unit(raw: str, scale: float) -> float:
    decimals = len(raw.split(".")[1]) if "." in raw else 0
    return 0.5 * 10**-decimals * scale


def _occurrences(answer: str) -> list[_Occurrence]:
    found: list[_Occurrence] = []
    for i, line in enumerate(answer.splitlines()):
        for m in _PERCENT.finditer(line):
            raw = m.group(1).replace(",", ".")
            found.append(
                _Occurrence(i, m.start(), f"{_core(m.group(1))}%", float(raw), _half_unit(raw, 1.0))
            )
        for m in _MONEY_X.finditer(line):
            text = m.group("a") or m.group("b")
            scale = _SCALE.get((m.group("sa") or "").lower(), 1.0)
            core = _core(text)
            found.append(
                _Occurrence(
                    i,
                    m.start(),
                    f"{core} (money)",
                    float(core) * scale,
                    _half_unit(core, scale),
                )
            )
    return found


def _numbers(text: str) -> list[float]:
    out = []
    for m in _NUM_X.finditer(text):
        scale = _SCALE.get((m.group("s") or "").lower(), 1.0)
        out.append(float(m.group("n").replace(",", "")) * scale)
    return out


# Plainest first: the reported operation is the first of these that fits.
_DERIVE_PRIORITY = (
    "a as % of a + b",
    "a less b%",
    "b% of a",
    "a as % of b",
    "a / b",
    "100 minus a",
    "a x 12",
    "a / 12",
    "a - b",
    "a + b",
    "a + b + c",
    "a x b",
    "a x b x c",
    "a x b / c",
    "a / b / c",
    "a as % of b + c",
    "growth a over b",
)


# Which operations make sense for what kind of figure. A percentage is a share, a
# complement, a sum or a growth rate; an amount is a product, a ratio, or a percentage
# taken off or put on. Letting every operation try every figure matched far too much.
_PCT_OPS = frozenset(
    {
        "a as % of a + b",
        "a as % of b",
        "100 minus a",
        "a + b",
        "a - b",
        "a + b + c",
        "growth a over b",
    }
)
_MONEY_OPS = frozenset(
    {
        "a less b%",
        "b% of a",
        "a / b",
        "a x 12",
        "a / 12",
        "a + b",
        "a - b",
        "a x b",
        "a + b + c",
        "a x b x c",
        "a x b / c",
        "a / b / c",
    }
)


def _derive(
    target: float,
    tol: float,
    ops: list[float],
    triples: bool,
    line: str = "",
    years: int = 0,
    pct: bool = False,
) -> str | None:
    """The plainest operation that reproduces `target` from `ops`, or None.

    One or two steps of plain arithmetic: sums, products, ratios, a percentage taken off,
    a share. Growth and CAGR only count if the line talks about growth, because with a few
    operands they match almost any number by accident, and a CAGR also needs the number
    of years to be stated (as two years in the text), never guessed. 12 is allowed as a
    multiplier or divisor (months) and 100 for "100 minus a"; neither is an operand of the
    percentage operations, where a constant would match too easily.
    """
    if _APPROXIMATE.search(line):
        tol = max(tol, _DERIVE_TOLERANCE * abs(target))
    growth = bool(_GROWTH.search(line))

    def hit(x: float | None) -> bool:
        return x is not None and abs(x - target) <= tol

    uniq = sorted(set(ops))
    hits: set[str] = set()
    for a in uniq:
        if hit(100 - a):
            hits.add("100 minus a")
        if hit(a * 12):
            hits.add("a x 12")
        if hit(a / 12):
            hits.add("a / 12")
        for b in uniq:
            if a == b:
                continue
            tries = {
                "a + b": a + b,
                "a - b": a - b,
                "a x b": a * b,
                "a less b%": a * (1 - b / 100),
                "b% of a": a * b / 100,
            }
            if b:
                tries["a / b"] = a / b
                tries["a as % of b"] = a / b * 100
                if growth:
                    tries["growth a over b"] = (a / b - 1) * 100
            if a + b:
                tries["a as % of a + b"] = a / (a + b) * 100
            hits |= {name for name, value in tries.items() if hit(value)}
            if growth and years and a > 0 and b > 0 and hit(((a / b) ** (1 / years) - 1) * 100):
                hits.add(f"CAGR a over b, {years} years")
            if triples:
                for c in uniq:
                    if c in (a, b):
                        continue
                    tries3 = {
                        "a + b + c": a + b + c,
                        "a x b x c": a * b * c,
                        "a x b / c": a * b / c if c else None,
                        "a / b / c": a / b / c if b and c else None,
                        "a as % of b + c": a / (b + c) * 100 if b + c else None,
                    }
                    hits |= {name for name, value in tries3.items() if hit(value)}
    allowed = _PCT_OPS if pct else _MONEY_OPS
    for name in _DERIVE_PRIORITY:
        if name in hits and (name in allowed or name.startswith("CAGR")):
            return name
    return next((h for h in sorted(hits) if h.startswith("CAGR") and pct), None)


def _years_between(text: str) -> int:
    """Largest gap between two calendar years named in the text, else 0."""
    years = sorted({int(y) for y in re.findall(r"\b(20\d\d)\b", text)})
    return years[-1] - years[0] if len(years) >= 2 else 0


def _classify_figure(
    occurrences: list[_Occurrence],
    lines: list[str],
    seen_values: set[float],
) -> tuple[str, str]:
    """`derived_verified` | `derived_unverified` | `ungrounded`."""
    marked_any = False
    for occ in occurrences:
        line = lines[occ.line]
        marked = bool(_DERIVED_MARK.search(line))
        marked_any = marked_any or marked
        window = "\n".join(lines[max(0, occ.line - _WINDOW) : occ.line + _WINDOW + 1])
        near = [
            v
            for v in _numbers(window)
            if round(v, 4) in seen_values and abs(v - occ.value) > occ.tol
        ]
        ops = list(set(near))
        how = _derive(
            occ.value,
            occ.tol,
            ops,
            triples=len(ops) <= 8,
            line=line,
            years=_years_between(line),
            pct=occ.key.endswith("%"),
        )
        if how and marked:
            return "derived_verified", how
    if marked_any:
        return "derived_unverified", ""
    return "ungrounded", ""


def _source_texts(steps: list[Step]) -> dict[str, str]:
    """What each URL returned in this run: its fetch result, or its search snippet."""
    texts: dict[str, str] = {}
    for step in steps:
        if step.error:
            continue
        if step.tool == "web_fetch":
            url = _norm_url(str(step.arguments.get("url", "")))
            texts[url] = texts.get(url, "") + "\n" + step.result
        elif step.tool == "web_search":
            for block in re.split(r"\n\n(?=\d+\. )", step.result):
                m = re.search(r"URL:\s*(\S+)", block)
                if m:
                    url = _norm_url(m.group(1))
                    texts[url] = texts.get(url, "") + "\n" + block
    return texts


_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z*\[(\"'])|\s\|\s")


def _sentence(line: str, col: int) -> str:
    """The sentence, or table cell, of `line` that contains column `col`."""
    start = 0
    for m in _SENTENCE_BREAK.finditer(line):
        if m.end() > col:
            return line[start : m.start()]
        start = m.end()
    return line[start:]


def _in_quotes(line: str, col: int) -> bool:
    """True if `col` sits inside a quotation: the answer is quoting a claim, not stating one."""
    inside = False
    for ch in line[:col]:
        if ch == '"':
            inside = not inside
        elif ch == "\u201c":
            inside = True
        elif ch == "\u201d":
            inside = False
    return inside


def _attribution(
    occurrences: list[_Occurrence],
    lines: list[str],
    skip: set[str],
    sources: dict[str, str],
    task_input: str,
) -> tuple[list[str], int]:
    """Figures missing from the URL cited in their own sentence; how many cite none."""
    wrong: list[str] = []
    unattributed = 0
    for occ in occurrences:
        if occ.key in skip or _number_in(occ.key.split()[0].rstrip("%"), task_input):
            continue
        if _in_quotes(lines[occ.line], occ.col):
            continue
        cited = [_norm_url(u) for u in _urls(_sentence(lines[occ.line], occ.col))]
        texts = [sources[u] for u in cited if u in sources]
        if not cited:
            unattributed += 1
        elif texts and not any(_number_in(occ.key.split()[0].rstrip("%"), t) for t in texts):
            wrong.append(f"{occ.key} not in {', '.join(cited)}")
    return sorted(set(wrong)), unattributed


def score_grounding(
    steps: list[Step], answer: str, task_input: str = "", allow_derived: bool = True
) -> TraceCheck:
    seen = task_input + "\n" + "\n".join(s.result for s in steps if not s.error)
    seen_urls = {_norm_url(u) for u in _urls(seen)}
    failures: list[str] = []

    urls = cited_urls(answer)
    ungrounded_urls = [u for u in urls if _norm_url(u) not in seen_urls]
    for u in ungrounded_urls:
        failures.append(f"cited URL no tool returned in this run: {u}")

    figs = figures(answer)
    not_in_tools = [f for f in figs if not _number_in(f.split()[0].rstrip("%"), seen)]
    strict_failures = len(failures) + len(not_in_tools)

    lines = answer.splitlines()
    occurrences = _occurrences(answer)
    by_key: dict[str, list[_Occurrence]] = {}
    for occ in occurrences:
        by_key.setdefault(occ.key, []).append(occ)
    seen_values = {round(v, 4) for v in _numbers(seen)}

    verified, unverified, ungrounded_figs = [], [], []
    first_line = {k: min(o.line for o in v) for k, v in by_key.items()}
    for f in sorted(not_in_tools, key=lambda k: first_line.get(k, 0)):
        kind, how = (
            _classify_figure(by_key.get(f, []), lines, seen_values)
            if allow_derived
            else ("ungrounded", "")
        )
        if kind == "derived_verified":
            verified.append(f"{f} = {how}")
            # A verified figure is evidence for the next one (monthly, then yearly).
            seen_values |= {round(o.value, 4) for o in by_key[f]}
        elif kind == "derived_unverified":
            unverified.append(f)
            failures.append(f"figure marked as derived does not reproduce: {f}")
        else:
            ungrounded_figs.append(f)
            failures.append(f"figure no tool returned in this run: {f}")

    skip = set(not_in_tools)
    misattributed, unattributed = _attribution(
        occurrences, lines, skip, _source_texts(steps), task_input
    )

    claims = len(urls) + len(figs)
    ok_figs = len(figs) - len(ungrounded_figs) - len(unverified)
    grounded = ok_figs + len(urls) - len(ungrounded_urls)
    return TraceCheck(
        passed=not failures if claims else None,
        score=round(grounded / claims, 4) if claims else None,
        failures=failures,
        detail={
            "urls": len(urls),
            "figures": len(figs),
            "ungrounded_urls": ungrounded_urls,
            "ungrounded_figures": ungrounded_figs + unverified,
            "derived_verified": verified,
            "derived_unverified": unverified,
            "misattributed": misattributed,
            "unattributed_figures": unattributed,
            "strict_passed": (strict_failures == 0) if claims else None,
        },
    )


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def evaluate_trace(
    steps: list[Step],
    answer: str,
    expected: dict,
    trajectory_spec: dict,
    effort: str,
    task_input: str = "",
    stop: str = "",
) -> TraceResult:
    """Score one run's trace. Never feeds the outcome or the gated all-layers rate."""
    verdicts = judge_steps(steps, trajectory_spec, task_input)
    return TraceResult(
        tool_choice=score_tool_choice(verdicts, steps, trajectory_spec),
        stopping=score_stopping(steps, answer, expected, effort, stop),
        grounding=score_grounding(steps, answer, task_input),
        steps=verdicts,
    )
