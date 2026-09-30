# scikit-learn lexical recall fused into companion chat

Base: native HTTP authorization PR #35, `490ac0437b49b4e7ef752a02d3454cf7e7b5b6f6`.

## Reproduced user-path gap

The native chat contract accepts up to 4000 characters, but its always-invoked
memory search rejected queries longer than 500. A valid 600-character question
failed before the responder was called. Existing memory recall also returned
keyword hits by recency alone, so a newer generic hit could displace an older
more relevant preference.

## Actual mature code reuse

The existing search now calls a standard-library sparse port of scikit-learn's
word-boundary character n-gram tokenizer, smoothed TF-IDF/sublinear term frequency,
L2 normalization and cosine similarity. Upstream had **67,434 stars** on
2026-09-30. The immutable source blobs, adaptations, BSD-3-Clause license and
copyright are retained in `third_party/scikit-learn/`.

No second memory store, optional adapter, embedding server or model download is
introduced. The port runs through the existing `CompanionChatRuntime.send` path
used by native HTTP and voice.

## Behavior and boundaries

- Preserve the full original question for the model and durable chat history
- Use at most eight 500-character candidate windows, at most 12 SQL keywords per
  window and 64 deduplicated records from the requested persona namespace
- Fit vocabulary/IDF on candidate memory text and tags, then score the full query
- Rank positive evidence by relevance, then newest update and stable memory ID
- Return no recalled memory for punctuation-only/no-match input, rather than
  silently falling back to recent private memory
- Keep memory placement as lower-authority application data, never persona rules
- Preserve explicit memory write/update/delete and audit behavior; no implicit
  transcript-to-memory writes, persistent fitted index or schema migration

This is lexical reranking of a bounded candidate set. It is not semantic search
or exhaustive corpus retrieval. SQL candidate selection is still keyword-based
and can miss a relevant older record beyond its per-window budget, or a term
outside its 12-keyword selection. There is no model-quality or device acceptance
claim. Chinese/English synthetic cases validate mechanics, not personal-memory
relevance judgments. A synthetic worst-size scorer probe (64 × 2784-character
records and a 4000-character query) took about 0.62 seconds in this cloud
container; this is not a phone latency benchmark.

## Validation

- Full strict Brain: **643 passed, 0 failed, 0 skipped**, Python 3.12.14 and
  hash-installed Python 3.13.5
- Real scikit-learn 1.9.1 oracle: **9 passed**, including 25 deterministic
  randomized corpora and character-tokenizer equivalence; tolerance 1e-12
- Real Pipecat queue/TTS regression: **8 passed** (no real synthesis/device)
- Native HTTP regression: 600- and 4000-character requests reach the responder,
  retrieve a suffix-relevant memory, preserve full prompt/history and replay
- Independent review: strict 643 and focused 53 passed; 100 extra mixed-Unicode\n  randomized parity probes had maximum absolute error 1.78e-15\n- Root regression: **44 Python tests and 66 JavaScript tests passed**
- Source/license Git hashes checked against all three declared upstream blobs
- Production/Brain hash lock unchanged; sklearn is test-only

Reproduce with the pinned Brain SDK environment:

```sh
cd brain
python scripts/verify_integrations.py --output /tmp/mygpt-lexical-evidence
python -m pip install '.[test,integrations,lexical-test]'
python -m pytest -q lexical_tests
# With the separately pinned Pipecat extra installed:
python -m pytest -q realtime_tests
```

The dedicated lexical workflow installs the real upstream oracle. Existing
Brain acceptance keeps two clean hash-locked installs without sklearn, proving
that production recall does not need the heavy ML package.
