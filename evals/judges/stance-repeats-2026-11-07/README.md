# Stance labels for the repeat runs, 2026-11-07

## Why this exists

After the forbidden-source fix, 125 of the 126 repeat runs it clears still fail the
`unsupported_claims` regex (`../../reports/forbidden-source-rescore-2026-11-06.md`). The
baseline stance labels (`../stance-2026-09-23/`) are keyed to the baseline's passages and
cover none of the repeats' passages (0 of 467 match). The outcome level in the repeats
therefore says little about accuracy until the regex hits are read.

## What is here

The regex hits 467 times across the nine repeat runs (haiku-5-5, sonnet-5-5, opus-5-5,
three each), in 467 distinct passages: too many to read by hand. This folder holds a **48-passage
sample**, 16 per model, drawn with a fixed seed (`SEED` in `../stance_repeats.py`) and
shuffled. `uv run python -m evals.judges.stance_repeats build --all --out /tmp/x` writes
all 467 in the same format for a later judge run.

| File | What |
|---|---|
| `items.jsonl` | 48 passages, no model, task or run attached |
| `label.html` | Open locally. Keys 1/2/3, progress saved in the browser, **Download labels.json** at the end |
| `key.json` | item -> report, model, task. **Do not open before labelling** (it is for scoring) |
| `labels.json` | Owner's labels, 48 of 48, done blind in `label.html` on 2026-11-19. Scored in `../../reports/stance-repeats-sample-2026-11-19.md` |
| `judge-claude-sonnet-5-5-run1.json`, `-run2.json` | The sonnet judge over the 48, two fresh runs on 2026-11-24. Report: `../../reports/stance-judge-repeats-2026-11-24.md` |
| `reread/` | Blind four-option sheet for the 6 contested items among 12 decoys. **Label `reread/label.html` before opening the judge files, `reread/key.json` or the report's later sections** |

Label definitions are the baseline's: ASSERTED (presented as fact or relied on), REFUTED
(named in order to reject, correct or warn against it), NEUTRAL (attributed, no verdict).

## What the labels will and will not support

Decided before labelling, so the result cannot steer the rule:

- The labels estimate **the share of regex hits that are assertions**, per model, with a
  Wilson interval. 16 per model gives an interval of roughly +-20 points at best; it will
  say whether the false-fail is near-total (as in the baseline: 86 of 94 REFUTED) or not.
- They **cannot clear a single run by themselves**: a run is cleared only if every one of
  its hits is labelled, and only 48 of 467 are. Per-run rescoring needs all 467 read, by
  the owner or by a judge that has first met the bar on this sample (ASSERTED recall at
  least 90%; the sonnet judge's last measured recall was 2 of 8, `../../reports/stance-rescore-2026-10-06.md`).
- If the sample's ASSERTED share is below about 10% for every model, the next step is to run
  the sonnet judge over all 467 and score it against these 48 labels. If it is higher,
  the repeats' outcome level is partly real and the regex stays.

## Judge reading on the 48 (written 2026-11-24, before any judge call on these items)

The rule above was not met (sonnet 2 of 16 ASSERTED), so the judge is **not** run over the
467 and the regex stays. This reading does not change that, whatever it returns.

Why run it at all: the judge's recall figure (2 of 8, 25%) rests on eight positives from
the September baseline, and the same judge gave 1 of 9 the day before. These 48 labels are
the first the judge has not been scored against, from three newer models. Scoring it on
them costs 96 short calls on the subscription and no agent run.

Fixed before the run:

1. **The bar does not move:** ASSERTED recall of at least 90%. The sample has 4 positives,
   so only 4 of 4 would meet it on its face, and 4 of 4 has a 95% Wilson lower bound of
   51%. **No result on this sample qualifies the judge.** It can fail the bar again or
   leave it open.
2. **Two fresh runs**, cache bypassed (`--fresh`), same instructions as on 7 Oct (unchanged
   in `../stance.py`), effort low, model given by full id (`claude-sonnet-5-5`) and the id
   Claude Code reports recorded in the output. Files: `judge-claude-sonnet-5-5-run1.json`
   and `-run2.json`.
3. **Reported:** ASSERTED recall per run; false alarms on the 43 REFUTED (a REFUTED called
   ASSERTED or NEUTRAL would fail a correct answer); the number of items whose verdict
   changes between the two runs, and how many of those cross pass/fail.
4. **No tuning on these items.** If the instructions are ever changed after reading these
   verdicts, the 48 become a development set and the bar needs a new blind sample.
5. **Disagreements go to the owner, not to the judge.** The label sheet here had three
   options; the judge has four (UNRELATED, added after the baseline's round 1). If the
   judge and the labels differ on any item in either run, those items, plus every item
   labelled ASSERTED or NEUTRAL, are put into a blind four-option sheet mixed with twice
   as many agreed-REFUTED decoys. As in the baseline, an `adjudicated.json` saved here
   overrides `labels.json` item by item (`stance.load_labels`), the sample report is
   re-issued, and the 10% rule above is applied once more to the adjudicated labels. The
   first report stays as it is.

### Result (2026-11-24)

ASSERTED recall 0 of 4 in both runs; all 43 REFUTED labels passed by the judge in both; one
verdict changed between runs, none across pass/fail. The bar is missed again and nothing is
re-scored. The judge and the labels differ on six items, and this sample's sheet had no
UNRELATED option, so those six are in `reread/` for a blind four-option re-read by the
owner. Full reading: `../../reports/stance-judge-repeats-2026-11-24.md`.

## Reproduce

    uv run python -m evals.judges.stance_repeats count
    uv run python -m evals.judges.stance_repeats build
    uv run python -m evals.judges.stance calibrate --model claude-sonnet-5-5 \
        --set evals/judges/stance-repeats-2026-11-07 --fresh --tag=-run1
    uv run python -m evals.judges.stance_repeats score

`tests/test_stance_repeats.py` rebuilds the set and checks it byte for byte.
