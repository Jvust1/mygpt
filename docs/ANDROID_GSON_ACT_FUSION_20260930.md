# Gson strict JSON completes the Android AIRI reply path

Base: speech/cancellation PR #38, `87d60caa78a0773bc1dd28782ca1aeca8dbe1280`.

## Reproduced gap

The inherited Android `AiriActEmotionParser.java` failed compilation with **22
syntax errors** from over-escaped quote literals. Even apart from compilation,
regex-only payload extraction did not enforce the reviewed Python boundary for
quoted terminators, truncated control syntax, duplicate keys and invalid JSON.

The existing Android workflow's Java job was guarded by `Jvust/mygpt`, so it could
be skipped in the current `Jvust1/mygpt` repository. Activating the real smoke gate
also exposed a pre-existing test error: a 200×310 rectangle center was called an
equal-distance tie. The fixture now uses a square for the tie and separately
asserts the rectangle's correctly closer horizontal side. Runtime drag behavior
was not changed to satisfy the mistaken assertion.

## Live app path

`CompanionV2Activity.sendMessage` calls this same shared parser after
`local.generate`, then uses its clean text for conversation storage and TTS and
its emotion for `characterRuntime.showEmotion`. The local-LLM activity and
`OnDeviceCompanionBrain` facade also call it. This replaces the existing broken
parser; no parallel optional adapter or alternate app flow is added.

Gson **2.14.0** (24,236-star, Apache-2.0) supplies strict streaming JSON decoding.
All four Gradle consumers are pinned, the 313 KB jar is hash-verified, and full
Gson/AIRI licenses are included in app assets. Exact source identities and the
Android reflection caveat are documented in `third_party/gson/`.

## Preserved/hardened semantics

- Existing Result fields and emotion vocabulary remain compatible with callers
- Quote/escape-aware envelope boundaries; malformed and truncated ACT syntax
  never becomes visible text, conversation history or speech
- Last valid emotion wins; unknown/invalid markers do not reset a valid prior hint
- Gson STRICT mode, full document consumption, duplicate-key rejection at every
  level, finite floating values and Unicode scalar validation
- 768 UTF-8 bytes per JSON payload; depth 24; 16,000 UTF-16 units per Java reply
- String/object emotion forms, Unicode name trimming and intensity clamping
- Huge JSON integers remain valid and clamp appropriately; nonfinite exponent
  results are rejected as in the Python boundary
- No tool, delay, model selection or permission operation can be encoded here

Java retains its existing UTF-16-unit reply ceiling, while Python counts Unicode
code points; parity cases are within both input ceilings. Java's existing float
intensity field is compared with a 1e-6 numerical tolerance.

## Verification and limits

- **18 Java smoke entrypoints pass locally**, including actual on-device facade
  generation → parser → reply integration with quoted/truncated/marker-only cases
- **327 synthetic golden cases** match the reviewed Python AIRI parser, including
  deterministic randomized payloads, byte/depth limits and all opener truncations
- Independent review reran all 18 entrypoints and 327 fixtures, plus 239 extra
  differential probes. It caught the fourth shared-source consumer (voice app);
  dependency/notices and a discovery-based consumer guard now include it
- Actual Maven jar bytes, source/license blobs, Java 8 base class files, Gradle
  consumers and license assets are checked; no new large environment is installed
- Local runtime is Java 21 with compiler module, using `-source 8 -target 8`; its
  stripped image lacks `--release 8` support, so this alone is not a Java 8 API check
- The hosted gate now targets the current repository, runs actual Java 8, and
  separately compiles with Java 17 `--release 8`; both execute all smoke cases
- The separate Android APK job remains outside this candidate's enabled scope

This verifies the shared Java boundary and its real Gson dependency. It does not
claim an APK build, JNI/model inference, physical device behavior, microphone/TTS
output, skin asset licensing or end-user acceptance. No private models/skin assets
are downloaded or published. Python runtime behavior is unchanged.

## Reproduction

```sh
python android_spike/tools/verify_gson_artifact.py /path/to/gson-2.14.0.jar
# The workflow lists the complete Java compile/run manifest.
# Regenerate the checked-in synthetic oracle using the pinned Brain environment:
python android_spike/tools/generate_act_fixtures.py
```

The workflow's artifact fetch is fixed to Maven Central, version 2.14.0 and its
committed SHA-256. Generated class files and the downloaded jar are not source
artifacts and must not be committed.
