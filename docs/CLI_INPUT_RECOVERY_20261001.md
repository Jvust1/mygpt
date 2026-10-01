# Local companion CLI input recovery

Base: [PR #53](https://github.com/Jvust1/mygpt/pull/53),
`fc65a4da99a7ee2fe4a38b166fcfdca2d19127ff`.

The actual `chat_local_ollama.py` entry point built memory/chat contracts outside
recoverable input handlers. A 2001-character `:remember` or 4001-character chat
raised an uncaught validation error and exited before a following valid command.
Invalid Unicode also failed downstream, and a bare `:remember` was sent as chat
instead of being treated as an empty explicit-memory command.

## Bounded fix

Catch only Pydantic validation/Unicode errors while constructing bounded input.
Validate UTF-8 after the existing length-constrained model accepts the string;
rejected text is not echoed. Continue the same loop so the user can correct it.
Bare/empty `:remember` reports empty memory text without model invocation.

The SQLite write remains outside that catch. Success is printed only after
`memory.put` returns; actual storage failures and operation-time interrupts are
not reclassified as bad input. Existing provider-error handling is unchanged.
There is no new command, provider, dependency, persistence schema or limit.

## Evidence

Fourteen tests execute the real CLI main loop, actual stores/runtime and actual
Ollama adapter with synthetic `httpx.MockTransport` replies. Six regressions
fail on the old code. Coverage includes:

- Overlong/malformed/empty memory command followed by a valid persistent write
- Overlong/malformed chat followed by one valid provider call and clean ACT reply
- Existing exact limits of 2000 memory and 4000 chat characters
- EOF/Ctrl+C at the prompt exits while preserving earlier committed memory
- Explicit update/delete/history semantics, namespace scope and recall after delete
- Actual SQLite audit-trigger failure rolls back without a false success message
- KeyboardInterrupt, SystemExit and OSError during a write propagate without a
  successful-memory confirmation

`:forget` still removes active memory while retaining its audit history; it is
not changed into a purge. Chat/context data is not implicitly turned into memory.
Startup/configuration and unexpected runtime/storage failures retain their
existing behavior; this is not blanket exception suppression.

This hardens an existing complete Mem0/AIRI/Ollama input→memory→response path,
not another upstream adoption. All pinned sources, licenses and the dependency
lock remain unchanged. Model HTTP is synthetic; no installed/live model,
Android/device, microphone or audible playback acceptance is implied.
