# Companion V2 prompt budget

Pinned llama.cpp Android currently uses an 8192-token context and includes
native context shifting. MyGPT does not replace that upstream behavior.

The remaining risk is an oversized **single user turn** containing:
- current signed Book context;
- current supervision state;
- relevant explicit memory;
- recent conversation re-prime data;
- current user message.

`CompanionPromptBudget` now applies a conservative **5600-character** pre-JNI
budget. This is intentionally described as a character guard, not an exact
token counter.

Priority:
1. preserve the complete current user message;
2. preserve signed Book metadata and as much current Book text as fits;
3. preserve current supervision state;
4. include relevant explicit memories within a bounded JSON block;
5. include recent conversation history only with remaining room.

Book title/text may be truncated inside valid JSON and carry explicit
`title_truncated/text_truncated` flags. Memory may report
`omitted_for_budget`; this status also invalidates older recalled-memory blocks
as current memory.

Memory/history data strings encode raw square/angle brackets as Unicode escapes,
so content cannot manufacture a raw MyGPT closing delimiter.

Each generated turn writes only a content-free
`files/prompt-budget-last.txt` report with lengths/counts/truncation flags.
No Book, memory, history or user text is persisted in that report.
