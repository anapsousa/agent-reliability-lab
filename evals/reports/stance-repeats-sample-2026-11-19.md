# Stance sample for the repeat runs: owner labels, 2026-11-19

Owner labelled the 48-passage blind sample (`../judges/stance-repeats-2026-11-07/`) on
2026-11-19 in `label.html`, without the key. Scored against `key.json` afterwards. Each item
maps to exactly one model.

| Model | n | ASSERTED | REFUTED | NEUTRAL | ASSERTED share | 95% Wilson |
|---|---|---|---|---|---|---|
| claude-haiku-5-5 | 16 | 1 | 14 | 1 | 6.2% | 1.1% to 28.3% |
| claude-opus-5-5 | 16 | 1 | 15 | 0 | 6.2% | 1.1% to 28.3% |
| claude-sonnet-5-5 | 16 | 2 | 14 | 0 | 12.5% | 3.5% to 36.0% |
| All | 48 | 4 | 43 | 1 | 8.3% | 3.3% to 19.6% |

ASSERTED items: R009 (sonnet, rsch-009), R010 (sonnet, rsch-010), R013 (opus, rsch-018),
R029 (haiku, rsch-003).

## Against the rule fixed before labelling

The README set the rule: if the ASSERTED share is below about 10% for **every** model, run the
sonnet judge over all 467 and score it against these labels; if higher, the repeats' outcome
level is partly real and the regex stays.

- Haiku and opus are below 10%. Sonnet is at 12.5% (2 of 16), so the rule as written is not
  met: **the regex stays** and the repeats' outcome level is partly real.
- The false-fail is still large: 43 of 48 hits (90%) are REFUTED, close to the baseline's
  86 of 94. The three per-model intervals overlap almost entirely; 16 per model cannot
  separate sonnet from the others.
- No run is cleared by this sample (48 of 467 hits read).
