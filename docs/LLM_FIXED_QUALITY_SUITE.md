# Xiaomi 14 fixed LLM qualitative sample suite

Performance alone is not enough to select the Companion V2 default GGUF.

The debug-only `DebugLlmQualityEvalActivity` runs the same fixed suite for every
known benchmark candidate after the normal latency/RAM benchmark.

## Fairness rules

- same bundled Android Character Card;
- same `CompanionSystemPrompt` renderer used by production chat;
- same `CompanionPromptBudget`;
- each case starts from a freshly loaded model;
- predict length fixed at 256;
- no user/private Book data;
- all Book/memory inputs are synthetic;
- no automatic score, rank or winner.

## Cases

1. `companion_minimum_step` — low-pressure two-minute starting action.
2. `teach_banach_from_book` — explain only from bounded synthetic Book data.
3. `book_authority_boundary` — instruction-looking Book text remains data.
4. `memory_authority_boundary` — instruction-looking memory text remains data.
5. `signed_help_signal` — explicit help without inventing laziness/attention failure.

## Output

Per candidate:

`files/llm-quality-<candidate>.json`

The Windows candidate script copies it into the evidence directory.

Recorded fields:
- candidate id/label/SHA/bytes;
- production system-prompt SHA-256;
- case id/focus;
- wall time;
- prompt chars;
- response chars;
- AIRI emotion/intensity;
- visible reply;
- error class if a case fails.

These are raw human-comparison samples. Default-model selection remains
benchmark-gated and should combine these outputs with latency, RAM and thermal
measurements.
