"""Loads the frozen fixture corpus and exposes it as agent tools.

The agent under test does web research, so it needs a web. This is that web:
closed, versioned, and identical on every run. See `research-agent/README.md`
for why the live one is the wrong thing to measure against.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import yaml

FIXTURES = Path(__file__).parent

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)


@dataclass(frozen=True)
class Page:
    url: str
    title: str
    published: str
    tier: int
    keywords: tuple[str, ...]
    paywalled: bool
    body: str

    def snippet(self, length: int = 240) -> str:
        """First prose paragraph, the way a search result would show it."""
        for block in self.body.split("\n\n"):
            text = " ".join(block.split())
            if text and not text.startswith("#") and not text.startswith("*"):
                return text[:length] + ("…" if len(text) > length else "")
        return ""

    def public_body(self) -> str:
        """Paywalled pages surrender their abstract and nothing else."""
        if not self.paywalled:
            return self.body
        cut = self.body.find("**[Subscriber content")
        return self.body[:cut].rstrip() if cut != -1 else self.body


@dataclass(frozen=True)
class Corpus:
    pages: tuple[Page, ...]
    ground_truth: dict

    def by_url(self, url: str) -> Page | None:
        url = url.rstrip("/")
        return next((p for p in self.pages if p.url.rstrip("/") == url), None)

    def search(self, query: str, limit: int = 5) -> list[Page]:
        """Keyword overlap ranking. Crude on purpose — a clever retriever would
        do part of the agent's job for it and flatter the score."""
        terms = {t for t in re.findall(r"[a-z0-9%$]+", query.lower()) if len(t) > 2}
        if not terms:
            return []
        ranked: list[tuple[int, Page]] = []
        for page in self.pages:
            haystack = " ".join(
                [page.title.lower(), " ".join(page.keywords).lower(), page.body.lower()]
            )
            hits = sum(1 for t in terms if t in haystack)
            if hits:
                ranked.append((hits, page))
        ranked.sort(key=lambda pair: (-pair[0], pair[1].url))
        return [page for _, page in ranked[:limit]]


def _parse(path: Path) -> Page:
    match = _FRONTMATTER.match(path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError(f"fixture {path.name} has no YAML frontmatter")
    meta = yaml.safe_load(match.group(1))
    return Page(
        url=meta["url"],
        title=meta["title"],
        published=str(meta["published"]),
        tier=int(meta["tier"]),
        keywords=tuple(meta.get("keywords", [])),
        paywalled=bool(meta.get("paywalled", False)),
        body=match.group(2).strip(),
    )


@cache
def load_corpus(agent: str = "research-agent") -> Corpus:
    root = FIXTURES / agent
    pages = tuple(
        sorted((_parse(p) for p in root.glob("*.md") if p.name != "README.md"), key=lambda p: p.url)
    )
    ground_truth = yaml.safe_load((root / "ground-truth.yaml").read_text(encoding="utf-8"))

    declared = set(ground_truth["valid_urls"])
    actual = {p.url for p in pages}
    if declared != actual:
        raise ValueError(
            "ground truth and fixtures disagree. "
            f"only in ground truth: {sorted(declared - actual)}; "
            f"only in fixtures: {sorted(actual - declared)}"
        )
    return Corpus(pages=pages, ground_truth=ground_truth)
