# Official Ollama async request fusion

Base: Pipecat runtime PR #32, `47ede8ead6a4c4875ab3b431831875f18353bd8e`.

## Gap closed

The old `OllamaResponder` used `asyncio.to_thread(urlopen)`. Cancelling the voice
turn stopped waiting for its result, but the blocking HTTP request could keep
running on a worker thread. The existing provider is now directly adapted from
the official Ollama Python async request/stream lifecycle. Cancellation closes
the actual in-flight HTTP connection rather than leaving that thread behind.

Upstream `ollama/ollama-python` had **10,563 stars** at the 2026-09-30 18:47 UTC
GitHub check. Exact source revision, blob identity, MIT license and copyright
are retained under `third_party/ollama-python/`.

## Existing entry points preserved

Both `brain/scripts/chat_local_ollama.py` and
`brain/scripts/serve_companion_ollama.py` continue constructing `OllamaResponder`
and `CompanionChatRuntime`. No new provider adapter or launcher is introduced.

The now-exercised cancellation path is:

`real Pipecat InterruptionFrame → CompanionChatRuntime cancellation → Ollama async HTTP context closes → owned loopback server observes EOF`

No reply is spoken or committed for the cancelled exchange. The AIRI visible
text/emotion split, persona authority and native HTTP replay behavior remain.

## Boundaries

- Only `http://127.0.0.1:11434/api/chat` is accepted
- Redirects are rejected, even if they point to another loopback URL
- `OLLAMA_HOST`, `OLLAMA_API_KEY`, environment proxies and `.netrc` cannot change
  the destination or add authentication
- Response body is bounded to 1,000,000 bytes, with one total request deadline
- Content encoding must be identity; no compressed-body expansion
- Strict JSON rejects duplicate keys/nonfinite numbers; provider error bodies
  are not exposed in the runtime error text
- No request/response payload is logged by the adapter

## Verification

Local results:

- Python 3.12.14 strict Brain suite: **595 passed, 0 failed, 0 skipped**
- Clean Python 3.13.5 strict Brain suite: **595/0/0**
- Second Python 3.13.5 environment installed with the regenerated hash lock:
  **595/0/0**
- Real Pipecat integration suite: **8 passed**, including the full cancellation
  path through the actual async HTTP transport
- Loopback TCP cancellation before headers and during partial body: pass
- Dependency consistency and launcher doctor: pass

Tests use synthetic request content and owned ephemeral loopback servers. Only
the test transport redirects the fixed production URL to its owned local port;
production endpoint validation is unchanged. No real Ollama model, paid/cloud
provider, microphone or audio device is used. Closing the client connection is
verified; actual model-server compute cancellation/quality needs device evidence.

The Linux/Python 3.13 hash lock contains the same existing package versions and
hashes plus exactly three additional packages: httpx/httpcore/certifi. It was
generated from a real clean install report and hash-reinstalled, not fabricated.
Existing focused CI now installs the package's declared test dependencies so
it cannot silently omit the new runtime HTTP dependency.

Hosted acceptance must be checked at the exact published head. This candidate
does not open a LAN endpoint or complete the phone/tablet deployment.
