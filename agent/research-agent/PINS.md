# Pin log — research-agent

Every version directory under `agent/research-agent/` is a frozen system under
test. Historical pass rates in `evals/reports/` are only comparable if the thing
they measured never moved. Log every pin and re-pin here.

| Version | Date | Source | Context re-copied | What changed |
|---|---|---|---|---|
| `v1` | 2026-08-06 | `~/.claude/agents/research-agent.md` | initial | Baseline pin. Only deviation from live: four context paths rewritten from absolute orchestrator-repo paths to `../context/`. Prompt body byte-identical otherwise. |

## Publication edit (2026-10-06)

When this repo was made public, the orchestrator's first name in `v1/agent.md` (in the
sentence "orchestrated by ...") was replaced with "the assistant", and business names
inside the stored transcripts were pseudonymised. The baseline reports in
`evals/reports/` were produced with the original wording. The change is one noun in an introductory sentence and does not touch any
instruction, but it is a deviation, so it is logged here rather than hidden.

## Rules

1. Never edit a published version directory. Copy to the next `vN` and edit there.
2. Re-copying context files counts as a version bump, even if the prompt is untouched.
3. Record the live agent's own git SHA or mtime at pin time when you have one — "the version I had that day" is not a reference.

## Harness deviations

`v1` is a Claude Code subagent. It is executed under Inspect as a port, not as
itself. Anyone reading a pass rate from this suite is reading a number about the
port, so the gap is written down rather than left implicit.

| Live agent | Under Inspect | Why, and what it costs |
|---|---|---|
| Runs inside Claude Code | `system_message(agent.md)` + `generate()` with tools | No react scaffolding or submit tool is injected, so the system prompt stays byte-faithful. Cost: no subagent handoff behaviour is exercised. |
| Reads context by absolute path with the `Read` tool | `read_context` tool over the four vendored files | Keeps the "read your context first" step a real, observable tool call, so the trajectory scorer can check ordering later. Inlining the files into the prompt would have erased that step. |
| `Firecrawl` → `WebSearch` → `WebFetch` | `web_search` + `web_fetch` over the frozen corpus | Reproducibility. See `evals/fixtures/research-agent/README.md`. Cost: the agent's documented Firecrawl-first tool preference is untested, and so is fallback-on-failure behaviour. |
| Writes back to `research-memory.md` after each task | Not implemented | The memory-update half of the agent's protocol is currently unmeasured. It is a real capability and a real injection surface — it belongs in the M3 red-team scope. |

Two of these are measurement gaps rather than fidelity choices, and both are
listed above so they cannot quietly turn into "the agent passes": tool-preference
and fallback behaviour, and the memory write-back.

## Second harness: real Claude Code (2026-09-23)

`evals/runners/claude_code.py` runs `v1` as itself: `claude -p` with the pinned prompt
as `--system-prompt`, and only the web swapped, via `mcp/fixture-web/`. That closes the
first deviation above for this harness. The remaining gaps:

| Gap | Cost |
|---|---|
| Tool names reach the model as `mcp__fixture-web__web_fetch`, not `web_fetch` | Scorers strip the prefix. The model sees a longer name than the port's |
| MCP errors arrive as `Error executing tool web_fetch: 404 …` | Same text as the port, plus the SDK's prefix |
| `--max-turns 12` stands in for the port's 25-message cap | Different unit. Turns are counted as assistant message plus results |
| Claude Code injects the account email into every session | The live agent receives it too, so this is faithful. Reports redact it |
| Memory write-back is still not implemented | Unchanged from the port |
