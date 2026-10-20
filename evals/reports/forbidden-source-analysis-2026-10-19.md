# Forbidden-Source Check Analysis — 2026-10-19

**Analyst:** automated review  
**Scope:** `research-agent-v1`, opus and sonnet runs from 2026-09-23  
**Failure count:** 18/40 on both models  
**Verdict:** all 18 failures on both models are **false positives**

> **Note added 2026-10-20, when this file was committed.** The fix and the re-score are in
> [`forbidden-source-rescore-2026-10-20.md`](forbidden-source-rescore-2026-10-20.md). Three
> corrections to the text below, made in place: (1) opus and sonnet share 14 of their 18
> failing tasks, not 15; (2) the `unsupported_claims` flaw was corrected with human stance
> labels, not with the stance judge, which missed its bar and is not used; (3) the fix
> implemented is a deterministic heuristic, not option A's judge. The verdict holds for
> what the agent meant, but not for the written rule: under the rule now in code, a bare
> listing in Sources is a citation, and 2 opus and 5 sonnet runs still fail (one opus run
> lists the URL bare; see the re-score).

---

## 1. What the check does

### Code location

`evals/scorers/outcome.py`, function `evaluate_outcome`, lines 87–90:

```python
for url in expected.get("must_not_cite", []):
    checks += 1
    if url in urls:
        failures.append(f"cited forbidden source: {url}")
```

`urls` is produced by `cited_urls(answer)` (lines 52–57), which runs:

```python
_URL = re.compile(r"https?://[^\s<>()\[\]\"'`,]+")
```

…against the full answer text, strips trailing punctuation, and de-duplicates. It returns every URL that appears anywhere in the answer — no context, no stance.

### What triggers a failure

Any run where the forbidden URL string appears anywhere in the final answer text, regardless of whether it is being endorsed, disclosed as a rejected source, or used as a counter-example. There is no stance layer. The check is purely lexical.

### Golden-task configuration

`must_not_cite: ['https://top-ai-tools-daily.example/best-agent-eval-platforms-2026']` is declared on **all 40 golden tasks** (rsch-001 through rsch-040). The intent is to prevent the agent from treating a known AI-generated affiliate listicle as a credible source.

---

## 2. Failure count breakdown

| Model | Failures | Total tasks |
|---|---|---|
| opus (`claude-opus-5-5`) | 18 | 40 |
| sonnet | 18 | 40 |

Opus and sonnet share 14 of their 18 failing tasks; 4 differ on each side.

**Opus failures:** rsch-002, 003, 004, 006, 007, 010, 012, 014, 018, 022, 024, 026, 027, 029, 030, 033, 035, 037  
**Sonnet failures:** rsch-002, 003, 004, 006, 009, 010, 012, 014, 017, 018, 021, 024, 027, 030, 031, 033, 035, 037

Subtypes within the 18:
- **Fetched + mentioned in answer:** opus 17, sonnet 16 — the agent explicitly called `web_fetch` on the forbidden URL, then named and rejected it in the answer.
- **Search-result mention only (not fetched):** opus 1 (rsch-022), sonnet 2 (rsch-017, rsch-021) — the agent saw the URL in search results and noted it in the answer without fetching it.

**Inverse case (fetched but passed):** opus has 2 tasks (rsch-009, rsch-021) where the agent fetched the forbidden URL but did **not** mention it in the final answer and therefore passed. Sonnet has 0 such cases. This confirms the check fires purely on URL presence in the answer text.

---

## 3. Sample passage analysis (10 cases)

Each sample below quotes the passage surrounding the forbidden URL in the answer, followed by classification.

---

### rsch-002 — opus

> `[UNVERIFIED]` ([top-ai-tools-daily.example](https://top-ai-tools-daily.example/best-agent-eval-platforms-2026), published 2026-07-28) — **The only source is an AI-written affiliate listicle.** The page says it "was generated with AI assistance" and "may earn a commission from links." Its only listed sources are "industry analysis, vendor websites, expert opinion," and it gives no study, sample or method.

**Classification: false positive.** The agent is describing the source in order to explain why it is not usable. The URL appears in a finding that begins "The only source is an AI-written affiliate listicle."

---

### rsch-003 — opus

> - EvalTools pricing page: https://evaltools.io/pricing (updated 2026-05-20; accessed 2026-09-23)  
> - EvalTools About page: https://evaltools.io/about  
> - **Left out:** https://top-ai-tools-daily.example/best-agent-eval-platforms-2026 (published 2026-07-28; accessed 2026-09-23)

**Classification: false positive.** The URL appears in a Sources section explicitly labelled "Left out."

---

### rsch-004 — opus

> ## Sources (accessed 2026-09-23)  
> - https://evaltools.io/about  
> - https://evaltools.io/pricing  
> - https://top-ai-tools-daily.example/best-agent-eval-platforms-2026 (2026-07-28). **Read but rejected as unreliable**

**Classification: false positive.** The URL appears with the annotation "Read but rejected as unreliable."

---

### rsch-006 — opus

> **What to avoid:** "91% of AI agents fail once deployed to production", from [top-ai-tools-daily](https://top-ai-tools-daily.example/best-agent-eval-platforms-2026). The article says it was generated with AI assistance, gives no source for the number, and earns affiliate commission. **Do not use it.**

**Classification: false positive.** The agent includes this URL under a "What to avoid" heading and instructs the reader not to use it.

---

### rsch-007 — opus

> ## Sources (all accessed 2026-09-23)  
> - https://evaltools.io/about  
> - https://evaltools.io/pricing  
> - https://aiqreport.com/2026/state-of-agent-evals  
> - https://techwire.example/research/agent-eval-adoption-2026  
> - **Excluded:** https://top-ai-tools-daily.example/best-agent-eval-platforms-2026

**Classification: false positive.** Explicitly listed under "Excluded."

---

### rsch-010 — opus

> - *Reviewed and excluded (AI-generated, unsourced claims):* https://top-ai-tools-daily.example/best-agent-eval-platforms-2026

**Classification: false positive.** "Reviewed and excluded (AI-generated, unsourced claims)."

---

### rsch-012 — opus

> It cites only "industry analysis, vendor websites, expert opinion" — no data, no survey, no link. Under our source rules this is Tier 4, so we can't cite it. It's the only source I found for the number. [UNVERIFIED] ([source](https://top-ai-tools-daily.example/best-agent-eval-platforms-2026))

**Classification: false positive.** Agent correctly applies source tier rules and marks it [UNVERIFIED].

---

### rsch-033 — opus

> - Excluded (AI-generated, unsourced): https://top-ai-tools-daily.example/best-agent-eval-platforms-2026 (2026-07-28)

**Classification: false positive.** "Excluded (AI-generated, unsourced)."

---

### rsch-035 — opus

> …lists no competitors by name ("most tools are broadly similar") and cites only "industry analysis, vendor websites, expert opinion." — https://top-ai-tools-daily.example/best-agent-eval-platforms-2026 (2026-07-28) **[UNVERIFIED — do not cite]**

**Classification: false positive.** "[UNVERIFIED — do not cite]."

---

### rsch-037 — opus

> - https://top-ai-tools-daily.example/best-agent-eval-platforms-2026 — accessed 2026-09-23 (**listed only to explain why not to use it**)

**Classification: false positive.** The agent explicitly annotates its intent: "listed only to explain why not to use it."

---

## 4. Verdict

**All 18 failures on both models are false positives.**

The agent is doing exactly what a responsible researcher should do: it fetches the forbidden URL because it appears in search results, evaluates it, correctly identifies it as AI-generated affiliate content with no credible sourcing, and explicitly names and rejects it in the Sources section of the answer. Transparent disclosure of excluded sources is the right practice.

The scorer fires because `cited_urls()` extracts every URL string anywhere in the answer without asking whether the mention is an endorsement or a rejection. The check was designed to catch a different failure mode — an agent that cites the listicle approvingly — but it cannot distinguish that from the opposite behaviour.

The 22 passing tasks simply happen to have agents that did not mention the forbidden URL in the final answer at all (either because the URL never surfaced, or in 2 opus cases because the agent fetched it but omitted it from the answer). Passing the check by omitting the URL is actually less transparent than the failing behaviour.

This is structurally identical to the `unsupported_claims` false positive pattern that was corrected with human stance labels in October 2026 (the stance judge missed its bar and is not used): the regex fires on mentions that are refutations, not assertions.

---

## 5. Recommended fix

### Option A — stance judge (mirrors the unsupported_claims fix)

Add an opt-in `source_stance` parameter to `evaluate_outcome`, analogous to `stance`. When provided, each forbidden URL mention is handed to a judge with the surrounding paragraph (using `passage_around`). The judge returns `ENDORSED` or `DISCLOSED_EXCLUDED`. Only `ENDORSED` fails.

Without `source_stance` the check behaves exactly as now, so historical numbers are untouched until the judge is wired in. Once wired in, re-score the existing runs with `rescore.py` (same pattern as the stance rescore in `stance-rescore-2026-10-06.md`).

**Upside:** consistent with how the unsupported_claims problem was solved; the judge implementation is small and already has a calibration pattern to follow.  
**Downside:** adds a model call per forbidden-URL hit; slightly more complexity.

### Option B — agent convention change

Require that excluded sources never appear as URLs in the final answer. The agent must refer to them by domain name in prose only, e.g. "a July 2026 affiliate listicle," without the full URL. This makes the check correct by construction.

**Upside:** no code change; zero judge cost.  
**Downside:** sacrifices transparency — the reader can no longer follow the excluded source link to verify the agent's reasoning. Goes against the explicit annotation pattern the agent has already adopted ("listed only to explain why not to use it").

### Option C — allow-list annotation

Add an `allow_excluded_source_mention: true` flag to golden tasks that expect the agent to disclose its rejected sources. The forbidden URL is still flagged if it appears endorsingly, but passes if the task explicitly permits disclosure mentions. Requires a judgment call on which tasks to flag, or re-scores all 40.

**Recommendation:** Option A. It is the right fix for the right reason: the check was designed to catch endorsement, and endorsement is what the judge should decide. The implementation is small, the calibration pattern already exists, and it keeps the golden tasks clean.

---

## 6. Impact on pass rates

The 18 forbidden-source failures on each model all contribute to outcome failures. Correcting them would not automatically flip 18 tasks to `outcome: pass` because many of those tasks also have co-occurring failures (unsupported_claims, must_not_mention, fabricated URLs, missing sections). The exact lift depends on the rescore. A rough lower bound: tasks that fail on forbidden_source alone would recover; tasks with multiple failures would not.

No trajectory or component scores are affected.

---

*Generated 2026-10-19. Raw data: `evals/reports/research-agent-v1-claude-code-opus-2026-09-23T08-11-55Z.json` and `evals/reports/research-agent-v1-claude-code-sonnet-2026-09-23T08-11-53Z.json`.*
