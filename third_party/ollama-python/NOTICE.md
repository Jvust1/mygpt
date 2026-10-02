# Official Ollama Python async lifecycle adoption

Upstream: https://github.com/ollama/ollama-python

Pinned source: `8785556559ec1d045d27a1ba9d9cc7330c3d3cb1`

GitHub API eligibility checked 2026-09-30 18:47 UTC: **10,563 stars**, MIT.

Copyright (c) Ollama. Full MIT license retained in `LICENSE`, matching upstream
Git blob `8e3dc978a7ca8c53f56bbedc5b558116140fc02e`.

## Source and derived implementation

Source: [`ollama/_client.py`](https://github.com/ollama/ollama-python/blob/8785556559ec1d045d27a1ba9d9cc7330c3d3cb1/ollama/_client.py),
Git blob `13dd6441674289dca4befcfdd890eb4a5ceae94f`.

`AsyncClient._request`, `_request_raw`, `chat`, and asynchronous client closing
provide the directly adapted context-managed HTTP lifecycle. Local derived file:
`brain/mygpt_brain/providers.py` (`OllamaResponder`).

MyGPT changes:

- Replace the existing blocking `to_thread(urlopen)` call in place
- Keep the fixed loopback `/api/chat` endpoint and `stream=False` wire protocol
- Read the HTTP body incrementally under a hard byte cap and total deadline
- Close stream/client on cancellation, timeout and error
- Disable redirects, environment proxy/.netrc settings, and Ollama host/key
  inheritance; do not copy the upstream cloud/web-search/authentication features
- Reject compressed bodies and ambiguous/malformed JSON before returning text
- Sanitize errors rather than copying provider response/error bodies
- Reuse exact `httpx==0.28.1`, without adding a second Ollama provider or requiring
  the entire Ollama Python SDK

The HTTPX dependency and its dependencies retain their own package licenses.
The existing Linux/Python 3.13 hash lock was regenerated from a real clean
installation while preserving every existing version/hash; only certifi,
httpcore and httpx were added, then reinstalled with hashes in a second clean
environment.
