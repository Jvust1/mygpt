# Gson strict streaming integration

Upstream: https://github.com/google/gson

- Version **2.14.0**, release commit `3ff35d6269894901ab8006258395aafc4b9765cd`
- Eligibility checked 2026-09-30 UTC: **24,236 stars**, not archived
- License **Apache-2.0**, exact upstream LICENSE retained here
- Copyright 2008 Google Inc.; JsonReader copyright (C) 2010 Google Inc.
- JsonReader Git blob: `e908c79d8540f476c8f694f5caf9c0a7fa2c637f`
- Strictness Git blob: `461f1c8d0083b3c4dd99a8a006f279970b235bbe`
- LICENSE Git blob: `d645695673349e3947e8e5ae42332d0ac3164cd7`

The exact 313,604-byte Maven jar has SHA-256
`2cbd119bf1961c28788310963dc80ba65f58cdeec1dd139c8bdb1240faa2c36f`, independently
matched to Maven Central's `.sha256`. Base classes use Java 8 class-file version
52. The jar is not vendored into this repository; Gradle pins the dependency and
the hosted Java gate verifies its complete bytes before executing tests.
`PROVENANCE.json` records the immutable identities and artifact URL.

## Actual use

The existing Android `AiriActEmotionParser` now invokes Gson `JsonReader` with
`Strictness.STRICT` and a nesting limit. A bounded application traversal rejects
duplicate keys, nonfinite decimal/exponent numbers, lone Unicode surrogates,
non-object roots and trailing data. No reflective POJO mapping is used.

This is the parser already called by Companion V2 after local model generation
and before durable conversation storage, character emotion and speech. The
on-device brain facade and local-LLM activity also invoke it. All four Gradle
consumers of the shared Java source declare the exact dependency.

AIRI still supplies presentation protocol/normalization semantics (MIT). Gson
supplies the actual mature JSON decoder, not an unused adapter or another server.
MyGPT's quote-aware scanner and 768-byte JSON/16,000 UTF-16-unit reply limits are
application boundaries. Complete invalid and truncated control envelopes are
hidden from visible text; the last valid emotion wins. Nothing can execute an
action or change authorization.

## Android qualification and notices

Pinned upstream documentation requires Java 8 and Android API 21; current
consumers require API 24, 28 or 33. Upstream warns against Gson's reflective object
mapping on Android because shrinking/obfuscation can break it. This integration
uses only the streaming API, not reflective serialization or private-field access.
That distinction is deliberate; it is not a general recommendation to use Gson
reflection on Android.

Full Gson and AIRI license/attribution assets are bundled for all three direct app source
sets. Companion V2 already inherits the shared `android_spike` assets. No private
skin/model assets are copied, and no APK distribution is authorized by this notice.

Sources:
- https://github.com/google/gson/blob/3ff35d6269894901ab8006258395aafc4b9765cd/README.md
- https://github.com/google/gson/blob/3ff35d6269894901ab8006258395aafc4b9765cd/gson/src/main/java/com/google/gson/stream/JsonReader.java
- https://github.com/google/gson/blob/3ff35d6269894901ab8006258395aafc4b9765cd/gson/src/main/java/com/google/gson/Strictness.java
- https://github.com/google/gson/blob/3ff35d6269894901ab8006258395aafc4b9765cd/LICENSE
