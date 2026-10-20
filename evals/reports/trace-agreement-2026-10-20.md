# Trace checks against 30 hand labels, 2026-10-20

**Status: none of the three trace checks meets its bar.** The trace layer stays what it
was: a diagnostic, reported and never gated. This is the calibration that
[`trace-scores-2026-10-12.md`](trace-scores-2026-10-12.md) said was missing.

## Method

- **Sample.** 30 traces from the 23 Sep baseline, 10 per model, stratified so that half
  are traces the scorer failed on at least one check and half it passed on all. Shuffled
  with a fixed seed and renamed T-01 to T-30. The key is committed
  (`evals/judges/trace-labels-2026-10-12/key.json`); the labelling page is not, because it
  shows the agent's private context files.
- **Labels.** One annotator, the owner, blind to model and to every scorer verdict, three
  questions per trace: tool use ok/bad, stop right/early/overran, answer
  grounded/ungrounded. Completed 14 Oct. Committed as
  `evals/judges/trace-labels-2026-10-12/labels.json`, in the format the labelling page
  exports and `compare` reads, so no conversion was needed beyond a key-order tidy.
- **Bars,** fixed in code on 12 Oct before any label existed: per check, agreement
  >= 80% and recall of the human-flagged failures >= 80%.
- **Run:** `uv run python -m evals.judges.trace_labels compare --labels
  evals/judges/trace-labels-2026-10-12/labels.json`, from a checkout with the gitignored
  context files present, so `read_context` replays as it did for the 12 Oct trace scores.
  No model was called.

A check that does not apply to a trace (the scorer returns no verdict) leaves that trace
out of that check, so n differs per check.

## Result

| Check | n | Agreement | kappa | Human failures caught | False alarms | Meets bar |
|---|---|---|---|---|---|---|
| Tool choice | 30 | 21/30 = 70% (52%-83%) | 0.00 | 1/5 | 5 | NO |
| Stopping | 23 | 14/23 = 61% (41%-78%) | 0.22 | 3/3 | 8 | NO |
| Grounding | 29 | 22/29 = 76% (58%-88%) | 0.00 | 0/0 | 7 | NO |

Brackets are 95% Wilson intervals.

Confusion counts (human -> scorer):

| Check | Agree | Disagree |
|---|---|---|
| Tool choice | ok -> ok 20, bad -> bad 1 | ok -> bad 5, bad -> ok 4 |
| Stopping | right -> right 12, overran -> overran 2 | right -> overran 8, early -> overran 1 |
| Grounding | grounded -> grounded 22 | grounded -> ungrounded 7 |

Kappa is 0.00 for tool choice and grounding. For grounding that is forced: the human
called all 30 traces grounded, so there is only one human class and no agreement beyond
chance is possible. For tool choice it is a real zero: 70% observed agreement is exactly
what two raters with these base rates would reach by chance.

"Caught" for stopping counts any failing scorer verdict on a human-flagged failure. One of
the three (T-07) is caught in the wrong direction: the human says it stopped early, the
scorer says it overran. Counting direction, the scorer gets 2 of 3. Two more human-flagged
stopping failures (T-24 overran, T-30 early) are outside n because the scorer gives no
stopping verdict on them, so the human flagged 5 stopping failures in 30 traces and the
scorer has a verdict on 3.

## Disagreements

The scorer's reason is quoted from its failure list. The human gave no note on any of these.

**Tool choice** (9)

- T-03 (sonnet, rsch-010): human bad, scorer ok. The scorer marks all 15 steps ok.
- T-06 (sonnet, rsch-033): human ok, scorer bad. Step 9 fetched a URL no earlier step surfaced.
- T-07 (opus, rsch-017): human ok, scorer bad. Steps 9, 10 and 11 fetched URLs no earlier step surfaced.
- T-09 (opus, rsch-030): human ok, scorer bad. Steps 9 to 12 (and later) fetched URLs no earlier step surfaced.
- T-12 (opus, rsch-006): human bad, scorer ok. The scorer marks all 14 steps ok.
- T-15 (haiku, rsch-018): human bad, scorer ok. The scorer marks all 9 steps ok.
- T-20 (haiku, rsch-001): human bad, scorer ok. The scorer marks all 6 steps ok.
- T-26 (sonnet, rsch-006): human ok, scorer bad. Step 13 fetched a URL no earlier step surfaced.
- T-30 (haiku, rsch-029): human ok, scorer bad. Steps 6, 8, 19 and 23 fetched URLs no earlier step surfaced.

**Stopping** (9)

- T-03 (sonnet, rsch-010): human right, scorer overran. 7 calls after it had every required source (step 8); slack 2.
- T-06 (sonnet, rsch-033): human right, scorer overran. 7 calls after step 7; slack 2.
- T-07 (opus, rsch-017): human early, scorer overran. 6 calls after step 5; slack 2. Opposite readings of the same trace.
- T-09 (opus, rsch-030): human right, scorer overran. 14 calls after step 8; slack 3.
- T-18 (opus, rsch-008): human right, scorer overran. 3 calls after step 7; slack 2.
- T-19 (haiku, rsch-024): human right, scorer overran. 35 calls after step 10 (45 steps in all); slack 2.
- T-26 (sonnet, rsch-006): human right, scorer overran. 7 calls after step 8; slack 3.
- T-28 (sonnet, rsch-016): human right, scorer overran. 2 calls after step 2; slack 1.
- T-29 (haiku, rsch-008): human right, scorer overran. 10 calls after step 8; slack 2.

**Grounding** (7)

- T-03 (sonnet, rsch-010): human grounded, scorer ungrounded. Figures 90% and 89% appear in no tool result of the run.
- T-07 (opus, rsch-017): cited URL `https://evaltools.io/blog`, which no tool returned.
- T-09 (opus, rsch-030): cited `https://evaltools.io`; money figures 21600, 17280 and 22 in no tool result.
- T-14 (opus, rsch-014): money figure 1440 in no tool result.
- T-17 (haiku, rsch-039): cited `https://eur-lex.europa.eu/`, which no tool returned; figure 26%.
- T-20 (haiku, rsch-001): figure 89% in no tool result.
- T-29 (haiku, rsch-008): figures marked as derived (32%, 25.5%, 32.1%) do not reproduce; money figure 1.6 in no tool result.

## The labeller's notes

One note in 30 traces, on T-02 (sonnet, rsch-040; all three checks agree), verbatim:

> It gave more info thar what was asked which is not completely bad

## What it means for the trace layer

1. **Tool choice measures something the owner does not count as bad.** Every one of the
   scorer's five false alarms is the same rule: a fetch of a URL that no earlier step
   surfaced. The owner passed all five. In the other direction the scorer catches 1 of the
   5 traces she called bad. Four of those five fetched the tier-4 listicle, but so did six
   traces she called ok, so that is not her rule either, and she left no note. The two are
   not measuring the same thing, which is what kappa 0.00 says.
2. **Stopping is too strict for the owner's reading.** 8 of the 11 traces the scorer calls
   overrun she calls right, including one 45-step trace on a standard task (T-19). The
   slacks (1, 2, 3 calls) are a policy line the owner does not hold. It does flag every
   failure she flagged that it has a verdict on, one of them in the wrong direction.
3. **Grounding flags things the owner accepts.** 7 false alarms and no human failures, so
   on this sample its precision on "ungrounded" is 0 of 7. Six of the seven include a
   figure no tool returned in the run; three include a cited URL no tool returned, two of
   them a bare domain. The README already said most grounding failures are correct
   arithmetic, not fabrication; this is the hand-label version of that.
4. **Nothing is re-tuned here.** Loosening the slack or the grounding rule until it agrees
   with these 30 labels would fit the check to its own test set. A change needs a fresh
   blind sample to be measured on.
5. **The trace numbers stay out of any claim about the agent.** The README already says
   the trace layer is uncalibrated; it is now measured and misses. Quote the per-check
   rates in `trace-scores-2026-10-12.md` as scorer output, not as how often the agent
   chose tools well, stopped well or stayed grounded.

## Limits

- **One annotator, 30 traces, one pass.** No second rater and no adjudication. The stance
  labels had 12 slips in 19 positives on the first pass, so a single pass is not ground
  truth.
- **Stratified, not random.** Half the sample is scorer-flagged traces, so flagged traces
  are over-represented and the agreement figures are not population rates.
- **Few positives.** 5 human tool failures, 5 stopping failures (3 inside n), 0 grounding
  failures. One label more or less moves recall by 20 to 33 points.
- **Baseline runs only, replayed.** All 30 traces are from 23 Sep, replayed against the
  fixture web with context files rebuilt as of the 6 Aug pin. Nothing from the 12 Oct
  repeats is labelled.
