# Trace-level scores, baseline runs, 2026-10-08

**Superseded by [`trace-scores-2026-10-12.md`](trace-scores-2026-10-12.md).** The grounding
column below ran without the private context files and treated all arithmetic as
ungrounded; do not quote it. Kept as published for the record.

**Status: first pass, not calibrated, not gated.** Nothing here feeds `all_layers` or
`evals/gate.py`.

## Why

The outcome layer says whether the answer was right. It does not say which step went
wrong. The trace is now scored on its own, one question per check:

1. **Tool choice.** For every step: right tool here? Verdict per step: ok, wrong
   (unsourced fetch, failed call, unknown or forbidden tool, context read after
   research) or redundant (identical call, page already fetched).
2. **Stopping.** Did it stop when it had enough? "Enough" is the first step after which
   every `must_cite` source was in hand: surfaced, for `quick` tasks; fetched, otherwise.
   Calls after that point beyond a slack (quick 1, standard 2, deep 3) are an overrun.
   Answering before it is an early stop. A turn-cap ending is never a clean stop.
3. **Grounding.** Does the final text match what the tools returned? Every cited URL and
   every figure (percentages, currency amounts) must appear in a tool result from the
   same run.

Code: `evals/scorers/trace.py`, tests in `evals/scorers/tests/test_trace.py`. New runs
store the result per task under `trace_scores` and per run under `summary.trace`; the
Inspect task reports it as a fourth metric, `trace`.

## Method for the stored runs

The committed reports keep each step's tool and arguments but not the tool output. The
fixture web is deterministic, so `evals/trace_rescore.py` rebuilds the output by replaying
each `web_search` and `web_fetch` against the frozen corpus with the same functions the
MCP server uses. Steps that errored in the real run keep an empty result.

```
uv run python -m evals.trace_rescore
```

## Results

The private context files are not present in this checkout, so `read_context` results
replay as empty. Any figure the agent took from its own business context therefore
counts as ungrounded here. Re-run on a machine with the context populated before quoting
the grounding column.

| Model | Tool choice (runs) | Mean step score | Stopping | Grounding | Outcome pass, grounding fail |
|---|---|---|---|---|---|
| haiku | 27/40 = 68% (52%-80%) | 98% | 11/30 = 37% (22%-54%) | 27/37 = 73% (57%-85%) | 4 |
| sonnet | 30/40 = 75% (60%-86%) | 97% | 16/30 = 53% (36%-70%) | 28/39 = 72% (56%-83%) | 2 |
| opus | 32/40 = 80% (65%-90%) | 96% | 15/30 = 50% (33%-67%) | 23/40 = 57% (42%-71%) | 0 |

Brackets are 95% Wilson intervals. Stopping applies to the 30 tasks with a `must_cite`;
grounding to runs whose answer contains at least one URL or figure.

| Model | Step verdicts | Overrun runs (calls after enough) | Early stops | Turn-cap | Ungrounded URLs |
|---|---|---|---|---|---|
| haiku | ok 585, wrong 15, redundant 3 | 16 (2, 2, 3, 3, 3, 6, 9, 10, 11, 11, 14, 15, 15, 16, 34, 35) | 2 | 1 | 1 |
| sonnet | ok 373, wrong 21, redundant 0 | 14 (2, 2, 2, 2, 3, 3, 7, 7, 7, 7, 10, 11, 14, 17) | 0 | 0 | 8 |
| opus | ok 325, wrong 27, redundant 0 | 15 (2, 2, 2, 3, 4, 4, 5, 5, 6, 6, 6, 6, 7, 14, 14) | 0 | 0 | 8 |

Every "wrong" step is the same thing: a `web_fetch` on a URL no earlier step surfaced,
i.e. a URL from memory. Haiku also repeated three identical calls.

Most frequent ungrounded figures:

- **haiku**: 89% x2, 38% x2, 32% x1, 25.5% x1, 32.1% x1, 40% x1, 1.6 (money) x1, 270 (money) x1
- **sonnet**: 70% x2, 51% x1, 68% x1, 90% x1, 89% x1, 199.2 (money) x1, 270 (money) x1, 275 (money) x1
- **opus**: 68% x2, 2390 (money) x2, 199 (money) x2, 22 (money) x2, 1.3 (money) x1, 50% x1, 60% x1, 259 (money) x1

## What it shows, and what it does not

- **The ranking flips again, per check.** Opus is best on tool choice and worst on
  grounding; haiku is worst on stopping. A single trace score would hide that, which is
  the argument for keeping the three apart.
- **Haiku does not stop.** 16 of 30 applicable runs overran, two by more than 30 calls.
  That is the component layer's "step budget exceeded", now located: the budget is blown
  *after* the agent already had its sources, not on the way to them.
- **Most ungrounded figures are arithmetic, not fabrication.** Spot checks: 89% is
  100% less AIQ's 11%; 68% and 50% are growth rates computed from Northgate's market
  figures; EUR 2,390 and EUR 199 are annual-billing calculations from the EUR 249 price.
  Opus does more of this arithmetic, and labels several results "my calculation", which is largely why it scores worst here. The check
  is doing what it says (no tool returned the number) and is not yet a fabrication
  detector. Haiku's "89% treat judge scores as ground truth" is an overreach worth a
  look: the source says 11% calibrated, not that the rest treat scores as ground truth.
- **Ungrounded URLs are the strongest signal.** 8 each for sonnet and opus: corpus URLs
  cited without being returned by any tool in that run. The outcome layer passes these,
  because the URL is valid somewhere in the corpus.

## Next

1. Label 30 traces by hand (tool choice, stopping, grounding) and calibrate the slack and
   the grounding rule against them before any of this is gated.
2. Let grounding accept figures the answer explicitly marks as derived, then check the
   arithmetic, instead of flagging all of them.
3. Attribution: check a grounded figure against the source it is attributed to, not just
   against any tool output.
4. Keep the raw transcripts the runner already writes to `evals/runs/claude-code/`
   (gitignored). The 2026-09-23 ones are not in this checkout, which is why this pass
   had to replay.
