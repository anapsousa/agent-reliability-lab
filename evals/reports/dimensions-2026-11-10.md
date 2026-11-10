# Five evaluation dimensions on the research agent, from the nine repeat runs (2026-11-10)

Plan item: P3 (evaluation strategy: quality, safety, reliability, latency, cost), the part
that needs no new model run. Code: `evals/dimensions.py`, tests: `evals/tests/test_dimensions.py`.

**No model was called for this report.** Every figure is read from the committed report JSON
in `evals/reports/repeats-2026-10-12/` (haiku-5-5, sonnet-5-5) and
`evals/reports/repeats-2026-11-02/` (opus-5-5): three runs of the same 40 tasks per model,
`research-agent` v1, Claude Code 2.1.x on the subscription. Reproduce with:

```
uv run python -m evals.dimensions --dir evals/reports/repeats-2026-10-12 \
    --dir evals/reports/repeats-2026-11-02
```

## The table

| Series | Quality: all layers / outcome (mean of k runs) | Reliability: pass^k / pass@k, all layers | Latency p50 / p95 / max (s) | Cost per run (API-equiv.) | Cost per all-layers pass | Safety |
|---|---|---|---|---|---|---|
| claude-opus-5-5 (k = 3) | 8% / 15% | 1/40 / 7/40 | 27.9 / 53.2 / 72.0 | $5.76 ($5.64-$5.85) | $1.73 (10 passes in 120 task-runs) | not measured |
| claude-haiku-5-5 (k = 3) | 2% / 19% | 0/40 / 1/40 | 16.4 / 35.5 / 55.1 | $0.19 ($0.19-$0.20) | $0.29 (2 passes in 120 task-runs) | not measured |
| claude-sonnet-5-5 (k = 3) | 0% / 12% | 0/40 / 0/40 | 18.3 / 39.6 / 105.0 | $2.83 ($2.78-$2.92) | n/a (no passes) (0 passes in 120 task-runs) | not measured |

How to read it:

- **Quality** is the mean single-run pass rate over the three runs, as recorded at run time.
  The `outcome` layer is known to be wrong in the failing direction (see `evals/reports/README.md`
  and `forbidden-source-rescore-2026-11-06.md`: 125 of 126 runs cleared by the forbidden-source
  fix still fail the `unsupported_claims` regex). The re-scores are separate reports and are not
  applied here, so the quality column understates all three models.
- **Reliability** is `evals.passk`: tasks that pass all three runs / tasks that pass at least once,
  out of 40. On `all_layers` no model passes more than 1 task every time.
- **Latency** is per-task wall time, the 120 task-runs of each model pooled; p95 is nearest-rank
  (an observed value). The sonnet maximum (105 s) is one task-run.
- **Cost** is Claude Code's API-equivalent figure. The runs used the subscription: no money was
  spent. Cost per `all_layers` pass is total cost over the number of passing task-runs, so it is
  only as meaningful as the pass count under it (2 for haiku, 10 for opus, 0 for sonnet).
- **Safety is not measured.** `redteam/suites/` and `redteam/findings/` are empty. The table says
  "not measured" rather than borrowing a proxy; the planned work is P5 (3-4 Dec).

## What the table says

1. **Cost spreads far more than quality does.** Opus costs about 30 times a haiku run
   ($5.76 against $0.19 for the same 40 tasks) and sonnet about 15 times, while the mean
   `all_layers` pass rate is 8%, 2% and 0% and none of the three is reliable. With rates this low,
   the order between models is within noise at n = 40 (one task is 2.5 points per run).
2. **Cost is recorded, not computed, in this repo.** `evals/runners/claude_code.py` copies the
   `total_cost_usd` field of Claude Code's result event unchanged (line 204) and sums it (line 317).
   There is no price table, no token field and no cache-read field in the repo or in any report
   JSON, so a per-token price cannot be checked here. What the files do show: the per-task costs
   add up exactly to each report's `summary.cost_usd.total` (all 12 reports, pinned by a test), so
   the recording is internally consistent.

3. **Latency tracks model size but the tail does not.** p50 runs 16 s (haiku), 18 s (sonnet),
   28 s (opus); p95 runs 36, 40 and 53 s. Sonnet's single 105 s task-run is the longest of the 360.
4. **Cheapest per passing run is not the same as best.** Haiku has the lowest cost per
   `all_layers` pass ($0.29) on 2 passes in 120; opus is $1.73 on 10. Neither number supports a
   model choice at this sample size. What would: more tasks, and the components layer repaired
   (its failures are real: step budgets and URLs from memory, per the baseline README).

## Unverified

- **Haiku cost drop.** The 23 Sep haiku-4-5 baseline
  (`evals/reports/research-agent-v1-claude-code-haiku-2026-09-23T08-11-54Z.json`) totals $1.91 over
  641 turns ($0.0030 per turn). The three haiku-5-5 runs total $0.19 each over 486-496 turns
  ($0.0004 per turn). Turns fell about 24%, cost about 90%. The per-turn cost of sonnet
  ($0.0079 on sonnet-5, $0.0071-$0.0073 on sonnet-5-5) and opus ($0.0143 baseline,
  $0.0142-$0.0144 on the 2 and 12 Oct and 2 Nov runs) is stable across Claude Code 2.1.280 to
  2.1.303, which argues against a general recording fault. Not checked, because the data is not in
  the repo: token counts, cache-read tokens, and the price Claude Code applied to each model.
  So (a) real token difference, (b) a price-table change for haiku, and (c) cache or alias
  accounting cannot be told apart from these files. Treat the haiku figures as "what Claude Code
  reported", not as evidence that haiku-5-5 is ten times cheaper.
- Sonnet and opus $/run were re-added from per-task `cost_usd` and match the summaries
  (sonnet $2.78-$2.92, opus $5.64-$5.85 per run); their earlier single-run baselines ($3.44 and
  $5.59) sit in the same range.

## Limits

- k = 3 and 40 tasks: ±15 points on a single run's rate (Wilson), wider on a difference.
- Alias drift: each series is keyed on the model actually seen; haiku-4-5 and the 5-5 models
  are not pooled.
- The 23 Sep baseline is single-run, so it is not in the table; its cost is quoted in point 2 only.
- Dollar figures are API-equivalent, not invoices.

## Next

P3 proper (Thu 19 Nov plan slot): put the same five columns on the reference system once it
exists, with pass^3 and a gate on cost and latency. The reference system is not built yet
(see the PR description).
