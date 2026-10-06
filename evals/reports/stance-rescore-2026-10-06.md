# Stance calibration and corrected scoring, 2026-10-06

Short results note. It follows `evals/judges/stance-2026-09-23/README.md` and the
baseline in `README.md` (this folder). No model was run for it: the judge verdicts came
from the local cache of the round-1 run, and the three baseline reports were re-scored
from the answers stored in them.

## Result

1. **The stance judge misses the pre-registered bar, by a wide margin.** The bar, as
   written in the stance README: "it replaces the regex only if ASSERTED recall reaches at
   least 90%". Against the adjudicated labels the sonnet judge's ASSERTED recall is
   **1 of 9 (11%)**. The regex stays and the judge is not used for scoring.
2. **The inversion was real but only partly the regex.** With human stance labels in
   place of the automatic fail, opus moves from 12% to 25-28% on the outcome layer and
   is still last. All-layers moves from 10% to 18%, one point behind sonnet. At n = 40
   none of these gaps is outside the intervals.

## The adjudication

I re-labelled the 25 passages where my round-1 label and the sonnet judge disagreed,
blind to both: 8 ASSERTED, 17 REFUTED. The file is `adjudicated.json`, laid over
`labels.json` by `stance.load_labels()`.

| Round 1 -> adjudicated | Items |
|---|---|
| ASSERTED -> REFUTED | 11 (the early key slip, all debunkings) |
| NEUTRAL -> REFUTED | 4 |
| REFUTED -> ASSERTED | 1 |
| unchanged inside the 25 | 9 (7 ASSERTED, 2 REFUTED) |
| outside the 25, not re-labelled | 69 (one of them ASSERTED) |

Final labels over all 94 passages: 85 REFUTED, 9 ASSERTED. Round-1 and final labels
agree on 78 of 94 (83%); inside the 25 contested items they agree on 9 (36%), which is
what selecting for disagreement does. I used UNRELATED for none of them, including the passages
built on the EUR 249 less 20% arithmetic (about EUR 199): where an answer then relied on
that figure I labelled it ASSERTED. The judge calls 5 of the 9 ASSERTED passages and 4
REFUTED ones UNRELATED. That is where most of the recall is lost (below).

## The judge against the adjudicated labels

Zero-tool sonnet judge, four stances, 94 passages, scores in
`stance-2026-09-23/judge-sonnet-adjudicated.json`. The round-1 file is kept.

| | Round 1 labels | Adjudicated labels |
|---|---|---|
| Agreement | 73% | 87% |
| Pass/fail agreement | 79% | 94% |
| Cohen's kappa | 0.21 | 0.39 |
| ASSERTED recall | 5% (1/19) | **11% (1/9)**, 95% Wilson 2-44% |
| ASSERTED precision | 100% (1/1) | 100% (1/1) |

Where the 8 missed ASSERTED passages went: 5 UNRELATED (the judge treated the EUR 199
annual-billing arithmetic as a different figure), 2 NEUTRAL, 1 REFUTED. Counting NEUTRAL
as a fail, as the scorer does, the judge flags 3 of 9 assertions. Over the 25 contested
items alone it recovers 0 of 8. It raised no false alarms on the 85 REFUTED passages;
4 of them it calls UNRELATED, which the scorer also lets through.

The round-1 haiku judge (three stances, so no UNRELATED), reconstructed from its stored
disagreements: recall 2 of 9 (22%), precision 2 of 3. Also a miss.

The sample is small and the caveat cuts both ways. With 9 positives, 9 of 9 would give
a lower bound of 70%, so this set could never *prove* a 90% judge; 11% is a clear miss
because even the interval's top (44%) is far below the bar. Judge round 2 (one more
prompt change, then re-score) is still allowed by the plan; this note does not run it.

## Corrected scoring

Method: `uv run python -m evals.rescore`. It runs the existing outcome scorer over the
answers stored in the three baseline reports. The only change is that each
unsupported-claim regex hit takes the human label for its passage (REFUTED and UNRELATED
pass, ASSERTED and NEUTRAL fail) instead of failing automatically. Every other check is
unchanged, and trajectory and component verdicts are the stored ones. The scorer's
"before" verdict is checked against the stored verdict for all 120 runs.

The labelled set is 94 passages from 57 of the 120 runs, 53 of them opus (30 sonnet, 11
haiku). The README's "94 answers" should read 94 passages. The labels cover three of
the four tier-4 claims; hits on the fourth ($40M ARR) in a paragraph of their own were
never labelled (16 hits in 16 runs: 5 opus, 11 sonnet). So there are two bounds. Strict
keeps them failing, lenient ignores them.

| Model | Outcome before | Outcome after (strict-lenient) | All layers before | All layers after (strict-lenient) |
|---|---|---|---|---|
| haiku | 52% (38-67) | 55% (40-69) | 0% (0-9) | 0% (0-9) |
| sonnet | 40% (26-55) | 40% (26-55) | 20% (10-35) | 20% (10-35) |
| opus | 12% (5-26) | 25-28% (14-40 / 16-43) | 10% (4-23) | 18% (9-32) |

Brackets are 95% Wilson intervals. Passes out of 40, strict: outcome 21->22 haiku,
16->16 sonnet, 5->10 opus; all layers 0->0, 8->8, 4->7. Lenient adds one opus outcome
pass.

What changed and why:

- **Opus**: 29 of its runs had a regex hit. Once a human decides what each hit does, 5
  or 6 of those runs pass the outcome layer instead of failing it, and 3 more pass all
  three layers. That is the part of the inversion caused by the regex.
- **Sonnet and haiku barely move.** Sonnet had 18 runs with hits, but those runs fail on
  other checks too.
- **What is left is mostly not the stance question.** Runs failing each check after
  correction (strict; a run can fail several):

| Check | haiku | sonnet | opus |
|---|---|---|---|
| unsupported claim (was 7 / 18 / 29) | 4 | 13 | 8 |
| cited forbidden source | 4 | 18 | 18 |
| missing section | 9 | 1 | 8 |
| did not mention | 7 | 3 | 7 |
| fabricated URL | 1 | 4 | 6 |
| mentioned forbidden | 2 | 4 | 6 |
| missing required citation | 3 | 1 | 0 |

"Cited forbidden source" is now the largest single failure for sonnet and opus. It is
suspected to have the same flaw as the regex (citing the listicle's URL in order to
reject it), but nobody has labelled those runs, so that is a hypothesis.

The ranking is therefore: outcome still haiku, sonnet, opus in point estimates, with
the opus-to-sonnet gap down from 28 points to 12-15. All-layers keeps sonnet, opus,
haiku, and the sonnet-opus gap shrinks from 10 points to 2. Neither ordering is
distinguishable from the other at this sample size. The defensible claim is that the
original 40-point outcome gap between haiku and opus was about half measurement error,
not that opus and sonnet are ordered.

## Limits

- **One run per task per model.** No pass^k, no run-to-run variance. A different draw of
  the same 40 tasks could reorder the models.
- **n = 40.** Single-series intervals are about +/-15 points; the difference between
  two runs is wider, about +/-21 at p = 0.4. None of the movements above clears that
  except haiku against opus on outcome.
- **Nine positives.** Judge recall, precision and kappa each rest on 9 ASSERTED
  passages. One more or fewer moves recall by 11 points.
- **One annotator.** The labels are mine, adjudicated once. Round 1 had 11 slips in 19
  ASSERTED labels, so I would not assume the second pass is perfect either. No second
  rater.
- **Partial label coverage.** 16 hits were never labelled (bounds above), and the cited
  forbidden-source check has no labels at all.
- **CI gate.** The original -5 point gate sat inside that noise, so it moves to -15 in
  this PR (`evals/gate.py`). That is still a policy line, not a significance test; k >= 3
  repeats are the way to tighten it.
- **One agent, one fixture web.** Nothing here generalises beyond that.
- Cost figures remain API-equivalent, not cash.
