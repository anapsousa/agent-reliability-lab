# pass^k, opus, k = 3, and the baseline re-run on today's context, 2026-11-02

**Status: repeat-run measurement for the third model, and the first like-for-like check of
the 23 Sep baseline.** One agent, one corpus, three runs. Nothing here feeds the gate.
Reports: [`repeats-2026-11-02/`](repeats-2026-11-02/).

## Why

[`passk-2026-10-12.md`](passk-2026-10-12.md) repeated haiku and sonnet three times each and
left two items open: opus was never repeated, and the baseline's models were never re-run
on today's context, so the drop between the 23 Sep baseline and the 12 Oct repeats (haiku
52% to 19%, sonnet 40% to 12% on outcome) could not be split between the model change and
the rebuilt context files. Opus closes both at once: the 23 Sep baseline ran
`claude-opus-5-5`, and `--model claude-opus-5-5` still resolves to that id, so these three
runs are the same model as the baseline, on the rebuilt context and a newer CLI.

## Method

- `python -m evals.runners.claude_code --model claude-opus-5-5`, three times, one after
  another, concurrency 4 inside a run, on the `main` at bd04ddf. Full model id, not the
  `opus` alias. Agent `v1`, prompt, corpus and context files unchanged between the runs and
  identical to the 12 Oct repeats (context rebuilt from the orchestrator repo as of the
  6 Aug pin; see `trace-scores-2026-10-12.md`).
- Claude Code 2.1.303. The baseline ran 2.1.280, the 12 Oct repeats 2.1.294.
- Raw transcripts kept with `evals.keep_runs` (outside the repo). Stored answers
  pseudonymised the same way as the baseline and the 12 Oct repeats (README, "Example
  data"); scores were computed before that and are unchanged.
- Tables from `uv run python -m evals.passk --dir evals/reports/repeats-2026-11-02`.

## Results

## claude-opus-5-5 (claude-opus-5-5), k = 3, 40 tasks

| Layer | Single-run pass rate (each run) | Largest gap between runs | pass^3 | pass@3 | Tasks that flip |
|---|---|---|---|---|---|
| outcome | 15% (18%, 15%, 12%) | 5 pts | 3/40 = 8% (3%-20%) | 10/40 = 25% | 7 |
| trajectory | 93% (92%, 92%, 92%) | 0 pts | 36/40 = 90% (77%-96%) | 38/40 = 95% | 2 |
| components | 28% (30%, 30%, 25%) | 5 pts | 9/40 = 22% (12%-38%) | 14/40 = 35% | 5 |
| all_layers | 8% (10%, 8%, 8%) | 3 pts | 1/40 = 2% (0%-13%) | 7/40 = 18% | 6 |
| tool_choice | 83% (82%, 82%, 85%) | 3 pts | 33/40 = 82% (68%-91%) | 34/40 = 85% | 1 |
| stopping | 44% (43%, 50%, 40%) | 10 pts | 12/30 = 40% (25%-58%) | 15/30 = 50% | 3 |
| grounding | 68% (65%, 65%, 75%) | 10 pts | 22/40 = 55% (40%-69%) | 32/40 = 80% | 10 |

Outcome flips by category: competitor 1/7, discovery 1/7, fact-check 3/7, lead 1/6, market 0/7, tech-comparison 1/6.

The gate fails a PR that loses more than 15 points on `all_layers` or `outcome`. The largest gap between two runs of the same unchanged agent here is 5 points (claude-opus-5-5, outcome), below the tolerance.

Brackets are 95% Wilson intervals. Trace rows are not gated. `all_layers` is outcome,
trajectory and components together.

## The baseline against the repeats: same model id, different context files and CLI

The 23 Sep opus baseline (`research-agent-v1-claude-code-opus-2026-09-23T08-11-55Z.json`)
was run on the original context files, which were not kept, on Claude Code 2.1.280.

| Layer | Baseline 23 Sep | Run 1 | Run 2 | Run 3 | Passed in baseline and every repeat | Passed in baseline, never in a repeat | Never in baseline, passed in some repeat |
|---|---|---|---|---|---|---|---|
| outcome | 5/40 | 7/40 | 6/40 | 5/40 | 2 | 1 | 6 |
| trajectory | 37/40 | 37/40 | 37/40 | 37/40 | 36 | 0 | 1 |
| components | 15/40 | 12/40 | 12/40 | 10/40 | 9 | 3 | 2 |
| all_layers | 4/40 | 4/40 | 3/40 | 3/40 | 0 | 2 | 5 |

Outcome failures by kind (a task can carry several):

| Failure kind | Baseline | Run 1 | Run 2 | Run 3 |
|---|---|---|---|---|
| unsupported claim asserted | 66 | 61 | 69 | 67 |
| cited forbidden source | 18 | 20 | 20 | 21 |
| fabricated URL | 8 | 9 | 11 | 10 |
| missing section | 8 | 9 | 8 | 7 |
| must-mention / must-not-mention misses | 16 | 15 | 13 | 14 |

Tasks whose outcome failures are **only** the two checks already known to fail debunkings
(`unsupported_claims`, `must_not_cite`): baseline 13, repeats 12, 14, 14. Component
failures: step budget exceeded 25 in the baseline, 28 / 28 / 30 in the repeats; unsourced
URL 22, then 19 / 22 / 21. API-equivalent cost $5.59 in the baseline, $5.85 / $5.64 / $5.78
here; p95 latency 46 s, then 47 / 48 / 56 s.

## What it shows

- **The opus baseline reproduces.** Outcome 12.5% on 23 Sep, 18 / 15 / 12% now; all layers
  10%, then 10 / 8 / 8%; the failure mix is the same to within a few counts. Rebuilding the
  context files and moving from CLI 2.1.280 to 2.1.303 did not move the level for this
  model.
- **So the haiku and sonnet drops were most likely the model change, not the context.**
  Those two series changed model (haiku-4-5 to haiku-5-5, sonnet-5 to sonnet-5-5) *and*
  context between 23 Sep and 12 Oct, and fell 33 and 28 points on outcome. Opus changed
  only context and CLI, and did not fall. This is consistent with the context rebuild being
  close to neutral; it does not prove it, since a smaller model could lean on the context
  files more than opus does, and n = 40 resolves about 15 points.
- **Three models, same shape.** Under the still-flawed outcome check, k = 3 single-run
  outcome rates are haiku 20 / 20 / 18%, sonnet 18 / 10 / 10%, opus 18 / 15 / 12%. pass^3
  on outcome is 3 of 40 for all three. pass^3 on all layers is 0, 0 and 1 of 40. The
  original baseline's ranking (52 / 40 / 12%) is gone with the model change, and nothing in
  the current numbers separates the three.
- **The level holds, the tasks do not, again.** Opus outcome moves 5 points between runs
  while 7 of 40 tasks change verdict; grounding moves 10 points while 10 of 40 flip, and
  pass^3 on grounding is 55% against a single-run 65-75%.
- **Only 2 outcome tasks have passed on every one of the four opus runs** (baseline plus
  three repeats), and no task has passed all layers on all four. One task passed every
  layer on all three repeats.
- **The gate's tolerance is still above the noise.** Largest gap on a gated layer, 5 points
  (outcome); the gate fails at 15. Three models, k = 3 each: the largest gap seen so far is
  sonnet's 7.5 points.

## Limits

- k = 3, one agent, one fixture corpus. pass^3 intervals are wide.
- The baseline comparison changes two things at once (context files and CLI version), so
  "the context rebuild is neutral" is an inference from one model, not a measurement of
  the rebuild alone.
- The outcome layer still carries the flawed `unsupported_claims` regex and the lexical
  `must_not_cite` rule (fix in draft PR #4, not merged, default unchanged): 12 to 14 of the
  33 to 35 failing outcome tasks per run fail on those two checks alone, so the outcome
  level says little about accuracy. The flips and the baseline comparison do not depend on
  the level.
- Trace rows come from the uncalibrated trace scorer; the 30-label comparison (PR #4) found
  all three checks under their 80% bar.
- The runs used the `main` runner, which still accepts aliases; the full id was passed by
  hand and `models_seen` confirms `claude-opus-5-5` in all three reports. Draft PR #6 makes
  the full id mandatory.

## Next

1. Haiku-4-5 and sonnet-5 by full id on today's context, if the CLI still serves them, to
   measure the context rebuild directly on the two models that dropped.
2. Merge the forbidden-source fix (PR #4) and re-score all twelve repeat reports with it, so
   the outcome level stops carrying the debunking failures.
3. A second annotator on the stance positives, before any judge number is quoted again.
