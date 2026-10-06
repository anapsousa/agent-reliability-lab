# CLAUDE.md — Agent Reliability Lab

Project-scoped instructions for contributors and coding agents.

## Project

Agent reliability and evaluation lab: build an agent, measure it properly, publish the measurement.

- Open the project folder directly in Claude Code. The repo is project-scoped, with its own MCP scoping.
- `README.md` is a public-facing artifact. Write it as one.

## Layout

The planned tree, extended one level so a second agent under test is a directory rather than a refactor.

```
agent-reliability-lab/
├── CLAUDE.md                 # this file
├── README.md                 # public-facing; portfolio artifact
├── .claude/agents/           # project-scoped agents — never ~/.claude/agents
├── agent/                    # systems under test, pinned
│   └── research-agent/
│       ├── PINS.md           # pin log — every version, every re-pin
│       ├── v1/agent.md       # frozen. Never edited; copy to v2 to change.
│       └── context/          # vendored orchestrator context, gitignored (stubs committed)
├── evals/
│   ├── golden/<agent>/       # task dataset, versioned, one file per task
│   ├── scorers/              # outcome, trajectory, tool-call, cost — shared
│   ├── judges/<agent>/       # LLM-as-judge prompts + calibration set — per agent
│   └── reports/              # pass-rate-over-versions, committed
├── mcp/                      # MCP server(s) written for this project
├── redteam/
│   ├── suites/               # injection + exfiltration suites
│   └── findings/             # one file per finding
├── traces/                   # OTel config, dashboards-as-code
└── .github/workflows/        # eval gate on PR
```

Keep new work inside these directories. Propose a new top-level directory before creating one.

### The pinning rule

Everything under `agent/` is a **frozen system under test**. Editing a published
version directory silently invalidates every historical pass rate in
`evals/reports/`. To change an agent, copy `vN` to `vN+1` and edit there, then
log it in that agent's `PINS.md`. Re-copying context files counts as a version
bump even when the prompt is untouched.

`agent/*/context/` holds the context files the live agent reads by
absolute path. They are vendored here so the system under test is reproducible,
and gitignored because they are private and this repo is public — only redacted
`*.example.md` stubs are committed.

## Tooling

Verify current versions and pricing before committing to any of these — the recommendations date to ~May 2026.

- **Eval harness core — Inspect (Python).** Models agentic tasks properly (solver/scorer separation) rather than bolting trajectories onto prompt testing. Trade-off: Python-first, off the existing TS muscle memory.
- **Tracing — Arize Phoenix.** Open source, OTel-native, traces stay portable. Trade-off: self-hosted.
- **Red-team — Promptfoo.** Ready-made injection and jailbreak plugins; YAML/TS config. Overlaps with Inspect on plain evals — use it for red-team only, never for both.
- **Rejected as primary — Braintrust.** Better DX, one tool instead of three, CI-native, but hosted and paid; a self-built harness is worth more as a public artifact. Reconsider for client work where speed beats provenance.

## Decisions (settled 2026-08-06)

| # | Decision | Consequence |
|---|---|---|
| 1 | First system under test: **`research-agent`**, pinned as `v1` | Widest tool surface, ingests untrusted web content, so it feeds both the eval suite and the M3 injection suite |
| 2 | CI regression tolerance: **X = 15 points** (was 5; revised 2026-10-06) | One 40-task run resolves about ±15 points, so 5 flagged noise. Tighten only with more tasks or k >= 3 repeats, not by choosing a smaller number |
| 3 | Tracing: **self-hosted Phoenix** | Local Docker, OTel-native, traces stay portable. `traces/data/` is gitignored local state |
| 4 | Repo: **public from day one** | The secrets rules below are load-bearing, not aspirational. Check git tracking before writing any file that carries credentials |
| 5 | Sequencing: **harness multi-agent, M1 depth on `research-agent` only** | Then `seo` → `qa` → `content` → `creative` → `copywriter`, one at a time, in descending tool-call surface |

On #5: scorers are shared across agents; judges and golden sets are not. The
per-agent cost is the human labelling (≥50 examples each), not the code. Adding
an agent means one new judge, one new golden set, one new directory.

## Conventions

- en-GB in code comments, commits, docs and chat. User-facing copy is pt-PT only, never pt-BR.
- Numbered step-by-step for multi-step tasks. Show the plan before large changes.
- Run tests and lint before declaring anything done.
- Never touch secrets or `.env*`. Never push without explicit confirmation.
- Check git ignore/tracking status **before** writing any file that carries credentials.
- Guard every backup so a second run never overwrites the first. Assume every script gets run twice — write it idempotent.
- Report entry-by-entry what was removed or replaced. Never just a count.
- Reviews are blunt: flag bad patterns, missing tests and security issues directly.
- **Cost rule:** the orchestrator session may run at high effort; sub-agents default to standard effort, never maximum.

## Sub-agents

Reuse generic `qa` and `research` agents. Project-scoped agents exist only where a real boundary exists:

| Agent | Owns | Effort |
|---|---|---|
| `evals-engineer` | `evals/` — golden set curation, scorer implementation, judge calibration | standard |
| `redteam` | `redteam/` — adversarial suites, findings log | standard |
| `mcp-builder` | `mcp/` | standard |

Boundary rule: do not create an agent per file. **If two agents would need the same context to do their job, they are one agent.**
