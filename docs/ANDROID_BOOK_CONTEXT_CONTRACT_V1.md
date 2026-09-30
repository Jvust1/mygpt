# Book Android → MyGPT Companion V2 signed context contract v1

Date: 2026-09-30

## Purpose

Provide fresh Book semantic context to Companion V2 without network transport,
screen reading, Accessibility, clipboard scraping, or durable source-text storage.

The receiver is protected by an Android `signature` permission. A Book build
must be signed with the same signing certificate as Companion V2 to send this
context. This is a deliberate deployment constraint.

## Permission

`dev.mygpt.companionv2.permission.BOOK_CONTEXT`

Protection level: `signature`.

The Book app must declare:

```xml
<uses-permission android:name="dev.mygpt.companionv2.permission.BOOK_CONTEXT" />
```

## Context action

Action:

`dev.mygpt.companionv2.action.BOOK_CONTEXT_V1`

The sender should target package `dev.mygpt.companionv2` explicitly.

Required extras:

| extra | type | rule |
|---|---|---|
| session_id | String | `[A-Za-z0-9][A-Za-z0-9_.-]{0,95}` |
| sequence | long | starts at 1; increments exactly by 1 in a session |
| course_id | String | bounded identifier |
| book_id | String | bounded identifier |
| book_version | String | permits `@`; max 160 chars |
| section_id | String | bounded identifier |
| source_id | String | bounded identifier |
| source_sha256 | String | lowercase 64-hex SHA-256 |
| mode | String | preview / learn / review / practice |
| captured_at_ms | long | source capture time |
| expires_at_ms | long | TTL >0 and <=300000 ms |
| title | String | optional/empty allowed; <=500 chars |
| text | String | nonblank; <=6000 chars |

A new session must begin with sequence 1. Within one session the
course/book/version identity cannot change. Context time cannot reverse.

## Clear action

Action:

`dev.mygpt.companionv2.action.BOOK_CONTEXT_CLEAR_V1`

Required extras:
- `session_id`
- `sequence` = prior accepted sequence + 1
- `occurred_at_ms`

This clears the current in-process context only.

## Example sender

```kotlin
val intent = Intent("dev.mygpt.companionv2.action.BOOK_CONTEXT_V1").apply {
    setPackage("dev.mygpt.companionv2")
    putExtra("session_id", "study-20260930")
    putExtra("sequence", 1L)
    putExtra("course_id", "functional-analysis")
    putExtra("book_id", "jiang-ze-jian")
    putExtra("book_version", "book@v1")
    putExtra("section_id", "ch1-s1")
    putExtra("source_id", "record-001")
    putExtra("source_sha256", "<64 lowercase hex>")
    putExtra("mode", "learn")
    putExtra("captured_at_ms", System.currentTimeMillis())
    putExtra("expires_at_ms", System.currentTimeMillis() + 120_000L)
    putExtra("title", "第一节")
    putExtra("text", "<bounded structured projection>")
}
sendBroadcast(intent)
```

The signature permission is enforced by Android before delivery.

## MyGPT handling

Accepted context is kept only in `BookContextMailbox`, a process-memory
singleton. It is not written to SharedPreferences, SQLite, chat history, or
long-term memory.

At prompt construction time it is rendered as
`BOOK_SIGNED_CONTEXT_JSON` and placed before the user message as
lower-authority application data. Recalled companion memory is a separate data
block. Neither Book content nor memory can become a system instruction.

If the context expires, the mailbox returns no context. Process death also
removes the context.

## Non-goals

This contract does not:
- modify the Book repository;
- authenticate a differently signed Book APK;
- persist textbook source text in MyGPT;
- grant Book control over provider/model/persona settings;
- grant Book UI automation, screen capture, Accessibility or overlay access;
- make Book source text trusted model instructions.

## Current acceptance status

Code contract only. Companion V2 and Book have not yet been jointly signed and
device-tested. GitHub hosted Actions are currently failing before runner
allocation, so exact-head Android execution remains pending.


## Freshness inside llama.cpp multi-turn history

llama.cpp's Android runtime retains KV/chat history across turns. Therefore
Companion V2 sends a Book state block on **every** user turn:

- fresh context: `"status":"fresh"`, including session, sequence,
  captured/expires timestamps and source identity;
- no current context: `{"status":"unavailable"}`.

The system prompt instructs the local model that only the current turn's
`status=fresh` block may be treated as current Book context. Earlier Book
blocks remain historical conversation data only. This prevents an expired or
cleared context from silently remaining the current study source merely because
llama.cpp retains prior KV state.
