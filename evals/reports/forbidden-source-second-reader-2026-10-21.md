# Forbidden-source check: a second, blind reading, 2026-10-21

**Status: the bar holds on a second reading. One small rule bug fixed (no stored number
moves). The heuristic is stricter than a reader, never looser.** Follows
[`forbidden-source-rescore-2026-10-20.md`](forbidden-source-rescore-2026-10-20.md), whose
203 mentions had been read once, by the author of the rule. No agent was re-run and no
model was called.

## Result

1. **The heuristic passes nothing the second reader would count as cited.** It passes 167
   of the 203 mentions. The second reader labelled all 167 as rejections. Of the 16
   mentions the second reader marked as support or as a listing with no verdict, the
   heuristic keeps all 16 as cited. The bar in `outcome.py` holds on both readings.
2. **Every disagreement goes the same way.** The heuristic keeps 36 mentions as cited. The
   second reader would pass 18 of them as rejections and calls 2 more "origin, no verdict".
   In all 20 the heuristic is the stricter of the two: these are false fails, never false
   passes.
3. **Agreement, heuristic against second reader: 185/203 = 91.1%, Cohen's kappa 0.62**
   (the 2 "origin, no verdict" counted as cited), or 183/203 = 90.1%, kappa 0.57 (counted
   as passed). Kappa is low next to the raw agreement because 82% of mentions are
   rejections, and all of the disagreement sits in the remaining 18%.
4. **Both readings agree that exactly one run relied on the listicle** (haiku-4-5,
   rsch-010, 23 Sep: two mentions, one of them "Used for failure rate claim only").
5. **One rule bug, found through a disagreement and fixed.** "no" was not treated as a
   negator, so "there is no reason to exclude <url>" would read as an exclusion and pass.
   No stored mention has that form. The fix changes no verdict on the 203 and no number in
   the re-score. See [The bug](#the-bug).

## Method

1. **Extraction, independent of the rule.** Every line of a stored answer holding the full
   forbidden URL, across the 23 Sep baseline (3 reports) and the 12 Oct repeats (6
   reports): 203 lines, the same unit and the same count the rule reports. Each was
   written to a scratch file (not committed) with the three lines either side and the
   nearest heading, pseudonymised (business, assistant and owner names replaced, the
   account email redacted).
2. **Blind labelling.** Each mention was given one of four labels before the rule's
   verdicts or `reader.json` were opened:

   | Label | Meaning |
   |---|---|
   | SUPPORT | the URL backs a claim the answer makes, hedged or not |
   | REJECT | says it was not used, excluded, not citable, or cited only to flag or trace it; or judges it unreliable, not credible, weak or inaccurate. Read in the line, its bullet block, and the 3 sentences either side. A verdict on the claim the page is the sole origin of counts ("don't use the 91% figure") |
   | UNMARKED | listed (a Sources entry or an inline pointer) with no verdict. Provenance tags alone ("AI-generated", "affiliate", "unsourced", "[UNVERIFIED]") are not a verdict. A Sources entry is read on its own line and its list label: a "source to avoid" line in another section does not rescue it |
   | OTHER | named as the origin of the claim under review, or criticised, with no verdict anywhere in that context |

   The criteria were fixed after reading the first 50 mentions once and before reading the
   rest. One of those 50 changed label when the criteria were fixed (#36, REJECT to
   UNMARKED). Four (#3, #5, #7, #48) were settled by reading the whole answer, still
   before the comparison.
3. **Comparison.** SUPPORT and UNMARKED map to cited (the rule's ASSERTED), REJECT to not
   cited (REFUTED). OTHER is reported both ways. Labels are committed in
   `evals/judges/forbidden-source-2026-10-20/second-reader.json`, keys and categories only.

**Not blind to everything.** The second reader had read the 2026-10-20 report first, so
it knew the aggregate split (167 passed, 36 kept) and the first reader's category names.
It did not know which mention got which verdict. It is also the assistant again, not the
owner. See [Limits](#limits).

## Numbers

### Second reader against the heuristic

| Second reader | Heuristic REFUTED (passed) | Heuristic ASSERTED (kept as cited) | Total |
|---|---|---|---|
| REJECT | 167 | 18 | 185 |
| SUPPORT | 0 | 2 | 2 |
| UNMARKED | 0 | 14 | 14 |
| OTHER | 0 | 2 | 2 |
| **Total** | **167** | **36** | **203** |

The recount matches the report: 203 mentions, 36 kept.

| OTHER counted as | Agreement | Expected by chance | Cohen's kappa |
|---|---|---|---|
| cited | 185/203 = 91.1% | 76.5% | 0.62 |
| passed | 183/203 = 90.1% | 77.2% | 0.57 |

### Second reader against the first reader

The first reader's categories map onto the second's as rejection to REJECT, support to
SUPPORT, bare and described to UNMARKED, critique to OTHER. On that mapping the readers
agree on 185/203 (kappa 0.64). Where they differ:

- 17 of the first reader's 19 "critique" mentions are REJECT here. The first reader read
  the line. The second also read the summary and the neighbouring bullets, where the
  verdict usually sits.
- 1 "described" mention is REJECT here (#6, "Comparison Site with Inaccurate Claim").
- Agreed outright: all 167 rejections, both supports, all 5 bare listings, 9 of 10
  described.

The first reader's binary verdicts equal the heuristic's on every mention (its bar test
enforces that), so the agreement figures above are the same against either.

## Disagreements

Ids are the mention numbers in the second reader's extraction. Series: `b-` the 23 Sep
baseline (haiku-4-5, sonnet-5, opus-5-5); `r-haiku1..3` and `r-sonnet1..3` the 12 Oct
repeats (haiku-5-5, sonnet-5-5) in run order. The heuristic keeps all 20 as cited.

| # | Mention | Second reader | Why |
|---|---|---|---|
| 3 | b-haiku rsch-012 L8 | OTHER | Names the page as sole origin and notes "no underlying source cited", no verdict. The rule's support cue was "cited for", which is the listicle citing nothing: the bug below. Verdict unchanged by the fix |
| 5 | b-haiku rsch-014 L15 | OTHER | "[Source: url]" for the $199 claim under check. The next bullet lists the site's problems, no verdict word |
| 6 | b-haiku rsch-014 L50 | REJECT | Sources entry "Comparison Site with Inaccurate Claim". "Inaccurate" is not a rejection cue. Judgement call |
| 7 | b-haiku rsch-018 L6 | REJECT | Sole origin. Summary two lines up: "not a credible number to repeat" |
| 9 | b-opus rsch-002 L4 | REJECT | Summary: "Don't use the 91% figure" |
| 35 | b-sonnet rsch-002 L6 | REJECT | Summary recommends dropping the stat "rather than citing it" |
| 44 | b-sonnet rsch-012 L4 | REJECT | Summary: the figure "is not credible" |
| 50 | b-sonnet rsch-018 L7 | REJECT | A "same source" pointer. The bullet above calls the page Tier 4, not citable |
| 60 | r-haiku1 rsch-002 L4 | REJECT | Summary: "should not go in your proposal" |
| 68 | r-haiku1 rsch-018 L6 | REJECT | "single weak source". Next bullet: "not a citable source" |
| 108 | r-haiku3 rsch-018 L4 | REJECT | Summary: "don't repeat" the claim |
| 119 | r-sonnet1 rsch-002 L4 | REJECT | "one weak source". Summary: "Don't repeat the 91% figure" |
| 128 | r-sonnet1 rsch-012 L4 | REJECT | "only source is weak ... lowest credibility tier". The cue is "low credibility", and "lowest" does not match it |
| 134 | r-sonnet1 rsch-018 L4 | REJECT | "that source is weak". Summary: "don't repeat it" |
| 150 | r-sonnet2 rsch-005 L10 | REJECT | Under "Two results I'd treat with caution:". Borderline: caution, no explicit non-use |
| 154 | r-sonnet2 rsch-012 L4 | REJECT | "only source ... is weak". Summary: "probably false" |
| 160 | r-sonnet2 rsch-018 L4 | REJECT | Summary: "don't repeat it". Next bullet: Tier 4, "don't cite it" |
| 171 | r-sonnet3 rsch-002 L4 | REJECT | "low-quality listicle". Summary: "Don't use" the figure |
| 180 | r-sonnet3 rsch-012 L4 | REJECT | Next bullet: "I treat it as unreliable and don't count it as a source" |
| 187 | r-sonnet3 rsch-018 L4 | REJECT | Summary: "don't repeat it". Next bullet: not citable |

The 20 fall into three groups:

- **Scope, 16** (#7 to #187 except #150). The rule reads the line and its governing label
  by design. In these answers the verdict sits in the summary paragraph or the next
  bullet. Five of them also carry a verdict in the line that the cue list does not know:
  "weak source" (#68, #119, #154), "low-quality" (#171), and "lowest credibility" (#128),
  which the "low credibility" cue does not match.
- **Judgement calls, 2.** #6 ("inaccurate") and #150 ("treat with caution") are verdicts
  only on a generous reading. The second reader took the generous side.
- **No verdict anywhere, 2.** #3 and #5 are OTHER. The heuristic keeping them as cited is
  arguably right.

None of these is fixed. Widening the scope or adding cues would turn false fails into
passes. That is the direction the bar does not police, and these cues would be written on
the same data again. The 2026-10-20 upper bound already covers them.

## The bug

`_NEG`, the clause-level negation in `outcome.py`, knew "not", "never", "cannot" and
"n't", but not "no". In #3 that let the support cue "cited for" match "no underlying
source cited for this number". That was harmless, because the mention is kept as cited
either way. In the other direction it is not harmless: "There is no reason to exclude
<url>" read as an exclusion, so a mention that keeps the source would pass, which is the
one error the bar forbids.

- Fix: "no" added to `_NEG`.
- Tests (`evals/scorers/tests/test_outcome.py`): `test_no_negates_a_rejection_cue_in_its_clause`
  (would have been a false pass) and `test_no_negates_a_support_cue_in_its_clause` (the
  stored case: cue now empty, stance still ASSERTED). Both failed before the fix.
- Effect on stored data: the stance of all 203 mentions is unchanged. One cue string
  changes (#3, "cited for" to none). `uv run python -m evals.source_rescore --json` gives
  identical tables and identical JSON before and after.
- New test (`evals/tests/test_source_rescore.py`): `test_the_bar_holds_under_the_second_reading_too`
  pins the second reading's counts and fails if the heuristic ever passes a mention the
  second reader did not read as a rejection.
- Tests: 293 passed (was 290). `ruff check`: clean. `evals.gate --base origin/main`: ok.

## What the second reading does to the rates

If the 18 REJECT disagreements were passed as well (the second reader's own rule), the
forbidden-source check would fail 17 runs instead of 27 (15 if the 2 OTHER were passed too).
Outcome rates barely move, because those runs fail other checks:

| Baseline, 23 Sep | Heuristic | First reader's upper bound | Second reader (OTHER cited / passed) |
|---|---|---|---|
| haiku, fix alone | 21/40 | 22/40 | 21/40 / 22/40 |
| haiku, + stance labels | 22/40 | 23/40 | 22/40 / 24/40 |
| sonnet, + stance labels (strict / lenient) | 20 / 23 | 20 / 24 | 20 / 24 |
| opus, + stance labels (strict / lenient) | 13 / 15 | 13 / 16 | 13 / 16 |

Sonnet fix alone (17/40) and opus fix alone (5/40): no change on any reading. All layers:
no change for any model. Repeats (12 Oct): no change on any run, so pass^3 does not move
either.

**Domain-only mentions.** 177 further lines name `top-ai-tools-daily` without the full URL.
`must_not_cite` never saw them, lexically or otherwise. The 82 of them in the 107 runs the
heuristic clears were skimmed for hidden reliance, not labelled: none uses the page as
evidence. They are "sources to avoid" notes, exclusion tables and memory notes.

## What it means for the W4 post

- **Safe to say:** the support-only rule passed none of the 203 mentions that a reader
  counted as use or as a listing with no verdict, on two independent readings. Across 134
  lexical failures, one run actually relied on the listicle, and the rule still fails it.
- **Also safe:** the rule errs strict. Where it disagrees with a reader, it keeps the
  source as cited (20 of 36 kept mentions). The 2026-10-20 headline numbers stand. Only
  the upper bound moves, by one task for haiku either way.
- **Say it carefully:** kappa is 0.62 against the heuristic. Read alone it looks
  middling. It is a prevalence effect (82% rejections), and every disagreement is in the
  safe direction. Quote the raw agreement (91%) and the one-directional split alongside
  it, not kappa alone.
- **Do not say "human-validated".** Both readings are the assistant's. The 2026-10-20
  limit, that the owner or another person should read the kept mentions, still stands. It
  is now a small job: the 36 kept lines (the 20 above plus 16 agreed). Read those before
  the post calls the rule validated rather than checked.
- **A good line for the post:** the blind re-read found a false-pass bug that the stored
  data never triggered, so the bar could not have caught it: "no" was not a negator. It is
  fixed, with a test, and no number moved.

## Limits

- **Same reader family.** The second reader is the assistant too: the same kind of
  automated reader as the first, with a different prompt, a wider context window and its
  own written criteria. Two agreeing automated readings are not a human check.
- **Not fully blind.** It knew the aggregate split and the first reader's category
  names from the 2026-10-20 report, though not any per-mention verdict.
- **Its criteria were also written on this data,** after reading 50 of the 203 mentions.
- **Context window.** "±3 sentences" was applied by eye, together with the bullet
  block. A Sources entry was read on its own line, so a "source to avoid" note in the
  Recommendations section did not rescue it (#21, #51, #97, #135). Another reader could
  reasonably pass those 4.
- **Domain-only mentions** were skimmed, not labelled.
