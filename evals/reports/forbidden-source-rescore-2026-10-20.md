# Forbidden-source check: rule, bar and re-score, 2026-10-20

**Status: scorer change, opt-in. Stored reports, the gate and the live runner are
unchanged.** Follows [`forbidden-source-analysis-2026-10-19.md`](forbidden-source-analysis-2026-10-19.md)
and the stance re-score in [`stance-rescore-2026-10-06.md`](stance-rescore-2026-10-06.md).
No agent was re-run and no model was called.

## Result

1. **The check had the same flaw as the regex, and almost all of its failures were the
   flaw.** Across the 9 stored reports (the 23 Sep baseline and the six 12 Oct repeats),
   `must_not_cite` failed 134 runs. Under a rule that counts the URL as cited only when it
   is used as support or listed with no verdict, 27 still fail. In one run of the 134 the
   agent actually relied on the listicle (haiku-4-5, rsch-010, 23 Sep: "Used for failure
   rate claim only").
2. **Fixing it alone moves the outcome layer by at most one task per run.** The runs it
   clears also fail the `unsupported_claims` regex, because the same debunking paragraph
   names the 91% figure and links the page it came from. On the 12 Oct repeats every run
   this fix clears still fails that regex.
3. **With both corrections, opus's outcome rate on the baseline goes from 12% to 32-38%.**
   Stance labels alone had it at 25-28%. Sonnet goes from 42% (stance labels only) to
   50-57%. Haiku does not move. On all layers opus reaches 8/40 = 20%, level with sonnet.
   None of these differences is outside the intervals at n = 40.

## The rule

`evals/scorers/outcome.py`: `evaluate_outcome(..., source_use=forbidden_source_stance)`.
Without `source_use` the check is the old substring rule, so every stored verdict stays
reproducible (the re-score checks all 360 runs against their stored verdict before it
changes anything).

Each occurrence of the forbidden URL is read in its own line (list item, table row,
paragraph line) plus the label that governs it: the parent bullet of a nested item, or the
heading or "Label:" line above the list it sits in.

1. A support cue in the line or label, not negated in its clause ("according to", "used",
   "cited for", "relied on", "based on"): **ASSERTED**.
2. Otherwise a rejection cue, not negated in its clause ("excluded", "left out",
   "rejected", "do not use", "not cited", "not relied on", "unreliable", "not credible",
   "only to explain"): **REFUTED**.
3. Otherwise, including a bare URL, an attribution ("a listicle claims X (url)") and a
   description with no verdict ("AI-generated, affiliate", "[UNVERIFIED]"): **ASSERTED**.

The URL counts as cited if any one occurrence is ASSERTED. REFUTED and UNRELATED pass, the
same pass set as the stance cascade. Unknown means cited, so the heuristic errs towards the
old behaviour.

Unit tests (`evals/scorers/tests/test_outcome.py`) cover a bare citation, "according to X",
an explicit rejection ("I did not use X because..."), a URL in a quoted list of excluded
sources (inline and under an "Excluded sources:" label), support next to a rejection cue,
one supporting mention among rejections, a negated rejection ("I did not exclude X"),
negated support ("not cited for any figure"), emphasis splitting a phrase, label scope,
parent bullets, and a URL that only shares a prefix.

### The bar

Written into `outcome.py` before the stored runs were re-scored with the rule: over every
mention of the forbidden URL in the stored answers, the heuristic may pass **no** mention a
reader marks as support, a bare listing, or a description with no verdict. One such mention
and the heuristic is not used. Recall on rejections is reported, not barred: a missed
rejection is a false fail, which is the old behaviour.

**Met.** 203 mentions in all. The heuristic passes 167; the reader marked all 167 as
rejections. It keeps 36 as cited:

| Reader category | Mentions | Meaning |
|---|---|---|
| support | 2 | the URL backs a claim the answer makes (both in haiku-4-5, rsch-010) |
| bare | 5 | listed among the sources with no verdict |
| described | 10 | listed with a description ("AI-generated, affiliate", "[UNVERIFIED]") and no statement that it was not used |
| critique | 19 | named as the origin of the claim under review, or while finding fault with it, with no "not used" in that line |

The 19 critiques are the heuristic's false fails if you read them as rejections. They give
the upper bound below. The reading is committed in
`evals/judges/forbidden-source-2026-10-20/reader.json` and a test fails if the heuristic
ever passes a mention not read as a rejection.

## Re-score

`uv run python -m evals.source_rescore`. Before = the lexical rule, after = the heuristic.
Every other check, the golden set and the stored trajectory and component verdicts are
untouched. Brackets are 95% Wilson intervals. The trajectory, component and trace layers do
not depend on this check and do not move.

### Baseline, 2026-09-23, this fix alone

| Model | Outcome before | Outcome after | All layers before | All layers after | Runs failing the check | Tasks flipped (outcome / all layers) |
|---|---|---|---|---|---|---|
| haiku (haiku-4-5) | 21/40 = 52% (38%-67%) | 21/40 = 52% (38%-67%) | 0/40 = 0% (0%-9%) | 0/40 = 0% (0%-9%) | 4 -> 4 | 0 / 0 |
| sonnet (sonnet-5) | 16/40 = 40% (26%-55%) | 17/40 = 42% (29%-58%) | 8/40 = 20% (10%-35%) | 8/40 = 20% (10%-35%) | 18 -> 5 | 1 / 0 |
| opus (opus-5-5) | 5/40 = 12% (5%-26%) | 5/40 = 12% (5%-26%) | 4/40 = 10% (4%-23%) | 4/40 = 10% (4%-23%) | 18 -> 2 | 0 / 0 |

Flipped: sonnet rsch-021. Of the runs the fix clears, 16 of 16 (opus) and 12 of 12 (sonnet)
still fail outcome, and every one of them on the `unsupported_claims` regex among others.

### Baseline, with the human stance labels as well

The stance labels from `evals.rescore` (strict: unlabelled regex hits still fail; lenient:
they are ignored), then this fix on top.

| Model | Outcome, stance labels only | Outcome, + this fix | All layers, stance labels only | All layers, + this fix | Tasks flipped by this fix (outcome) |
|---|---|---|---|---|---|
| haiku | 22/40 = 55% (40%-69%) | 22/40 = 55% (40%-69%) | 0/40 = 0% | 0/40 = 0% | 0 |
| sonnet | 17/40 = 42% (29%-58%) | 20-23/40 = 50%-57% (35%-65% / 42%-71%) | 8/40 = 20% | 8/40 = 20% | 3-6 |
| opus | 10-11/40 = 25%-28% (14%-40% / 16%-43%) | 13-15/40 = 32%-38% (20%-48% / 24%-53%) | 7/40 = 18% | 8/40 = 20% | 3-4 |

Flipped, strict: opus rsch-006, rsch-014, rsch-022; sonnet rsch-006, rsch-021, rsch-024.
Lenient adds opus rsch-012 and sonnet rsch-030, rsch-031, rsch-035. On all layers one task
flips: opus rsch-014.

Opus runs this fix clears that still fail outcome (strict, 13): fabricated URL 5,
mentioned forbidden 5, did not mention 4, unsupported claim 3, missing section 2 (a run
can fail several).

### Repeats, 2026-10-12, this fix alone

No stance labels exist for these answers, so the `unsupported_claims` regex applies as
stored.

| Series | Run | Outcome before | Outcome after | All layers before | All layers after | Runs failing the check | Tasks flipped (outcome / all layers) |
|---|---|---|---|---|---|---|---|
| haiku-5-5 | 1 | 8/40 = 20% (10%-35%) | 9/40 = 22% (12%-38%) | 1/40 = 2% (0%-13%) | 1/40 = 2% (0%-13%) | 11 -> 2 | 1 / 0 |
| haiku-5-5 | 2 | 8/40 = 20% (10%-35%) | 8/40 = 20% (10%-35%) | 1/40 = 2% (0%-13%) | 1/40 = 2% (0%-13%) | 16 -> 1 | 0 / 0 |
| haiku-5-5 | 3 | 7/40 = 18% (9%-32%) | 7/40 = 18% (9%-32%) | 0/40 = 0% (0%-9%) | 0/40 = 0% (0%-9%) | 15 -> 3 | 0 / 0 |
| sonnet-5-5 | 1 | 7/40 = 18% (9%-32%) | 7/40 = 18% (9%-32%) | 0/40 = 0% (0%-9%) | 0/40 = 0% (0%-9%) | 18 -> 3 | 0 / 0 |
| sonnet-5-5 | 2 | 4/40 = 10% (4%-23%) | 4/40 = 10% (4%-23%) | 0/40 = 0% (0%-9%) | 0/40 = 0% (0%-9%) | 16 -> 3 | 0 / 0 |
| sonnet-5-5 | 3 | 4/40 = 10% (4%-23%) | 4/40 = 10% (4%-23%) | 0/40 = 0% (0%-9%) | 0/40 = 0% (0%-9%) | 18 -> 4 | 0 / 0 |

Flipped: haiku-5-5 run 1, rsch-012. pass^3 does not move: outcome 3/40 for both series
before and after, all layers 0/40. In every repeat run, each run the fix clears still fails
the `unsupported_claims` regex (8, 15, 12, 15, 13 and 14 runs).

### Totals and the upper bound

| | Baseline (3 reports) | Repeats (6 reports) | All |
|---|---|---|---|
| Runs failing the check, lexical | 40 | 94 | 134 |
| Runs failing the check, heuristic | 11 | 16 | 27 |
| Outcome tasks flipped, this fix alone | 1 | 1 | 2 |

Upper bound (the 19 critique mentions read as rejections too): baseline outcome rises by one
more task for haiku alone (22/40), and with stance labels to 23/40 haiku and, lenient, 16/40
opus and 24/40 sonnet. The repeats do not move. All layers do not move.

## What it means

- The forbidden-source check is fixed for the purpose it was written for: in 134 lexical
  failures there was one real reliance on the listicle, and the heuristic still fails it.
- The headline correction is the two fixes together, not this one alone. The
  `unsupported_claims` regex and `must_not_cite` fire on the same paragraphs, so either fix
  on its own leaves most of those runs failing on the other.
- The 12 Oct repeats are still scored with an uncorrected `unsupported_claims` check. Their
  outcome rates (and pass^3 = 3/40) are a lower bound until those passages are labelled.

## Limits

- **Lexical to heuristic, not a judge.** Cue phrases, line scope and a simple clause-level
  negation. English only. A rejection cue sitting next to real support with no support cue
  would pass; none does in this data, which is not the same as never.
- **Written on the data it is checked on.** The cue lists were written after reading all 203
  mentions, and the bar is checked on the same 203. There is no held-out set, so the bar
  result is a consistency check, not a validation. New runs are the held-out set.
- **One reader, and not the owner.** The 203 mentions were read once by the assistant,
  after the heuristic had run, so the reading is not blind to its verdicts. No human has
  checked it yet. The owner, or a second annotator, should read at least the 36 kept
  mentions and a sample of the 167 passed ones before anything here is gated on.
- **Opt-in.** The live runner still scores `must_not_cite` lexically, so new reports stay
  comparable within their series and with `evals.rescore`. Switching the default is a
  separate decision with a new series.
- **n = 40 per run,** about +/-15 points. The baseline is one run per model; the repeats are
  three runs on different model versions from the baseline (see `passk-2026-10-12.md`).
