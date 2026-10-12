# Trace-level scores, baseline runs, 2026-10-12

**Status: second pass, still not calibrated, still not gated.** Nothing here feeds
`all_layers` or `evals/gate.py`. Supersedes [`trace-scores-2026-10-08.md`](trace-scores-2026-10-08.md),
whose grounding column should not be quoted (see "What changed").

## Why

The outcome layer says whether the answer was right. It does not say which step went
wrong, so the trace is scored on its own, one question per check:

1. **Tool choice.** For every step: right tool here? Verdict per step: ok, wrong
   (unsourced fetch, failed call, unknown or forbidden tool, context read after
   research) or redundant (identical call, page already fetched).
2. **Stopping.** Did it stop when it had enough? "Enough" is the first step after which
   every `must_cite` source was in hand: surfaced, for `quick` tasks; fetched, otherwise.
   Calls after that point beyond a slack (quick 1, standard 2, deep 3) are an overrun.
   Answering before it is an early stop. A turn-cap ending is never a clean stop.
3. **Grounding.** Does the final text match what the tools returned? Every cited URL and
   every figure (percentages, currency amounts) must appear in a tool result from the
   same run, or be marked as derived and reproduce from numbers that do.

Code: `evals/scorers/trace.py`, tests in `evals/scorers/tests/test_trace.py`. New runs
store the result per task under `trace_scores` and per run under `summary.trace`.

## What changed since 8 October

The first pass listed four next steps. Three are done here, one is partly done.

1. **Context restored for the replay.** The first pass ran without the private context
   files, so any figure the agent took from its own context counted as ungrounded. They
   are now present. The vendored copies are rebuilt from the orchestrator repo's git
   history as of the 2026-08-06 pin (orchestrator repo commit `b19a78e`), because the files the runs
   actually read were not kept. They are gitignored, used only to replay stored runs, and
   `v1` is unchanged. Treat `read_context` as approximate.
2. **Derived figures are checked, not just flagged.** A figure no tool returned is
   accepted only if the answer marks it as derived (my calculation, works out to,
   implied, an equation) *and* plain arithmetic reproduces it from numbers the run
   grounded, within one line either side. A marked figure that does not reproduce fails.
   An unmarked one stays ungrounded. The strict reading is kept alongside.
3. **Attribution, as a diagnostic.** A figure in a sentence that cites a URL should be in
   what that URL returned. It does not gate (see below).
4. **Raw transcripts.** The runner already wrote them; they were gitignored and the
   2026-09-23 set was lost. `evals/keep_runs.py` now copies them out of the repo, and
   this script reads them in preference to replaying. For this baseline every report
   still went through replay, which is the only route left.

## Method

Replay: the fixture web is deterministic, so each `web_search` and `web_fetch` is
replayed against the frozen corpus with the same functions the MCP server uses. Steps that
errored in the real run keep an empty result: their text was an error message, never
evidence.

```
uv run python -m evals.trace_rescore                 # replay, or raw if kept
uv run python -m evals.trace_rescore --runs DIR      # where the transcripts are
```

## Results

Context replay: private context files present, read_context replayed

| Model | Tool choice (runs) | Mean step score | Stopping | Grounding, strict | Grounding, derivations checked | Outcome pass, grounding fail |
|---|---|---|---|---|---|---|
| haiku | 27/40 = 68% (52%-80%) | 98% | 11/30 = 37% (22%-54%) | 29/37 = 78% (63%-89%) | 29/37 = 78% (63%-89%) | 3 |
| sonnet | 30/40 = 75% (60%-86%) | 97% | 16/30 = 53% (36%-70%) | 31/39 = 79% (64%-89%) | 32/39 = 82% (67%-91%) | 0 |
| opus | 32/40 = 80% (65%-90%) | 96% | 15/30 = 50% (33%-67%) | 26/40 = 65% (50%-78%) | 29/40 = 72% (57%-84%) | 0 |

| Model | Step verdicts | Overrun runs (calls after enough) | Early stops | Turn-cap | Ungrounded URLs |
|---|---|---|---|---|---|
| haiku | ok 585, wrong 15, redundant 3 | 16 (2, 2, 3, 3, 3, 6, 9, 10, 11, 11, 14, 15, 15, 16, 34, 35) | 2 | 1 | 1 |
| sonnet | ok 373, wrong 21, redundant 0 | 14 (2, 2, 2, 2, 3, 3, 7, 7, 7, 7, 10, 11, 14, 17) | 0 | 0 | 8 |
| opus | ok 325, wrong 27, redundant 0 | 15 (2, 2, 2, 3, 4, 4, 5, 5, 6, 6, 6, 6, 7, 14, 14) | 0 | 0 | 8 |

| Model | Tool output from | Derived figures verified | Marked derived, does not reproduce | Sentences citing a URL where the figure is not in it | Figures with no URL to check |
|---|---|---|---|---|---|
| haiku | 40 replay | 0 | 3 | 0 | 199 |
| sonnet | 40 replay | 1 | 0 | 1 | 265 |
| opus | 40 replay | 7 | 0 | 0 | 414 |

Non-ok step reasons:

- **haiku**: fetched a URL no earlier step surfaced (15); identical call repeated (3)
- **sonnet**: fetched a URL no earlier step surfaced (21)
- **opus**: fetched a URL no earlier step surfaced (27)

Marked as derived but not reproducible:

- **haiku**: 32% x1, 25.5% x1, 32.1% x1
- **sonnet**: none
- **opus**: none

Most frequent ungrounded figures (after derivations):

- **haiku**: 89% x2, 1.6 (money) x1, 32% x1, 25.5% x1, 32.1% x1, 270 (money) x1, 199 (money) x1, 150 (money) x1
- **sonnet**: 90% x1, 89% x1, 270 (money) x1, 275 (money) x1, 21600 (money) x1, 180 (money) x1
- **opus**: 22 (money) x2, 1.3 (money) x1, 2390 (money) x1, 3300 (money) x1, 280 (money) x1, 1440 (money) x1, 21600 (money) x1, 17280 (money) x1

Brackets are 95% Wilson intervals. Stopping applies to the 30 tasks with a `must_cite`;
grounding to runs whose answer contains at least one URL or figure.

## What it shows, and what it does not

- **Tool choice and stopping are unchanged** from the first pass: neither depends on the
  context files or on how figures are read. Opus is best on tool choice, haiku worst on
  stopping, and the intervals overlap, so no model is named best.
- **The grounding gap narrowed, it did not close.** Restoring the context moved the strict
  rate from 73/72/57% to 78/79/65% (haiku/sonnet/opus). Checking derivations moved opus up by
  three runs (72%), sonnet by one (82%) and haiku by none. Opus is still lowest,
  but the intervals overlap fully.
- **One real catch.** Haiku marks three figures in one answer as an implied CAGR (32%,
  25.5%, 32.1%, task rsch-008) that do not reproduce from the source's own numbers:
  $310M in 2025 to $2.4bn-$4.1bn in 2030 is about 51% to 68% a year. That is a wrong
  calculation, presented as one.
- **Most of what remains is not yet sorted.** The ungrounded figures left are a mix of
  arithmetic the answer does not label (EUR 1,800 x 12 = 21,600; 100% less 11% = 89%),
  assumptions with no source (an exchange rate, a burn estimate), and a few I have not
  classified. This check cannot tell the first two apart, so it is still not a fabrication
  detector. Hand labels are the next step.
- **Ungrounded URLs are the strongest signal, and are unchanged.** 8 each for sonnet and
  opus: corpus URLs cited without being returned by any tool in that run. The outcome
  layer passes these, because the URL is valid somewhere in the corpus.
- **Attribution found nothing, and cannot yet.** One flag in 120 runs, and it is a false
  positive: the answer repeats the listicle's "$40M ARR" claim, unquoted, beside the page
  that contradicts it. Before the quotation rule and sentence scoping, most of the first five flags were of that kind or an artefact of scope.
  That is the debunk-versus-cite flaw the outcome regex has, in another place. And 199,
  265 and 414 figures (haiku, sonnet, opus) sit in sentences that cite no URL, so they were
  never checked. "No misattribution found" is not "no misattribution".

## Known limits

- One annotator, no hand labels for any of the three checks. The overrun slack and the
  derivation rules are policy, tuned on these 120 runs, so the grounding rates here are
  not out-of-sample.
- The derivation check is plain arithmetic within a line either side. It misses a figure
  whose operands sit further away, and a wider pool was tried and dropped because it
  verified two wrong CAGRs by coincidence.
- The replayed `read_context` is a reconstruction (see "What changed").

## Next

1. Label 30 traces by hand (tool choice, stopping, grounding) and calibrate the slack
   and the derivation rules against them before any of this is gated.
2. Attribution needs a stance signal (is the figure asserted or quoted to be refuted?)
   before it can say anything. Reuse the stance judge once it passes its bar.
3. Run `evals.keep_runs` after every real run, and re-score the next baseline from the
   raw transcripts instead of replaying.
