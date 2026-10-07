# agent-reliability-lab

[![Eval gate](https://github.com/anapsousa/agent-reliability-lab/actions/workflows/eval-gate.yml/badge.svg)](https://github.com/anapsousa/agent-reliability-lab/actions/workflows/eval-gate.yml)

An evaluation harness for one LLM agent, built to be measured honestly in public:
a 40-task golden set, three scorer layers, calibration against human labels, and a
regression gate in CI. I am a QA engineer, not a model researcher. The point of the
repo is to apply test-management discipline to an agent, and to publish what that
turns up, including the places where my own measurement was wrong.

## Headline: my eval ranked Opus last, and the eval was wrong

I ran the same research agent on three Claude models over the same 40 tasks. The
outcome layer produced this ranking:

| Model | Outcome | Trajectory | Components | All layers | API-equivalent cost | p95 latency |
|---|---|---|---|---|---|---|
| haiku | 52% (38-67) | 95% | 8% | 0% | $1.91 | 55 s |
| sonnet | 40% (26-55) | 95% | 28% | 20% | $3.44 | 80 s |
| opus | 12% (5-26) | 92% | 38% | 10% | $5.59 | 46 s |

Brackets are 95% Wilson intervals. One run per task per model, 2026-09-23.

Opus, the most careful model, came last. The cause is a regex. The always-on
`unsupported_claims` check fails any answer where a known-bad figure appears (a
fabricated "91% of agents fail" statistic, a fake $199 price). It cannot tell an
answer that asserts the figure from one that quotes it to reject it. The regex
flagged 94 passages in 57 of the 120 runs, and 53 of the passages were opus.

What I did about it:

1. Labelled all 94 flagged passages blind, by hand: 71 refuted, 19 asserted, 4 neutral.
   So the regex called 94 assertions and I found 19 (9 after adjudication, below).
2. Built an LLM stance judge (zero tools, one passage per call) and scored it against
   my labels. It agrees on 70 of 71 refutations and misses most assertions (asserted
   recall 16% for haiku, 5% for sonnet). **It is not calibrated and is not used for
   scoring.**
3. Read the disagreements. Twelve of my 19 "asserted" labels were plain debunkings
   (eleven within the first 18 items, the twelfth found on a repeat pass): a key slip on my side, not the judge's. Four more
   were correct arithmetic (EUR 249 less 20% is about EUR 199) that matched the regex,
   which is why a fourth label, UNRELATED, now exists.
4. Put the 25 contested items into a blind adjudication page and re-labelled them.
   12 of the 19 asserted labels became refuted, 4 neutrals became refuted, 1 refuted
   became asserted. Final: 86 refuted, 8 asserted.
5. Scored the judge against those labels, against a bar I wrote down first: the judge
   replaces the regex only if asserted recall reaches 90%. **It missed: 2 of 8, 25%** (11% on an earlier run of the same
   judge, so it is unstable as well as wrong).
   Most of the misses are the EUR 199 annual-billing arithmetic, which the judge calls
   unrelated. The regex stays, the judge is not used.
6. Re-scored the stored transcripts with the human labels in place of the automatic
   fail. Opus moves from 12% to 25-28% on outcome and is still last on that layer;
   on all layers it goes from 10% to 18%, next to sonnet's 20%. The regex explained
   about half of the original 40-point gap, not all of it. A second check, citing a
   forbidden source, fails 18 of 40 runs for both opus and sonnet and has not been
   examined. Full table, method and limits:
   `evals/reports/stance-rescore-2026-10-06.md`.

The component layer's failures were checked by hand and are real: blown step budgets,
and URLs fetched from memory instead of from search results.

A second finding, from an earlier calibration round (70 blind human labels): human/judge
agreement was 54% on a fixture corpus whose sources cannot be checked, and 85% on real,
live-verified vendor sources. On the same items the LLM judge matched the known-correct
verdict 90% and 100%, so the humans were the noisy side where nothing could be looked up.
Details in `evals/judges/calibration-2026-09-15/report.md`.

## Known limits

Read these before citing any number here.

- **One run per task.** This is called a reliability lab and has no repeated-trial data
  yet: no pass^k, no run-to-run variance. That is the largest hole and the next thing
  to fill.
- **The headline outcome ranking in the table above is wrong, and the corrected one is
  not clean either.** The reports are kept as they were. The re-scored numbers are in
  `evals/reports/stance-rescore-2026-10-06.md`; the models are not separable at n = 40.
- **n = 40 gives about +/-15 points** per series. The CI gate originally failed a PR at
  -5 points, tighter than the instrument can resolve, and now fails at -15. It is a
  policy line, not a significance test: it catches a large regression and misses smaller
  ones. Repeated runs (k >= 3) are the way to tighten it.
- **The stance judge failed its pre-registered bar** (asserted recall 25%, bar 90%) and
  is not used for scoring. The labels behind that number are one annotator's, with 8
  positives.
- **One agent, one domain.** A research agent against a frozen fixture web. Nothing here
  generalises to other agents or to the live web.
- **Cost is API-equivalent.** Runs go through Claude Code on a subscription, so the
  dollar figures are what the same runs would cost billed, not what I paid.
- **Red-team suites and tracing are not done.** `redteam/findings/` is empty and
  `traces/` is a placeholder. Nothing is claimed about injection resistance.

## How the measurement works

Three scorer layers, because "did it work" is three questions:

1. **Outcome**: did the task complete correctly (must-cite, must-not-cite,
   must-mention, no fabricated URLs, no unsupported claims).
2. **Trajectory**: was the path sane (no loops, no abandoned branches).
3. **Component**: tool-call correctness and step count within budget.

Every run reports pass rate, cost and p95 latency together, and sample size with
every result.

The agent runs as itself: `claude -p` with the pinned prompt, and only the web swapped
for a frozen fixture corpus served over MCP (`mcp/fixture-web/`), so runs are
deterministic in what the agent can see. Built-in tools are disabled by name and each
task runs in an empty directory.

**The pinning rule.** Everything under `agent/` is frozen. Editing a published version
changes what the eval measures, so changes go into a new `vN+1` directory and are logged
in `PINS.md`.

## Layout

| Path | Contents |
|---|---|
| `agent/` | Systems under test, pinned by version |
| `evals/golden/` | 40 task definitions, with fabricated-URL and unpassable-check guards |
| `evals/fixtures/` | The frozen fictional web (invented vendors on `.example` domains) |
| `evals/scorers/` | Outcome, trajectory and component scorers, with unit tests |
| `evals/judges/` | LLM judges, human labels, calibration reports, the adjudication page |
| `evals/runners/` | The Claude Code runner |
| `evals/reports/` | Committed baseline reports, one JSON per run |
| `evals/gate.py` | The CI regression gate |
| `mcp/fixture-web/` | The fixture web as an MCP server |

## Run it

Needs Python 3.12+, [uv](https://docs.astral.sh/uv/), and for real runs a logged-in
Claude Code CLI.

```
uv sync --all-extras --dev
uv run pytest evals/ -q                      # unit tests, no model calls
uv run ruff check .
uv run inspect eval evals/tasks/research_agent.py --model mockllm/model   # harness smoke test
```

Real runs use your Claude Code subscription, not an API key:

```
uv run python -m evals.runners.claude_code --model sonnet --tasks rsch-001,rsch-002
uv run python -m evals.gate --base origin/main
```

The agent under test reads four private context files that are gitignored here; only
redacted stubs are committed. To run a real sweep you need to populate them, see
[`agent/research-agent/context/README.md`](agent/research-agent/context/README.md).
The unit tests and the mock-model smoke test do not need them.

## Example data

The transcripts and stance items in this repo were generated while the agent ran with my
own business context loaded. Before publishing I pseudonymised that context: business
and project names inside the stored answers are replaced with placeholders ("Acme
Training", "Atelier Alfa"), and one phrase in the agent prompt was genericised (logged
in `agent/research-agent/PINS.md`). Scores, labels and numbers are unchanged; I re-ran
the full test suite and `evals.rescore` after the edit to confirm. The repo was also
published from a fresh history, so earlier commits are not part of it.

## Author

Ana Sousa · Pompousweek

## Licence

Code, fixtures and reports: [MIT](LICENSE). The fixture corpus is invented. Product
names that appear in the calibration sets (Braintrust, Langfuse, Promptfoo, Arize
Phoenix) belong to their owners and are described from their public documentation as
of 2026-09-15.
