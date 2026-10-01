# Coherent companion source checkpoint

Implementation base: [PR #47](https://github.com/Jvust1/mygpt/pull/47),
`ea4e529b56f1967bfd1a98e1a1367947977dc055`.
This checkpoint adds no runtime feature, upstream, dependency or permission.
It refreshes recoverable source/evidence after the reviewed integration stack.

## Included working paths

- AIRI reply text/emotion parsing and paired history in Python and Android
- Pipecat response/TTS framing, interruption, conservative speech presentation,
  fresh voice events across restart and explicit silent receipt recovery
- Fixed-endpoint Ollama async HTTP lifecycle with bounded responses/deadlines
- scikit-learn-derived lexical memory, including Unicode SQL candidate preprocessing
  and the actual Android memory-search call path
- Strict Gson ACT decoding used by the Android reply pipeline
- SQLite persistence/receipt replay, native authorization completion guards,
  bounded Book context and valid-Unicode prompt clipping
- Android TTS completion leases that reject stale success/failure side effects

All immutable source identities and licenses remain in `third_party/` and the
relevant Android assets. The current archive includes all supported tracked
regular files plus the generated manifest. Unsupported or unsafe files still
reject packaging instead of being silently omitted.

## One exact-head checkpoint

The existing aggregate workflow now also calls the existing source-recovery
workflow at the same immutable push SHA. The source job builds twice, compares
bytes, verifies every member, extracts into a new directory, and reruns recovered
Python/JavaScript/Java and loopback startup/input probes.

The implementation-base aggregate was green with:

- Python 3.13: 724 strict + 48 actual-upstream/story cases, zero failures/skips
- Root Python: 65; JavaScript: 66
- Java 8 and Java 17 --release 8: 22 entrypoints each
- Included Java fixtures/projections: 327 Gson, 109 sklearn, 128 AIRI,
  3520 history budgets, 1288 Book Unicode budgets and completion ownership

The new checkpoint's terminal run, actual source file count, archive bytes,
external SHA-256 and artifact link belong in its PR evidence. They are not guessed
or self-referenced in this source document. A private durable copy can retain the
verified ZIP and a short handoff before the three-day CI artifact expires.

## Recovery is source-level

The archive is not an APK, model package or offline dependency-complete app.
Model weights, private skin files, recordings, personal chat databases and
credentials are excluded. The two existing llama.cpp/sherpa-onnx Gitlinks are
exact external references, not bundled or fetched source trees. The already-tracked
Gradle wrapper is the sole hash-checked bootstrap-jar exception.

The package retains a trusted external SHA-256 requirement. Manifest/member
hashes detect damage; the embedded commit value is not an authenticity signature.
Verify the hash before extraction. See `FUSION_SOURCE_RECOVERY_20260930.md` for
source scope and the verification commands.

## Explicit remaining gates

- No actual Android Activity/Kotlin/APK/JNI/device, microphone or audible-model acceptance
- Model replies/audio generation in the integration stories are synthetic
- SQLite receipt replay is data recovery, not an audio-delivery acknowledgment;
  it does not promise exactly-once physical playback
- Android completion leases guard synchronous callbacks, not native backend
  admission or AudioTrack lifetime/cancellation
- Noncooperative Python callbacks can retain a runtime lock past a deadline;
  eventual stale output rejection is not hard compute cancellation
- Lexical candidate windows remain bounded and may miss older relevant records

The reviewed changes remain draft. Main is unchanged; this checkpoint does not
merge, deploy, accept SDK licenses or broaden data/model access.
