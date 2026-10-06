# Judge calibration — 2026-09-15

## Method

Two rounds of blind human labelling, both by Ana, both collected via a published Artifact
(pass/fail buttons, no ground truth shown, order shuffled). No real agent was run for either
round — every "answer" is hand-authored to exercise a specific pass or fail condition, then
graded against a known-correct verdict.

**Round 1 — fixture set (50 items, 25 golden tasks × 2 variants).** Built directly from
`evals/golden/research-agent/rsch-*.yaml`. The "a" variant satisfies that task's
`must_cite`/`must_not_cite`/`must_mention` rules; the "b" variant deliberately breaks the one
failure mode called out in that task's `notes` (wrong-tier citation, a fabricated number, a
backwards methodology read, an honest-refusal that fills in a guess instead). Domain is
"EvalTools" — a fictional company on a frozen, non-resolving fixture internet, by design (see
`evals/golden/SCHEMA.md` and the corpus notes) so the harness can grade deterministically
without live web calls.

**Round 2 — real-vendor set (20 items, 10 tasks × 2 variants).** Same shape, but about real
products — Braintrust, Langfuse, Promptfoo, Arize Phoenix — with every source URL fetched
directly on 2026-09-15 and verified to actually state the cited claim.

## Result

| Set | Agreement | n |
|---|---|---|
| Fixture (fake sources) | **54%** | 50 |
| Real vendors (real sources) | **85%** | 20 |

## The finding

The fixture round's first pass (before the sources were labelled as fictional) produced the
same ~54-56% number — so the low agreement isn't an artefact of confusing Ana about the
premise; it holds even once the fixture nature was made explicit. **When a source can't be
independently checked, a confidently-worded wrong answer is genuinely hard to catch** — most
of round 1's disagreements are "b" (deliberately flawed) answers that got passed, not "a"
(correct) answers that got failed. That matches the exact risk the golden-set notes for
rsch-009 name directly: *"fabrication that is indistinguishable from competence unless you
know the corpus."*

Round 2 nearly doubles agreement with the same reader, same grading task, same format — the
only variable that changed is that the sources are real and clickable. Two of the three
disagreements there are the harder direction (a wrong answer passed); one (`r06a`) is a
correct answer that got failed and is worth Ana rechecking by hand, since it may just be a
misread rather than a real judgement call.

## Implication for M1

The calibration checkbox in `agent-reliability-handoff.md` asked for "≥50 human-labelled
examples" — this round supplies 70 across two sets, satisfying that on count. But the more
useful takeaway is qualitative: **a judge (human or LLM) calibrated only against an
unverifiable fixture corpus is measuring something close to "does this sound right," not
"is this actually right."** The regression gate this project is building should weight
mechanical checks (`must_cite`/`must_not_cite` regex matching, the always-on fabricated-URL
scorer) more heavily than free-form LLM-judge agreement wherever a task's ground truth can be
checked mechanically — and where it can't, expect judge/human agreement to sit closer to 54%
than 85%, not because the judge or the human are bad at their jobs, but because the task
itself is genuinely harder without a live source to check.

## LLM-judge run — 2026-09-15, later same day

Run via `evals/judges/run_llm_judge.py`, using `claude -p --model sonnet --effort low`
(Ana's existing subscription, not a billed `ANTHROPIC_API_KEY` call — pure text judgment on
already-written answers, no tool use, no agent execution). Full output in
`judge-results.json`.

| Comparison | All (n=70) | Fixture (n=50) | Real (n=20) |
|---|---|---|---|
| Judge vs. human | 62.9% | 54.0% | 85.0% |
| Judge vs. known-correct verdict | 92.9% | 90.0% | 100.0% |

The judge tracked the known-correct verdict far more closely than the human did on the
fixture set (90% vs. 54%) — plausibly because a model has less social pressure than a person
to extend good faith to confident, well-formatted prose citing a source it can't check. This
is itself a data point for the project's thesis: automated, mechanically-groundable checks
catch what a generous human reader misses.

One judge/truth disagreement is worth keeping as a teaching example rather than a bug:
**`t24a`** — a correct answer that mentions a real "11%" judge-calibration figure — was
FAILed by the judge with the reason *"introduces a specific 11% judge-calibration figure not
established anywhere as fact."* That figure is real within the fixture's own task definition
(`rsch-038`'s `must_mention` pattern), but invisible to a judge reading only the raw Q&A pair
with no access to the source documents. The judge hit the exact same blind spot the human
did on this style of task — evidence that an LLM judge without the mechanical
`must_cite`/`must_mention` scorer alongside it is not meaningfully more trustworthy than a
person, on ungroundable material. This is the argument for keeping the deterministic
`evals/scorers/outcome.py` checks as the primary gate and treating the LLM judge as a
second opinion, not a replacement.

## Open

- `r06a` — recheck by hand; possible mislabel rather than a real disagreement.
- Consider growing the real-vendor set past 20 if the case study wants a bigger n; the fixture
  set does not need growing — its ceiling is what it is by design.
- The regression gate still needs a real, billed model run against the full 40-task golden
  set to produce a pass-rate baseline — separate from this calibration work, and still
  pending Ana's spend decision.
