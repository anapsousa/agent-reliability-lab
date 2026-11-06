# Forbidden-source fix on all repeat runs, 2026-11-06

**Status: re-score of stored answers only. No agent was re-run and no model was called.
Stored reports, the gate and the live runner are unchanged.** Extends
[`forbidden-source-rescore-2026-10-20.md`](forbidden-source-rescore-2026-10-20.md) to the
2 Nov opus-5-5 repeats ([`passk-opus-2026-11-02.md`](passk-opus-2026-11-02.md)), now that
the fix is merged (PR #4) and the owner has fixed the construct: a forbidden source is
cited only when the answer relies on it as evidence that the claim is true; naming it as
the origin of a claim in order to discredit it is not citing it.

## Result

1. **On all nine repeat runs (three models, three runs each) the check failed 155 runs.
   With the fix, 29.** Opus: 20, 20, 21 -> 4, 5, 4.
2. **The outcome layer moves by one task across all nine runs** (haiku-5-5 run 1,
   rsch-012). Of the 126 runs the fix clears, the other 125 still fail the
   `unsupported_claims` regex, because the same debunking paragraph names the figure and
   links the page it came from. pass^3 does not move for any model: outcome 3/40 each,
   all layers 0, 0 and 1/40.
3. **So the second false-fail is now fixed and the first is the one that binds.** The
   outcome level in the repeats says little about accuracy until the unsupported-claims
   regex is replaced on these runs too. The stance labels that fixed it for the baseline
   (`stance-rescore-2026-10-06.md`) are keyed to the baseline's passages, so they do not
   carry over; the repeats need their own reading or a calibrated judge.

## The bar on the new runs

The heuristic passes 75 forbidden-URL mentions in the opus repeats. None of them was in
the 203 mentions read on 20 and 21 Oct, so they were read on 6 Nov
(`judges/forbidden-source-2026-10-20/opus-2026-11-02-reading.json`): all 75 are
rejections (an explicit exclusion, or the claim's origin named with a verdict against
it). The reader was the assistant and was not blind to the heuristic's verdict, so this
is a consistency check, not a validation. Pinned by
`test_the_bar_holds_on_the_later_opus_repeats`. The 16 mentions the heuristic keeps as
cited in the opus runs are unread; they fail the check, as before.

## Numbers

`uv run python -m evals.source_rescore` (baseline tables unchanged from 20 Oct).

Repeats 2026-10-12 and 2026-11-02, forbidden-source fix alone:

| Series | Run | Outcome before | Outcome after | All layers before | All layers after | Runs failing the check | Tasks flipped (outcome / all layers) |
|---|---|---|---|---|---|---|---|
| haiku (claude-haiku-5-5) | 1 | 8/40 = 20% (10%-35%) | 9/40 = 22% (12%-38%) | 1/40 = 2% (0%-13%) | 1/40 = 2% (0%-13%) | 11 -> 2 | 1 / 0 |
| haiku (claude-haiku-5-5) | 2 | 8/40 = 20% (10%-35%) | 8/40 = 20% (10%-35%) | 1/40 = 2% (0%-13%) | 1/40 = 2% (0%-13%) | 16 -> 1 | 0 / 0 |
| haiku (claude-haiku-5-5) | 3 | 7/40 = 18% (9%-32%) | 7/40 = 18% (9%-32%) | 0/40 = 0% (0%-9%) | 0/40 = 0% (0%-9%) | 15 -> 3 | 0 / 0 |
| sonnet (claude-sonnet-5-5) | 1 | 7/40 = 18% (9%-32%) | 7/40 = 18% (9%-32%) | 0/40 = 0% (0%-9%) | 0/40 = 0% (0%-9%) | 18 -> 3 | 0 / 0 |
| sonnet (claude-sonnet-5-5) | 2 | 4/40 = 10% (4%-23%) | 4/40 = 10% (4%-23%) | 0/40 = 0% (0%-9%) | 0/40 = 0% (0%-9%) | 16 -> 3 | 0 / 0 |
| sonnet (claude-sonnet-5-5) | 3 | 4/40 = 10% (4%-23%) | 4/40 = 10% (4%-23%) | 0/40 = 0% (0%-9%) | 0/40 = 0% (0%-9%) | 18 -> 4 | 0 / 0 |
| claude-opus-5-5 (claude-opus-5-5) | 1 | 7/40 = 18% (9%-32%) | 7/40 = 18% (9%-32%) | 4/40 = 10% (4%-23%) | 4/40 = 10% (4%-23%) | 20 -> 4 | 0 / 0 |
| claude-opus-5-5 (claude-opus-5-5) | 2 | 6/40 = 15% (7%-29%) | 6/40 = 15% (7%-29%) | 3/40 = 8% (3%-20%) | 3/40 = 8% (3%-20%) | 20 -> 5 | 0 / 0 |
| claude-opus-5-5 (claude-opus-5-5) | 3 | 5/40 = 12% (5%-26%) | 5/40 = 12% (5%-26%) | 3/40 = 8% (3%-20%) | 3/40 = 8% (3%-20%) | 21 -> 4 | 0 / 0 |

| Series | Layer | pass^3 before | pass^3 after |
|---|---|---|---|
| haiku (claude-haiku-5-5) | outcome | 3/40 | 3/40 |
| haiku (claude-haiku-5-5) | all_layers | 0/40 | 0/40 |
| sonnet (claude-sonnet-5-5) | outcome | 3/40 | 3/40 |
| sonnet (claude-sonnet-5-5) | all_layers | 0/40 | 0/40 |
| claude-opus-5-5 (claude-opus-5-5) | outcome | 3/40 | 3/40 |
| claude-opus-5-5 (claude-opus-5-5) | all_layers | 1/40 | 1/40 |

