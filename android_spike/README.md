# Android integration spike: Book → coordinator → Live cue

This contains a dependency-free Java 8 core and a small Android device test host. The host builds a **synthetic debug APK** to exercise the coordinator plus a private Spine renderer for selected Live skin 3714430278. It is not an authenticated Book integration or a model/voice implementation. The skin bytes stay external and are selected through Android SAF; the APK contains only the renderer/runtime needed for private evaluation.

The host must implement `VerifiedBookPort` using Book's actual local authority and short-lived lease checks before forwarding a projected event. The current Book lease receiver (`brain/mygpt_brain/book_bridge.py`) authenticates explicit selected content for a TestModel reply; it does **not** yet emit this study-event stream. This spike does not infer an event from a screenshot or accept arbitrary HTTP JSON as Book authority. Only opaque `book-lease://` references enter the coordinator; text, notes and answers stay in Book.

`CharacterRuntime` receives `QUIET`, `PAUSED`, `NEEDS_INPUT`, or `GENTLE_CHECK_IN`. The current Android candidate maps those cues into Spine animations for Live skin 3714430278 while Live remains the asset authority. Jonah remains only a historical UI interaction prototype.

The coordinator starts quiet. Practice error prompts require a local user opt-in and a ten-minute cooldown. A help request changes the cue but does not call a model; the host must use the existing explicit, revocable Book lease and separate model consent path for content. Pausing, expiry, revocation, session/epoch mismatch, replay and sequence gaps fail closed. No OS activity, microphone, overlay, cloud sync, or provider request is performed.

Run the deterministic boundary smoke with a JDK 8+:

```sh
mkdir -p android_spike/build/classes
javac --release 8 -d android_spike/build/classes \
  android_spike/src/main/java/dev/mygpt/spike/CompanionCoordinator.java \
  android_spike/src/test/java/dev/mygpt/spike/CompanionCoordinatorSmoke.java
java -cp android_spike/build/classes dev.mygpt.spike.CompanionCoordinatorSmoke
```

Next implementation gate: in a Book Android and mygpt Android test host, prove the exact Book producer identity and revocation path, then bind a Live `CharacterRuntime` implementation and test lifecycle/permission behavior on a device. Local chat and voice engines need separate benchmarks and user consent gates. Do not call this code production transport or a verified user-device build.

## Android test host

`android_spike/app` is a separate package (`dev.mygpt.spike`) with no permissions, no internet access and no automatic model calls. Every button says it simulates Book activity; its authority callback is an in-memory test double that can be revoked. The host includes a GPU-backed Spine surface for 3714430278; the separate text label remains only as a readable cue fallback. Leaving the Activity foreground or locking the device clears the session and this-session supervision opt-in. A 30-second synthetic event deadline also clears a visible cue without waiting for another button press.

With Android SDK 35, JDK 17 and Gradle 8.13 installed:

```sh
gradle -p android_spike :app:assembleDebug --no-daemon
```

The debug APK appears at `android_spike/app/build/outputs/apk/debug/app-debug.apk`. CI builds and uploads it as a short-lived test artifact. Do not use this package to assess actual Book transport, Live WPK animation, model teaching quality, or cross-app overlays.

## 3714430278 Spine renderer implementation

The decrypted runtime package `3714430278.zip` has been inspected directly. Its pinned SHA-256 is `eb6eddc96172c03fe4d0dd4dd8a68180ce832aeb82ae07f7f82175fed57bc23f`; the Android importer verifies this exact identity before extraction. It contains 13 flat entries and is a **Spine 4.1.20** skeletal package, not a Cubism/Live2D model.

Primary runtime files:
- `model.json` — Live package controller/motion map.
- `skeleton.bin` — Spine binary skeleton exported with version `4.1.20`.
- `c610_00.atlas` — texture atlas with premultiplied alpha.
- `c610_00.png` — atlas texture.
- `lpk_files.json` — package identity and decrypted-name mapping.

The first implemented Android renderer uses `spine-libgdx:4.1.0` and libGDX 1.10.0. The Activity uses Android's Storage Access Framework to let the user select the already-decrypted ZIP. The app stores only a persisted URI grant plus a verified local extraction in app-private storage; no broad storage permission is requested.

Before rendering, `SpinePackageLayout` rejects path traversal/nested entries, duplicate required files, oversized decompression, wrong skin ID, missing required resources, and non-4.1 skeleton versions. The renderer then loads `skeleton.bin` + `c610_00.atlas` and displays the skeleton on a GPU-backed libGDX surface.

Current cue mapping:
- `QUIET` → `idle`
- `PAUSED` → freeze current animation
- `NEEDS_INPUT` → `smile` (fallback `idle`)
- `GENTLE_CHECK_IN` → `action` (fallback `idle`)

The decrypted package also advertises tap motions including `etc`, `no`, `pain`, `sad`, `special`, and `surprise`; these remain available for later conversation/emotion mapping.

**Verification boundary:** this refresh branch is derived from PR #10 latest head `3ad7d14a5446a3c0c6f23aa7e00703a3535f4e7e`. PR #10's later state/evaluation/handoff updates are preserved. The refresh adds the Spine runtime license notice, exact package metadata and primary/backup skin registry; it is not called refresh-CI-verified or device-verified until this branch's workflow and a physical Android device both pass. Book events are still synthetic. Production redistribution is separately gated by the Spine Runtimes license.


### Exact selected package identity

- ZIP SHA-256: `eb6eddc96172c03fe4d0dd4dd8a68180ce832aeb82ae07f7f82175fed57bc23f`
- ZIP bytes: 12,342,220
- Uncompressed bytes: 12,340,902
- Entries: 13
- ZIP CRC: PASS
- Spine binary: 4.1.20
- Runtime: spine-libgdx 4.1.0 + libGDX 1.10.0
- First Android ABI: arm64-v8a

The importer verifies the exact ZIP SHA-256 before extraction. The debug APK bundles the matching Spine runtime license notice, while distribution remains separately license-gated.

### PR #10 latest baseline

Before this refresh, PR #10 exact-head commit `a076be06e2e4c3eeecdab3f1860143771bfef0d3` passed workflow run `36449517394`: Java 8 package-layout smoke, Android `:app:assembleDebug`, and `lib/arm64-v8a/libgdx.so` payload verification all passed. Its APK SHA-256 is `d7eea8e80e1d782e0ff0e8f350d6064b9f7b415f595af480c03e22667d7b56c9`. That baseline did not yet bundle the Spine runtime license notice; this refresh adds it without reverting PR #10's later documentation/governance updates.
