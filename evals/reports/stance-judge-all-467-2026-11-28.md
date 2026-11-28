# Stance judge over all 467 regex hits, 2026-11-27 run, written up 2026-11-28

The sonnet stance judge read every one of the 467 passages the `unsupported_claims` regex hits
across the nine repeat runs, and called **none of them ASSERTED**. That number cannot be read as
"the repeats are clean": on the 48 passages Ana labelled, the same judge caught **0 of 2** real
assertions. The bar (ASSERTED recall of at least 90%) is missed again, the regex stays, and
nothing is re-scored here. A re-score, if there is ever one, is Ana's decision.

Why this ran: the four-option re-read (PR 13, merged 26 Nov) left 2 ASSERTED of 48 (sonnet 1 of
16, opus 1 of 16, haiku 0 of 16), under the 10% rule in
`../judges/stance-repeats-2026-11-07/README.md`, which sends the next step to the judge over all
467. The judge run itself happened in the night of 27 Nov and was never committed; this report
reads those verdict files, after checking them (see "What was checked").

## Stated before the numbers

**Two positives cannot qualify the judge.** The adjudicated labels hold 2 ASSERTED passages
(R009, R013). Catching both would be 2 of 2, whose 95% Wilson lower bound is 34%, so no result on
this sample could show recall of 90%. The most it can do is fail the bar, or leave it open.

## Fixed beforehand (the queued task, 26 Nov)

1. Judge `claude-sonnet-5-5`, effort low, instructions byte-identical to October (the
   `INSTRUCTIONS` block in `stance.py` hashes the same at `7e5c5c8`, 6 Oct, and now), cache
   bypassed (`--fresh`), `claude -p` with every tool disabled, subscription only. 467 calls in ten
   chunks (47 x 7, 46 x 3). Every chunk file records `claude-sonnet-5-5` as the model Claude Code
   billed.
2. Set built with `stance_repeats build --all` (467 hits, 467 distinct, none already covered by
   a baseline label).
3. Scored on the 48 labelled passages against `adjudicated.json`; bar unchanged.
4. Per-model and per-run shares on the other 419, with Wilson intervals. No re-score, regex
   unchanged.

## Scored on the 48 labelled passages

| Measure | Result |
|---|---|
| Agreement with the adjudicated labels | 43 of 48 (89.6%) |
| Pass/fail agreement (REFUTED or UNRELATED pass; ASSERTED or NEUTRAL fail) | 46 of 48 (95.8%) |
| Cohen's kappa | 0.14 |
| **ASSERTED recall** | **0 of 2** (95% Wilson 0% to 66%) |
| REFUTED labels called a failure | 0 of 46 |

The two real assertions: **R009** called UNRELATED (the judge reads the 199 as annual-billing
arithmetic on the EUR 249 list price), **R013** called REFUTED (the 12,000-customer figure quoted
"only to contrast it" with the vendor's site). The other three disagreements are REFUTED labels
the judge called UNRELATED (R010, R029, R042); they pass either way.

For comparison, the 24 Nov runs on these same labels gave 44 of 48 and 43 of 48, recall 0 of 2
both times. Kappa is low because with two positives and no NEUTRAL or UNRELATED labels it has
almost nothing to separate. The one-way error from 24 Nov holds: the judge passes what the labels
fail, and has never failed what the labels pass.

## What the judge says about the other 419

Verdicts: **0 ASSERTED**, 378 REFUTED, 36 UNRELATED, 5 NEUTRAL. Under the scorer's rule the
judge would fail 5 and pass 414.

| Model | Passages | ASSERTED | REFUTED | UNRELATED | NEUTRAL | ASSERTED share (95% Wilson) |
|---|---|---|---|---|---|---|
| haiku-5-5 | 106 | 0 | 97 | 8 | 1 | 0% (0% to 3.5%) |
| sonnet-5-5 | 132 | 0 | 115 | 15 | 2 | 0% (0% to 2.8%) |
| opus-5-5 | 181 | 0 | 166 | 13 | 2 | 0% (0% to 2.1%) |
| all | 419 | 0 | 378 | 36 | 5 | 0% (0% to 0.9%) |

Per run (the other 419; three runs per model):

| Run | Model | Passages | ASSERTED | NEUTRAL | REFUTED | UNRELATED | Wilson 95% upper |
|---|---|---|---|---|---|---|---|
| haiku 12 Oct 14:40 | haiku-5-5 | 38 | 0 | 0 | 35 | 3 | 9.2% |
| haiku 12 Oct 14:50 | haiku-5-5 | 36 | 0 | 1 | 31 | 4 | 9.6% |
| haiku 12 Oct 15:00 | haiku-5-5 | 32 | 0 | 0 | 31 | 1 | 10.7% |
| sonnet 12 Oct 14:46 | sonnet-5-5 | 45 | 0 | 0 | 39 | 6 | 7.9% |
| sonnet 12 Oct 14:56 | sonnet-5-5 | 44 | 0 | 1 | 38 | 5 | 8.0% |
| sonnet 12 Oct 15:05 | sonnet-5-5 | 43 | 0 | 1 | 38 | 4 | 8.2% |
| opus 2 Nov 21:20 | opus-5-5 | 57 | 0 | 0 | 52 | 5 | 6.3% |
| opus 2 Nov 21:25 | opus-5-5 | 63 | 0 | 0 | 58 | 5 | 5.8% |
| opus 2 Nov 21:31 | opus-5-5 | 61 | 0 | 2 | 56 | 3 | 5.9% |

Including the 48 labelled passages, all 467 give 0 ASSERTED (0% to 0.8%); per-run counts for the
full set are in `summary.json`.

## Why zero ASSERTED is not a finding about the repeats

- **The judge's zero is what it would say either way.** It missed both known assertions. The
  sample's own ASSERTED share is 2 of 48 (4.2%, Wilson 1% to 14%); if that held over the other
  419, there would be roughly 4 to 59 assertions in them, and the judge found none. Two positives
  say nothing precise, but they also do not say "none".
- **Its blind spot is concentrated in one claim.** 37 of the 40 UNRELATED verdicts are on the
  "EvalTools pricing starts at $199/month" claim, the category where the judge turned a real
  assertion (R009) into UNRELATED, and which is behind five of its six October misses. Of those
  37, 33 are passages nobody has labelled. UNRELATED passes the outcome scorer, so this is the
  one place an unlabelled assertion could be hiding behind a pass.
- **The judge contradicts itself in places.** Of the five NEUTRAL verdicts, R146's reason reads
  as REFUTED (the figure is flagged as unsupported without being relied on), and R183's reason
  is about the source page ("Do not cite"), not the claim. Same kind of fault as the
  UNRELATED/REFUTED flip on 24 Nov. Nothing here is corrected.
- **Stability across chunks:** the stance mix is roughly constant (REFUTED 38 to 45 of each
  chunk); chunk 9 has the most UNRELATED (8 of 46). Each passage was judged once; this run says
  nothing about run-to-run flips beyond the 24 Nov pair.

## What the judge cannot be used for

It is not calibrated and is not swapped in. The regex stays as it is, `unsupported_claims` on
the repeat runs is unchanged, and no run's score moves. What this adds to the record: **the
judge does not turn up any assertion in the repeats, and it has not shown it could.**

## For Ana to decide

1. **No re-score** (recommended). The judge has not met the bar and cannot on this sample.
2. If you want to know whether the repeats hide assertions, the cheapest real step is not another
   judge run: it is reading the **33 unlabelled UNRELATED "$199/month" passages** yourself, on a
   four-option sheet (`stance_repeats build --all` makes the passages; I did not build a sheet
   or label anything). Thirty-three passages, one claim, and the judge's one demonstrated blind
   spot. The result would also add positives to the sample, which is what the bar needs.
3. The W7 post told readers this step was "next, not run yet". That sentence is now stale; this
   report is the update. No post has been drafted for it; "the judge found none and also missed
   the two we know about" is the honest line if a post is wanted.

## What was checked before reading the verdicts

- The 27 Nov run's `items.jsonl` and `key.json` are **byte-identical** to a fresh
  `stance_repeats build --all` on `origin/main` (`2f3f6c6`).
- 10 chunk files, 467 verdicts, 467 distinct item ids, each file records
  `models_used = ["claude-sonnet-5-5"]`, `effort = low`, `fresh = true`.
- `INSTRUCTIONS` hash unchanged since 6 Oct (`7e5c5c8`); `stance.py` has no diff against
  `origin/main`.
- `pytest evals/judges/tests`: 42 passed, including the new `test_stance_all.py`.
- The 48 labelled passages are matched into the 467 set on exact (claim, passage) text; all 48
  were found.

## Limits

- Two positives (see above). One annotator, who also set the bar.
- One judge call per passage, no repeat; the 24 Nov pair is the only stability figure.
- `claude -p` at low effort run from a checkout of this repository, as in October: not a bare
  model call, Claude Code's own context travels with it.
- I did not re-run the 467 calls this pass; the verdicts come from the 27 Nov run (judge files
  timestamped 27 Nov 03:01 to 03:48, in the sweep worktree `agent-reliability-lab-sweep-1127`,
  uncommitted until now). The claim that those calls were made as specified rests on the files'
  recorded model/effort/fresh fields and on the matching build, not on having watched them.

## Reproduce

    uv run python -m evals.judges.stance_repeats build --all --out <dir under /Volumes/Backup>
    uv run python -m evals.judges.stance_all run --model claude-sonnet-5-5   # ten chunks, ~470 calls
    uv run python -m evals.judges.stance_all analyse                         # writes summary.json

Files: `../judges/stance_all.py`, `../judges/tests/test_stance_all.py`,
`../judges/stance-all-2026-11-27/` (`items.jsonl`, `key.json`, ten `judge-claude-sonnet-5-5-runNN.json`,
`summary.json`). The folder name carries the date the judge ran; `label.html`, which `build --all`
also writes, is not committed.
