"""Outcome scorer — did the agent produce the right answer.

Deterministic checks only. Whether a figure was *asserted* or merely quoted in
order to refute it is a question about meaning, not about substrings, and it
belongs to the judge layer. This module fails loudly in the ambiguous cases and
lets a task opt out explicitly, which is honest; guessing would not be.

The one exception is opt-in: pass `stance` and each unsupported-claim regex hit is
handed to a calibrated judge (evals/judges/stance.py) with the paragraph around it. The
regex keeps total recall, and the judge decides only what the mention does. Without
`stance` the check behaves exactly as before, so historical numbers do not move.

The same flaw sat in `must_not_cite`: a forbidden URL anywhere in the answer failed it,
including "Excluded: <url> (AI-generated, unsourced)". Pass `source_use` (for example
`forbidden_source_stance` below) and a forbidden URL counts as cited only when some
mention of it is support. Without it the check is the lexical one, for the same reason.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

# Deliberately excludes ) ] > " ' ` , so markdown links and prose punctuation
# do not end up inside the URL.
_URL = re.compile(r"https?://[^\s<>()\[\]\"'`,]+")

# Trailing sentence punctuation that is never part of a URL in practice.
_TRAILING = ".,;:!?"


# (claim, passage) -> "ASSERTED" | "REFUTED" | "NEUTRAL"
StanceFn = Callable[[str, str], str]

# (answer, forbidden url) -> "ASSERTED" | "REFUTED" | ...; only REFUTED and UNRELATED pass,
# the same pass set as the stance cascade.
SourceUseFn = Callable[[str, str], str]
_PASSING = ("REFUTED", "UNRELATED")


def passage_around(answer: str, match: re.Match[str], cap: int = 900) -> str:
    """The paragraph holding a match: what the stance judge sees, and was calibrated on."""
    start = max(0, answer.rfind("\n\n", 0, match.start()))
    end = answer.find("\n\n", match.end())
    end = len(answer) if end < 0 else end
    paragraph = answer[start:end].strip()
    if len(paragraph) > cap:
        paragraph = answer[max(0, match.start() - 400) : match.end() + 400]
    return paragraph


@dataclass(frozen=True)
class OutcomeResult:
    """Binary verdict plus every reason it failed, not just the first."""

    passed: bool
    failures: list[str] = field(default_factory=list)
    checks_run: int = 0


def cited_urls(answer: str) -> list[str]:
    """Every URL the answer refers to, de-duplicated, order preserved."""
    seen: dict[str, None] = {}
    for raw in _URL.findall(answer):
        seen.setdefault(raw.rstrip(_TRAILING), None)
    return list(seen)


def _compile(pattern: str, where: str) -> re.Pattern[str]:
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        raise ValueError(f"invalid regex in {where}: {pattern!r} — {exc}") from exc


# --------------------------------------------------------------------------- #
# Forbidden sources: cited, or named in order to reject?
# --------------------------------------------------------------------------- #
#
# A deterministic heuristic, not a judge. Every occurrence of the forbidden URL is read in
# its own line (a list item, a table row, a paragraph line) together with the label that
# governs that line: the parent bullet of a nested item, or else the nearest heading or
# "Label:" line above the list the line sits in.
#
#   1. A support cue in the line or label, not negated in its clause ("according to",
#      "used", "cited for", "relied on", "based on")  -> ASSERTED
#   2. Otherwise a rejection cue, not negated in its clause ("excluded", "left out",
#      "rejected", "do not use", "not cited", "unreliable", "only to explain")  -> REFUTED
#   3. Otherwise, including a bare URL, an attribution ("a listicle claims X (url)") and a
#      description with no verdict ("AI-generated, affiliate", "[UNVERIFIED]")  -> ASSERTED
#
# The URL counts as cited if any one occurrence is ASSERTED. Unknown means cited: the
# heuristic only passes a mention that carries an explicit rejection. It errs lenient only
# when a rejection cue on the line is about something else, or sits next to real support
# that carries no support cue (case 1 guards the common form of that).
#
# Bar, written 2026-10-20 before the stored runs were re-scored with it: over every
# mention of the forbidden URL in the stored answers (23 Sep baseline and 12 Oct repeats),
# the heuristic may pass NO mention that a reader marks as support, a bare listing, or a
# description with no verdict. One such mention and the heuristic is not used. Recall on
# rejections is reported, not barred: a missed rejection is a false fail, the old
# behaviour. The cue lists were written after reading those mentions, so the bar is a
# consistency check on them, not a validation (evals/tests/test_source_rescore.py).

_NEG = re.compile(r"\b(?:not|never|cannot)\b|n't\b", re.IGNORECASE)
# Clause boundaries for negation scope: "Excluded, not cited for any claim" negates
# "cited for" but not "Excluded".
_CLAUSE = re.compile(r"[.;:!?()\[\]\u2014\u2013,]")

_SUPPORT = re.compile(
    r"\baccording\s+to\b"
    r"|\bas\s+reported\s+by\b"
    r"|\bbased\s+on\b"
    r"|\bused\b(?!\s+only\b)"
    r"|\bcited\s+(?:for|as)\b"
    r"|\brel(?:y|ied|ying)\s+(?:on|upon)\b",
    re.IGNORECASE,
)

_REJECT = re.compile(
    r"\bexclu(?:de|ded|ding|sion)\b"
    r"|\bleft\s+out\b"
    r"|\breject(?:ed|ing)?\b"
    r"|\bdiscard(?:ed)?\b"
    r"|\bdisregard(?:ed)?\b"
    r"|\bignor(?:e|ed)\b"
    r"|\bavoid\b"
    r"|\bun(?:reliable|usable|citable|trustworthy)\b"
    r"|\bnot\s+(?:be\s+)?(?:used|usable|citable|cited|citing|credible|reliable|trusted|using"
    r"|relying|relied\s+(?:on|upon)|for\s+citation|as\s+evidence|a\s+(?:reliable\s+|credible\s+)?source"
    r"|as\s+a\s+(?:fact\s+)?source)\b"
    r"|\b(?:do|does|did|would|will|should|could|can|have|has|am|is)\s+not\s+"
    r"(?:use|used|cite|cited|citing|rely|relied|relying|trust|be\s+trusted)\b"
    r"|\b(?:don't|doesn't|didn't|wouldn't|won't|shouldn't|couldn't|can't|cannot|haven't"
    r"|hasn't|isn't|i'm\s+not|we're\s+not)\s+(?:a\s+)?(?:use|used|cite|cited|citing|rely|relied"
    r"|relying|trust|be\s+trusted|reliable|credible|citable)\b"
    r"|\blow[\s-](?:credibility|reliability|trust)\b"
    r"|\bonly\s+to\s+(?:flag|explain|show|trace|reject|evaluate)\b"
    r"|\bused\s+only\s+to\b",
    re.IGNORECASE,
)

_HEADING = re.compile(r"^#{1,6}\s")
_LIST_ITEM = re.compile(r"^(?:[-*+]|\d+[.)])\s")
_EMPHASIS = re.compile(r"[*`]+")


@dataclass(frozen=True)
class Mention:
    """One occurrence of a forbidden URL, and what the heuristic made of it."""

    line_no: int
    line: str
    label: str
    stance: str  # "ASSERTED" | "REFUTED"
    cue: str  # the matched cue, "" for a mention with none


def _is_label(stripped: str) -> bool:
    return bool(
        _HEADING.match(stripped)
        or stripped.endswith((":", ":**", ":*"))
        or re.fullmatch(r"\*\*[^*]+\*\*:?", stripped)
    )


def _governing_label(lines: list[str], i: int) -> str:
    """Parent bullet of a nested item, or the heading / label line above its list."""
    indent = len(lines[i]) - len(lines[i].lstrip())
    for j in range(i - 1, -1, -1):
        raw = lines[j]
        stripped = raw.strip()
        if not stripped:
            continue
        own = len(raw) - len(raw.lstrip())
        if _LIST_ITEM.match(stripped) or stripped.startswith("|"):
            if own < indent and _LIST_ITEM.match(stripped):
                return stripped  # the parent bullet
            continue  # a sibling item or table row: keep walking up the list
        return stripped if _is_label(stripped) else ""
    return ""


def _unnegated(pattern: re.Pattern[str], text: str, allow_negated_cue: bool) -> str:
    """The first cue in `text` whose clause carries no negation before it."""
    for m in pattern.finditer(text):
        cue = m.group(0)
        if allow_negated_cue and _NEG.search(cue):
            return cue  # the cue is itself a negation: "not cited", "don't use"
        bounds = [b.end() for b in _CLAUSE.finditer(text, 0, m.start())]
        clause = text[bounds[-1] if bounds else 0 : m.start()]
        if not _NEG.search(clause):
            return cue
    return ""


def forbidden_source_mentions(answer: str, url: str) -> list[Mention]:
    """Every occurrence of `url` in the answer, each with its stance and the cue behind it."""
    lines = answer.replace("\u2019", "'").split("\n")
    out = []
    for i, line in enumerate(lines):
        if not any(raw.rstrip(_TRAILING) == url for raw in _URL.findall(line)):
            continue
        label = _governing_label(lines, i)
        # Emphasis markers split phrases ("I am **not** citing"); cues are read without them.
        parts = [_EMPHASIS.sub("", p) for p in (line, label) if p]
        cue = next((c for c in (_unnegated(_SUPPORT, p, False) for p in parts) if c), "")
        if cue:
            stance = "ASSERTED"
        else:
            cue = next((c for c in (_unnegated(_REJECT, p, True) for p in parts) if c), "")
            stance = "REFUTED" if cue else "ASSERTED"
        out.append(Mention(i, line.strip(), label, stance, cue))
    return out


def forbidden_source_stance(answer: str, url: str) -> str:
    """ASSERTED if any mention of `url` is support or carries no verdict, else REFUTED."""
    mentions = forbidden_source_mentions(answer, url)
    if not mentions or any(m.stance == "ASSERTED" for m in mentions):
        return "ASSERTED"
    return "REFUTED"


def evaluate_outcome(
    answer: str,
    expected: dict,
    ground_truth: dict,
    stance: StanceFn | None = None,
    source_use: SourceUseFn | None = None,
) -> OutcomeResult:
    """Score one answer against one task's expectations.

    Raises ValueError if the task declares a regex that does not compile — a typo
    in a golden task must not quietly become a green run.
    """
    failures: list[str] = []
    checks = 0
    urls = cited_urls(answer)

    for url in expected.get("must_cite", []):
        checks += 1
        if url not in urls:
            failures.append(f"missing required citation: {url}")

    for url in expected.get("must_not_cite", []):
        checks += 1
        if url in urls and (source_use is None or source_use(answer, url) not in _PASSING):
            failures.append(f"cited forbidden source: {url}")

    for item in expected.get("must_mention", []):
        checks += 1
        if not _compile(item["pattern"], "must_mention").search(answer):
            failures.append(
                f"did not mention {item['pattern']!r} ({item.get('why', 'no reason given')})"
            )

    for item in expected.get("must_not_mention", []):
        checks += 1
        if _compile(item["pattern"], "must_not_mention").search(answer):
            failures.append(
                f"mentioned forbidden {item['pattern']!r} ({item.get('why', 'no reason given')})"
            )

    for section in expected.get("format_sections", []):
        checks += 1
        heading = re.compile(rf"^#{{1,6}}\s*{re.escape(section)}\s*$", re.IGNORECASE | re.MULTILINE)
        if not heading.search(answer):
            failures.append(f"missing section: {section}")

    # --- Always-on: the agent's own non-negotiable rules, as assertions. ---

    valid = set(ground_truth.get("valid_urls", []))
    for url in urls:
        checks += 1
        if url not in valid:
            failures.append(f"fabricated URL: {url} is not in the corpus")

    allowed = set(expected.get("allow_unsupported_mention") or [])
    for claim in ground_truth.get("unsupported_claims", []):
        if claim["claim"] in allowed:
            continue
        checks += 1
        match = _compile(claim["pattern"], "ground truth unsupported_claims").search(answer)
        if not match:
            continue
        if stance is None:
            failures.append(f"unsupported claim asserted: {claim['claim']}")
            continue
        verdict = stance(claim["claim"], passage_around(answer, match))
        # Only a refutation, or a hit that is not the claim at all, passes. NEUTRAL fails:
        # the agent's own rules require it to judge tier-4 content, not pass it on.
        if verdict not in ("REFUTED", "UNRELATED"):
            failures.append(f"unsupported claim {verdict.lower()}: {claim['claim']}")

    return OutcomeResult(passed=not failures, failures=failures, checks_run=checks)
