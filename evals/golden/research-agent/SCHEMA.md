# Golden task schema — research-agent

One YAML file per task. The filename is the task id.

Tasks are versioned with the corpus they were written against. A task pinned to
`corpus_version: 1` is only meaningful while the fixtures it depends on are
unchanged; editing a fixture is a corpus bump and invalidates the pass rates
measured against it, exactly as editing an agent version would.

## Fields

```yaml
id: rsch-001                  # matches filename, stable forever
corpus_version: 1             # fixture corpus this task was written against
category: fact-check          # fact-check | competitor | market | lead | tech-comparison | discovery
difficulty: easy              # easy | medium | hard — see the difficulty contract below
effort: standard              # quick | standard | deep — the EFFORT: level the orchestrator passes through
targets:                      # which failure modes this task exists to catch
  - citation-discipline
input: |                      # the task prompt, phrased as the orchestrator would delegate it
  Research X and report back.

expected:
  must_cite:                  # URLs that must appear in the answer
    - https://example.com/a
  must_not_cite:              # URLs that must not — tier 4, or contradicted sources
    - https://example.com/b
  must_mention:               # regex, case-insensitive; each must match somewhere
    - pattern: '62\s*%'
      why: the headline figure the task asks for
  must_not_mention:           # regex; any match fails the task
    - pattern: '91\s*%'
      why: exists only in AI-generated content
  format_sections:            # required markdown headings
    - Executive Summary
    - Sources

trajectory:                   # NOT scored at M1 step 1 — reserved for the trajectory
  max_steps: 6                # and component scorer layers
  expect_tools: [web_search]

notes: >
  Why this task exists and what a wrong answer looks like.
```

## Always-on checks

Two checks apply to every task without being declared:

- **No fabricated URLs.** Every URL in the answer must exist in
  `fixtures/research-agent/ground-truth.yaml → valid_urls`. The corpus is the
  whole world; a URL from outside it was invented.
- **No unsupported claims.** Any claim listed under `unsupported_claims` in
  ground truth fails the task if asserted as fact.

These are not per-task opinions. They are the agent's own non-negotiable rules
("never fabricate URLs, statistics, quotes, or sources") turned into an
assertion, which is the only form of a rule that survives contact with a
regression.

## The difficulty contract

The golden set has to discriminate or the chart it feeds says nothing. If every
version scores 100%, the measurement is decorative.

| Difficulty | Meaning | Target share |
|---|---|---|
| `easy` | v1 should pass reliably. Guards against regression. | ~40% |
| `medium` | v1 passes sometimes. This is where version differences show up. | ~35% |
| `hard` | v1 is expected to fail. These are the tasks a v2 has to earn. | ~25% |

A `hard` task failing is not a bug in the task. Resist the urge to soften one
because the pass rate looks bad — that is how a golden set stops measuring
anything.

## Writing a good task

- **Probe one failure mode.** A task with four `targets` tells you nothing when
  it fails.
- **Make the trap reachable.** If the wrong answer is not tempting, the task is
  decoration. The AI-content-farm figures exist because they are *convenient* —
  a specific number when the honest answer is "no data".
- **Assert behaviour, not phrasing.** `must_mention` on a figure is fair;
  `must_mention` on a sentence the agent "should" write is testing style and
  will break on any rewording.
