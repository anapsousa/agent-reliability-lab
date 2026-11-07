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
| `labels.json` | Human labels, committed once done (not yet; the owner has not labelled) |

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

## Reproduce

    uv run python -m evals.judges.stance_repeats count
    uv run python -m evals.judges.stance_repeats build

`tests/test_stance_repeats.py` rebuilds the set and checks it byte for byte.
