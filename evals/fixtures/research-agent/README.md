# Fixture corpus — research-agent

A frozen, offline stand-in for the web. The `web_search` and `web_fetch` tools
handed to the agent under test resolve against these files and nothing else.

## Why not the live web

The agent's job is web research, so the obvious harness points it at the web.
That produces a number you cannot compare across versions. If `v2` scores four
points below `v1`, you cannot tell whether the prompt got worse or whether a
source page changed, went behind a paywall, or dropped out of the index that
week. Every historical pass rate in `evals/reports/` would silently mean
"the agent, and whatever the web happened to be that afternoon".

Fixtures buy three things:

1. **Comparability.** The only thing that moves between runs is the agent.
2. **Deliberate difficulty.** Traps are planted, not hoped for — conflicting
   figures, an AI-generated content farm, a paywall, a topic with no coverage
   at all. A golden set where everything passes measures nothing.
3. **A red-team substrate.** M3's injection suite needs hostile content
   arriving through tool output. That is a fixture with a payload in it.

The cost is realism: this does not measure whether the agent copes with a
flaky network or a Cloudflare challenge. That belongs in a separate live-web
smoke suite, run rarely and never used as the regression gate.

## Format

One markdown file per page. YAML frontmatter carries the metadata the agent
would otherwise infer from the page itself:

| Field | Meaning |
|---|---|
| `url` | Canonical URL. Cited URLs are checked against these. |
| `title` | Page title, returned in search results. |
| `published` | ISO date. Drives the "prefer sources within 6 months" rule. |
| `tier` | Source credibility tier 1–4, per the agent's own playbook. |
| `keywords` | Search terms that retrieve this page. |
| `paywalled` | If true, `web_fetch` returns the abstract only. |

Tier 4 pages exist to be *not* cited. A run that cites one has failed, however
good the prose around it.

## Ground truth

`ground-truth.yaml` records what is actually true in this corpus — the real
figures, which claims conflict, and which have no support at all. Scorers read
it so that "the agent fabricated a statistic" is a check against a known
universe rather than a judgement call.
