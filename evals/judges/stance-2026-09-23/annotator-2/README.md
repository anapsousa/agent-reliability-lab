# Second annotator — stance positives

**Status: scaffolding ready, no second labels yet.**

## Why

Every stance label behind the judge's calibration is one person's, and that person also
wrote the bar the judge is measured against. The bar (ASSERTED recall >= 90%) rests on 8
positives (9 in the 6 Oct round, before S010 moved to REFUTED). With one annotator there
is no way to tell a judge error from a labelling error, and round 1 already had eleven
key slips. So before the stance labels or the judge gate anything, and before the CI
gate is tightened on numbers that depend on them, a second person labels the same
positives blind.

## What is in this folder

| File | What |
|---|---|
| `items.jsonl` | 27 blind items: the 9 ever-ASSERTED passages + 18 REFUTED decoys, shuffled (seed 20261008), renamed A2-01 … A2-27 |
| `label.html` | Open from disk, no network. Keys 1-4, arrows, E to export `labels.json` |
| `key.json` | A2-id → original S-id. **Do not send this to the annotator.** |
| `labels.json` | The second annotator's export. Not here yet. |
| `agreement.json` | Written by `compare`. Not here yet. |

Decoys are there because a set of positives only gives the answer away. The passages are
public in this repo, so blinding rests on the instruction not to look; the key is
committed so the comparison is reproducible.

## Protocol

1. Confirm the bar in `evals/judges/annotator2.py` (`BAR_POSITIVE_AGREEMENT`,
   `BAR_KAPPA`) **before** opening any second label. Proposed: at least 8 of 9 positives
   agree on the pass/fail split the scorer uses, and Cohen's kappa >= 0.6 over the 27.
2. Send the annotator `label.html` only (it embeds the items). Brief them with the label
   definitions inside it, nothing else: not the judge's verdicts, not the first labels,
   not which items are positives, not how many.
3. They export `labels.json`. Save it here unchanged.
4. Run `uv run python -m evals.judges.annotator2 compare`. It writes `agreement.json`
   with agreement, kappa, agreement on the positives, and every disagreement by item.
5. Adjudicate disagreements together, blind to who said what, in the same way as round 2.
6. Write the result into the stance README and the repo's Known limits, whether the bar is
   met or not.

## What follows from the result

- **Bar met:** the 8 positives stand as ground truth for the judge's recall bar.
- **Bar missed:** the positives are not ground truth yet. The judge's 25% recall is a
  measurement against one person's reading, and the label definitions need tightening
  before anything else changes.

Either way, 9 positives is too few to calibrate a recall bar of 90% (one miss is 11
points). More positives are the real fix; this check only says whether the ones we have
can be trusted.
