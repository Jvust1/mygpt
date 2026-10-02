# Desktop text-chat vertical slice · 2026-10-02

Status: implementation candidate; new exact-head hosted Windows acceptance is
required. This document does not inherit a prior checkpoint's CI or claim a
real-model/user-device pass.

## Scope and reuse

The existing desktop model form now calls `CompanionChatRuntime`,
`OllamaResponder`, and `ChatSessionStore`. There is no second chat demo or
replacement persistence engine. The data directory contains `data/chat.sqlite3`;
its server-owned `desktop-local-chat-v1` session does not depend on browser
storage, a cookie's value, or the ephemeral loopback port. The existing desktop
persona instructions are constructed with `CompanionPersona`; no unbundled
persona JSON resource is required by the frozen executable.

The provider still accepts only `http://127.0.0.1:<validated integer>/api/chat`.
Proxy/environment credentials, redirects and remote URLs remain disabled.
The shared responder keeps its original default payload: `keep_alive` and
`options.num_predict` are omitted unless explicitly configured. Only Desktop
passes its existing unload policy (`keep_alive="0"`) and 2,048-token output
budget; Companion/voice callers do not inherit either setting. Optional values
are strictly validated before any request.
The user explicitly chooses an already installed local model and port. Input is
limited to 4,000 characters on both surfaces, with rejection rather than silent
truncation. The one-turn consent explains that recent conversation messages are
sent too. No model is installed, downloaded or automatically selected.

## Persistence and failure contract

1. A deliberate UI send creates a request UUID and snapshots the current input.
   Its dispatch fingerprint binds the UUID, text, session/persona, model and port.
2. An additive `chat_dispatch_claims` table in the existing SQLite database
   commits that request/fingerprint and a random lifecycle generation before provider contact.
   Admission/dispatch/completion require that generation to remain current, so an
   explicit deletion even before the history snapshot revokes the old attempt. It stores no extra
   transcript copy. A failure to save the claim prevents the provider call.
3. The existing runtime validates/normalizes a reply and atomically commits the
   user message, assistant message and successful receipt. Only that receipt
   permits the UI to display “saved”. A failed transaction preserves the draft
   and leaves no partially committed exchange.
4. Same UUID and same fingerprint with a successful receipt replays the stored
   result without inference. A conflicting fingerprint is rejected.
5. A claim without a receipt is an unknown outcome, including interruption after
   claim but before dispatch. That UUID never dispatches again, even after restart.
   The user may read history or deliberately start a new turn with a new UUID;
   the app does not automatically retry or regenerate. This is not a claim of
   provider-side exactly-once execution or guaranteed model cancellation.
6. One asyncio loop and runtime live for the desktop service's lifetime.
   A service-level slot rejects overlapping sends. Shutdown revokes completion
   under the same guard used around the existing transactional completion,
   cancels the async provider, joins the loop and closes the stores. Runtime
   deadlines reject late replies before commit.

The dispatch journal is additive to schema 2 and retains only durable request
identities/hashes. Existing rows are not rewritten or automatically deleted; successful history
and claims have no TTL. The existing explicit `delete_session` operation removes
that session’s claims together with messages/receipts, increments the deletion
epoch even for a claim-only session, and permits a new lifecycle to reuse IDs.
No deletion UI or automatic deletion is added. Total on-disk history is intentionally not bounded. The
existing runtime's transient compacted-ID expansion remains O(history); this
slice does not claim to fix that separate limitation. No real user database was
migrated during development. Do not run older/mixed versions against this data
or downgrade in place.

## Read-only recovery and UI

`GET /desktop-api/chat-history` uses the same Cookie, Host, Origin,
Sec-Fetch-Site and client-header protections as desktop state. It is restricted
to the server-owned desktop session/persona. Each keyset page returns at most
40 saved user/assistant messages, with a positive ordinal cursor for older
messages. System authority is not returned. Pages never prune the database.

Startup, reload and “read-only refresh” only read the database. A fresh browser
context and a changed loopback origin do not alter session identity. A response
epoch prevents an older asynchronous history read from replacing a newer one.
User/provider text is assigned through `textContent`; HTML is never executed.
Consent clears after every attempt and whenever prompt/model/port input changes.

The existing notes, goals, timer and import/export stay separate. Their backup
UI explicitly says it does not include chat history. Chat is not automatically
written to notes or the long-term memory store. No microphone, speech, capture,
cloud sync, Book integration, deletion or retention policy is added.

## Verification contract

Local tests use synthetic HTTP providers only. They cover:

- Two exact-text turns, prior Q/A in the second provider payload, SQLite pairs
  and receipts, and restart recovery after the synthetic provider stops
- Actual HTTP connection loss after commit and before response, followed by
  same-UUID replay with exactly one provider dispatch and one stored pair
- Claim-write failure before dispatch, interruption after claim, provider
  failure, an SQLite trigger abort between user and assistant inserts, late
  replies, shutdown cancellation, and same-ID payload/configuration conflicts
- Protected/paginated history, complete retained DB history, 4,000-character
  rejection, UI duplicate clicks, stale history responses, safe text rendering,
  and no automatic inference on load or refresh

The Windows build script requires one exact frozen EXE and Microsoft Edge;
it cannot fall back to another browser for this new gate. Earlier runs must be
judged by their actual recorded browser, not by the old fallback's existence.
The native script submits two synthetic turns through the real form, verifies
actual SQLite pairs/receipts and one duplicate replay, closes the EXE, stops the
synthetic provider, and restarts the same EXE/data directory in a fresh browser
context on a new port. It checks verbatim history with zero chat POSTs and zero
attempted connections to the stopped provider. Existing math, notes, timer,
backup and shutdown checks remain required. Evidence stays synthetic; native
binaries, databases and user data are not published by CI.

Real Ollama/model execution requires separate authorization and pinned runtime,
model, resource/disk and isolation checks. A synthetic provider pass establishes
wiring and recovery, not real-model quality, latency, hardware suitability,
Windows user-device acceptance, Android parity or release readiness.
