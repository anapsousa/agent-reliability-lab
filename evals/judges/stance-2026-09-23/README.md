# Stance calibration — 2026-09-23

## Why this exists

The first real-model baseline (three models, 40 tasks each, `evals/reports/*claude-code*`)
showed the outcome layer ranking the models backwards: opus 12%, sonnet 40%, haiku 52%.

The cause is the always-on `unsupported_claims` check. It fails a run whenever a tier-4
figure (the 91% failure rate, the $199 price, …) appears anywhere in the answer. A regex
cannot tell an assertion from a debunking, and `ground-truth.yaml` says so. The most
careful model names the listicle and explicitly refuses its figure, and scores worst for
it. Of the 94 regex hits across the 120 runs, 53 are opus.

The fix is a cascade: the regex stays as a cheap pre-filter, and a zero-tool
`claude -p` judge classifies only the hits as ASSERTED, REFUTED or NEUTRAL. A judge nobody
has checked is not a fix, though. It is a second unvalidated scorer. So the human labels
come first, blind, and the judge is scored against them before it scores the agent.

## Files

| File | What |
|---|---|
| `items.jsonl` | 94 passages, shuffled, with no model or task attached (the key is kept outside git) |
| `label.html` | Open locally. Keys 1/2/3, progress saved in the browser, **Download labels.json** at the end |
| `labels.json` | Human labels, committed once done |

## Label definitions

- **ASSERTED**: the answer presents the figure as fact or relies on it for a conclusion.
- **REFUTED**: the answer names the figure in order to reject, correct or warn against it.
- **NEUTRAL**: the answer attributes the figure to its source without a verdict. The
  agent's rules require it to judge tier-4 content, so NEUTRAL is a softer failure, and
  the scorer policy for it is decided after labelling, not before.

## Round 1 result (2026-09-24): the judge is not calibrated yet

94 human labels: 71 REFUTED, 19 ASSERTED, 4 NEUTRAL. The regex had called all 94 assertions.

| Judge | Agreement | Pass/fail agreement | κ | ASSERTED recall |
|---|---|---|---|---|
| haiku, three stances (`judge-haiku.json`) | 78% | 82% | 0.26 | 16% |
| sonnet, four stances (`judge-sonnet.json`) | 73% | 79% | 0.21 | 5% |

Both judges agree with the human on REFUTED (70 of 71). They disagree on ASSERTED, and
reading the 19 passages shows three different causes:

1. **Label slips.** Eleven are unambiguous debunkings ("Don't repeat it", "not usable",
   "Don't use. It's almost certainly wrong"). All eleven sit in the first 18 items of a
   shuffled set, which points to the key meaning slipping early, not to the judge.
2. **A missing category.** Four passages match the `$199` regex through correct arithmetic
   (EUR 249 less 20% for annual billing ≈ EUR 199). They are not the claim at all. Round 1
   had no label for that, so **UNRELATED** now exists, and it passes the scorer.
3. **Real misses.** Four are genuine assertions, which the judges catch only partly: a
   profile line stating "~$199/month entry", the 12,000 customers attributed to EvalTools'
   own page, and the 91% figure used to draw a conclusion.

So the next step is adjudication, not judge tuning. `adjudicate.html` holds the 25 items
where human and sonnet disagree. It is blind to both earlier labels and has four options.
Its output, `adjudicated.json`, overrides `labels.json` item by item. The judge is then
re-scored, and **it replaces the regex only if ASSERTED recall reaches at least 90%**. A
missed assertion is a fabrication the scorer lets through. A false alarm only costs a
re-read.

The scorer side is already in place: `evaluate_outcome(..., stance=...)` is opt-in, and
no committed report has been re-scored with it.

## Using `adjudicate.html`

Open it from disk, no network needed. It is blind by default: your round-1 label and both
judges' verdicts stay hidden until you press `R` for that item, and the notes file records
which items you peeked at. Keys `1`-`4` label and advance, arrows move, `N` jumps to the
note box, `E` exports. Progress autosaves in the browser.

Export downloads `adjudicated.json`, a plain `{item: stance}` map covering the 25 items
(and `adjudication-notes.json` if you wrote notes or peeked). Save both in this folder.
`stance.load_labels()` lays `adjudicated.json` over `labels.json` item by item and rejects
unknown items or stances; `calibrate` uses it, so re-running
`uv run python -m evals.judges.stance calibrate --model sonnet` re-scores the judge
against the adjudicated labels (zero-tool `claude -p` on the subscription, no billed API).

## Round 2 result (2026-10-07): adjudicated, and the bar is missed

`adjudicated.json` is committed. Final labels over the 94 passages: 86 REFUTED, 8
ASSERTED (round 1: 71 / 19 / 4). Of the 25 re-labelled items, 12 ASSERTED became REFUTED
(11 from the key slip, S010 on a repeat pass on 7 Oct), 4 NEUTRAL became REFUTED and 1
REFUTED became ASSERTED. The 6 Oct version (S010 still ASSERTED) is kept as
`adjudicated.round2-06oct.json`.

The sonnet judge against the adjudicated labels (`judge-sonnet-adjudicated.json`, fresh
run on 7 Oct): agreement 90%, pass/fail agreement 93%, kappa 0.50, **ASSERTED recall 2
of 8 (25%)**, precision 2 of 2. The bar was "at least 90%": missed. Five of the six
missed ASSERTED passages are called UNRELATED (the annual-billing arithmetic), one
NEUTRAL. The 6 Oct scoring of the same judge (`judge-sonnet-adjudicated-06oct-cached.json`,
recall 1 of 9) differs by one verdict per cell, so the judge is unstable as well. The judge is not used for scoring and the regex
cascade stays opt-in. Full numbers, the re-scored ranking and the limits are in
`evals/reports/stance-rescore-2026-10-06.md`. `rescored.json` holds the re-scoring output
(`uv run python -m evals.rescore --json`).
