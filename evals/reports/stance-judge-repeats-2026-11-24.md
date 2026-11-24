# Stance judge against the repeat-run sample, 2026-11-24

The sonnet stance judge was scored against the 48 owner labels of the repeat-run sample
(`../judges/stance-repeats-2026-11-07/`), twice, with the cache bypassed. What the reading
could and could not show was written into that folder's README and committed (`4b23190`)
before any judge call on these items. No agent was run and no score changes.

**Owner: do the re-read sheet (`../judges/stance-repeats-2026-11-07/reread/label.html`)
before reading past the first table.** The later sections describe the contested passages.

## Result

| Run | Model reported | Agreement | Pass/fail agreement | Kappa | ASSERTED recall | REFUTED called a failure |
|---|---|---|---|---|---|---|
| 1 | claude-sonnet-5-5 | 43 of 48 (89.6%) | 43 of 48 | 0.35 | **0 of 4** | 0 of 43 |
| 2 | claude-sonnet-5-5 | 42 of 48 (87.5%) | 43 of 48 | 0.30 | **0 of 4** | 0 of 43 |

Pass/fail is the split the outcome scorer acts on: REFUTED or UNRELATED pass, ASSERTED or
NEUTRAL fail.

## Against what was fixed beforehand

1. **The bar (ASSERTED recall of at least 90%) is missed again: 0 of 4 in both runs**
   (95% Wilson 0% to 49%). The October figure was 2 of 8. The two are not pooled: the
   October run asked for the alias `sonnet` and did not record which model answered.
2. **Stability:** 1 of 48 verdicts changed between the runs (R021, REFUTED then
   UNRELATED), and none crossed pass/fail. In run 2 the judge's own reason for R021 argues
   for REFUTED while its stance field says UNRELATED, so the one change is the judge
   contradicting itself, not a borderline passage.
3. **False alarms:** none. Every one of the 43 REFUTED labels was passed by the judge in
   both runs. Its error on this sample runs one way only: it passes what the label fails.
4. **No tuning.** The instructions are the October ones, byte for byte.
5. **The disagreements go back to the owner.** See the next section.

## What this does not settle

The judge and the labels differ on five items in both runs (the four ASSERTED and the one
NEUTRAL), and on a sixth in run 2. This run cannot say which side is right on any of them,
for a reason that is a fault in the sample's design, not in the labelling: **the sheet the
48 were labelled on had three options, and the judge has four.** UNRELATED was added in
October, after the baseline's first round, for a correctly derived figure that happens to
share the digits of a bad one. The sample's sheet was built from the older three-option
template, so that reading could not be recorded.

So, as fixed beforehand, the six contested items are in a blind four-option sheet with
twelve agreed-REFUTED decoys, renamed and shuffled (`reread/`, 18 items):

    uv run python -m evals.judges.stance_repeats reread   # already built and committed
    # label reread/label.html, save its export as reread/labels.json, then:
    uv run python -m evals.judges.stance_repeats apply    # writes adjudicated.json
    uv run python -m evals.judges.stance_repeats score    # ASSERTED share per model

What each outcome means, written now:

- The 10% rule in the sample's README is applied once more to the adjudicated labels, and
  that reading is final for this sample. The 19 Nov report stays as it is.
- **Fewer positives do not make the judge's bar easier to meet.** Recall is measured on
  positives. If the re-read leaves none, this sample cannot measure the judge's recall at
  all, and its only measured recall is still 2 of 8.
- If the labels stand, the judge has missed 4 of 4 real assertions on new models' answers
  and there is no case for running it over the 467.

## What the judge said (read after the re-read)

- Two of the four ASSERTED labels it called UNRELATED, and the NEUTRAL one as well: it
  reads the EUR 199 in them as annual-billing arithmetic on the EUR 249 list price. This is
  the category behind five of the judge's six misses in October.
- The other two ASSERTED labels it called REFUTED, with the reason that the figure is
  named only to be set against the vendor's own page.
- Per-item verdicts and reasons: `judge-claude-sonnet-5-5-run1.json` and `-run2.json` in
  the sample folder.

## Limits

- **Four positives.** Nothing here estimates the judge's recall with any precision, and
  nothing here could have qualified it (4 of 4 has a Wilson lower bound of 51%).
- **One annotator**, and the same person who set the bar. 48 of 467 passages read.
- **Three-option labels against a four-stance judge**, until the re-read is done.
- **The re-read is not fully blind.** It follows a judge run whose headline is public, the
  key is committed, and whoever labels knows the set contains the contested items. The
  decoys and the renaming hide which ones.
- The judge is `claude -p` at low effort with every tool disabled, run from a checkout of
  this repository, as in October. It is not a bare model call: Claude Code's own context
  travels with it.
- Two runs put a floor under the judge's instability, not a ceiling.

## Reproduce

    uv run python -m evals.judges.stance calibrate --model claude-sonnet-5-5 \
        --set evals/judges/stance-repeats-2026-11-07 --fresh --tag=-run1
    uv run python -m evals.judges.stance stability \
        evals/judges/stance-repeats-2026-11-07/judge-claude-sonnet-5-5-run1.json \
        evals/judges/stance-repeats-2026-11-07/judge-claude-sonnet-5-5-run2.json

Each calibrate run is 48 calls on the subscription, under a minute at six workers. A fresh
run overwrites the file of the same tag, so use a new tag.
