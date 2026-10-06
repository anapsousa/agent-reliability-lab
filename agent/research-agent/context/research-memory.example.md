# research-memory.md — redacted stub

Real file is gitignored. Copy from
`<orchestrator-repo>/research-agent/memory/research-memory.md`.

Contains: cached competitor profiles, preferred sources per topic, reusable
benchmarks. **Private — competitor intel and client-adjacent material.**

Shape:

```
## Competitor profiles
### [Company]
- Last verified: YYYY-MM-DD
- Confidence: high | medium | low
- [findings with source URLs]

## Preferred sources
- [topic] → [source, why]
```

> Eval note: this file is *mutable state* the agent writes back to. The harness
> must reset it to a fixed snapshot before every run, or task N contaminates
> task N+1 and the golden set stops being independent.
