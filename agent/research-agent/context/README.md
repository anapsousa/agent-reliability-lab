# Vendored context — system under test

The live `research-agent` reads four files from the orchestrator repo by
absolute path. That is fine for the live agent and wrong for an eval harness, for two
reasons:

1. **Reproducibility.** Files outside this repo change whenever the orchestrator repo is edited.
   A pass rate measured against a moving context is not a measurement of the
   agent — it is a measurement of the agent *and* whatever the context happened
   to be that afternoon.
2. **Disclosure.** This repo is public. Those files contain private business
   context and cached competitor profiles.

So the four files are vendored here and **gitignored**. Only the redacted
`*.example.md` stubs are committed, so the public repo shows the shape of the
context without its content.

## Setup after clone

Populate the four ignored files from your local orchestrator repo:

| Vendored file | Source in the orchestrator repo |
|---|---|
| `role.md` | `research-agent/CLAUDE.md` |
| `research-memory.md` | `research-agent/memory/research-memory.md` |
| `playbook.md` | `research-agent/skills/research-agent/SKILL.md` |
| `company-context.md` | `shared/company-context.md` |

Copy, don't symlink — a symlink reintroduces the moving target.

## Re-pinning

When you deliberately want the eval to reflect an updated context, re-copy the
files **and** bump the agent version directory (`v1` → `v2`). Changing context
under a fixed version number silently invalidates every historical pass rate in
`evals/reports/`.

Record each re-pin in `agent/research-agent/PINS.md` with the date and what changed.
