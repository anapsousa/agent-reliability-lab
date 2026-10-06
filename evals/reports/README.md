# Reports

One JSON per run, committed. `evals/gate.py` compares a PR's newest report per
(agent, harness, model) series with the base branch's newest.

## Baseline — research-agent v1, real Claude Code, 2026-09-23

First real-model run of the full golden set. The agent ran as itself (`claude -p`, pinned
`agent.md` as system prompt) against the frozen fixture web served by
`mcp/fixture-web/`. It ran on the Claude subscription, and cost is Claude Code's
API-equivalent figure.

| Model | Outcome | Trajectory | Components | All layers | API-equiv cost | p95 latency |
|---|---|---|---|---|---|---|
| haiku | 52% (38–67) | 95% | 8% | 0% | $1.91 | 55 s |
| sonnet | 40% (26–55) | 95% | 28% | 20% (10–35) | $3.44 | 80 s |
| opus | 12% (5–26) | 92% | 38% | 10% (4–23) | $5.59 | 46 s |

Brackets are 95% Wilson intervals. On 40 tasks they span about ±15 points.

## Known issue: the outcome layer ranks these models backwards

**Do not read the outcome column as model quality.** The always-on `unsupported_claims`
check fails any answer in which a tier-4 figure appears, including answers that quote
the figure in order to reject it. Opus does that most often, so it scores worst. The
component layer's failures were checked and are real: step budgets blown, and URLs
fetched from memory rather than from search results.

The reports below stay as they were. The stance judge was calibrated against adjudicated
human labels and missed its bar, so it is not used; the stored transcripts were re-scored
with the human labels instead. See `stance-rescore-2026-10-06.md`: opus moves from 12% to
25-28% on outcome, and the ranking is still not separable at n = 40.
