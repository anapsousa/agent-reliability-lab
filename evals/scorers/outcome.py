"""Outcome scorer — did the agent produce the right answer.

Deterministic checks only. Whether a figure was *asserted* or merely quoted in
order to refute it is a question about meaning, not about substrings, and it
belongs to the judge layer. This module fails loudly in the ambiguous cases and
lets a task opt out explicitly, which is honest; guessing would not be.

The one exception is opt-in: pass `stance` and each unsupported-claim regex hit is
handed to a calibrated judge (evals/judges/stance.py) with the paragraph around it. The
regex keeps total recall, and the judge decides only what the mention does. Without
`stance` the check behaves exactly as before, so historical numbers do not move.
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


def evaluate_outcome(
    answer: str,
    expected: dict,
    ground_truth: dict,
    stance: StanceFn | None = None,
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
        if url in urls:
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
