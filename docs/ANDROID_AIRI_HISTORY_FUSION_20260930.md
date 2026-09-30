# AIRI paired-history budgeting in the Android companion

Base: Android lexical memory PR #42,
`6c47f706971677d5f84c983e954558e4992b9bcc`.

## Reproduced gap and production change

The actual `CompanionPromptBudget.compose` kept one truncated assistant answer
but dropped its paired question when a prior two-row exchange met a tight
1024-character prompt cap. The complete current user message survived, but the
historical answer had lost its conversational context.

The same production composer now directly invokes a Java port of AIRI's
`keepRecentHistoryItems` reverse scan. A user turn and all following reactions
form one positional group. Selection works newest-first, fitting or omitting a
whole group instead of independently spending the budget on assistant rows.
A tight-budget regression now retains both rows within 1024 UTF-16 units.

Upstream **moeru-ai/airi** had **49,891 stars** on 2026-09-30 UTC. The existing
**MIT** source pin is `b40e3e87b149ea5fb75d4944440493829e601411`; unchanged
`compaction.ts` has Git blob `59a76a9877086f66b5abc09b0f22802e4e27df7d`.
Copyright and license remain in the Java source, `third_party/airi`, and every
shared-source Android consumer's direct/inherited asset notices.

## Local adaptations and unchanged authority

- Whole groups receive a common bounded text cap, preserving chronological order
- An assistant-only legacy prefix is omitted; consecutive or pending user turns remain valid
- If a complete group's minimum representation cannot fit, it is omitted entirely
- Historical snippets can still be explicitly marked truncated; no semantic summary is invented
- Valid surrogate pairs are not split when the shared history/memory JSON helper clips text
- Full current user text, 5200/default and dynamic prompt caps, Book/memory priority,
  data-boundary escaping and content-free reports remain intact
- Durable history, SQLite schema, model selection and system authority are untouched

Grouping is positional, not validation of an arbitrary reply-to graph. A recovered
conversation can lose older groups under budget pressure. This change does not
claim to preserve all historical text or provide semantic compaction.

## Evidence

The no-install Node 24 oracle executes the unchanged pinned AIRI TypeScript and
checks all 128 deterministic suffix-selection fixtures. Actual Java compares those
fixtures and runs 3520 prompt-budget projections, plus the reproduced orphan case,
legacy/pending cases, whole-group omission, full-current-user and Unicode guards.
The shared Java runner now has 20 entrypoints, retaining prior 327 Gson and
109 sklearn parity cases. Source and runtime dependencies remain unchanged.

A single hosted workflow couples the actual AIRI oracle with the existing Java
8/17 matrix at one exact head. YAML is parsed locally before publication.
Local source/target-only Java 21 checks do not replace those hosted API/runtime
gates. APK, Android database/device and model-quality acceptance remain separate.

```sh
node android_spike/tools/airi_history_oracle.mjs
GSON_JAR=/path/to/gson-2.14.0.jar bash android_spike/tools/run_boundary_smoke.sh
```

Only `--write` regenerates fixtures. Neither command downloads a model, uses a
private asset, fetches submodule source or changes the stored conversation.
