# Android integration spike: Book → coordinator → Live cue

This is a dependency-free Java 8 core intended for an Android host module. It is **not** an APK, an authenticated Book integration, a Live renderer, or a model/voice implementation. It contains no imported upstream code or assets.

The host must implement `VerifiedBookPort` using Book's actual local authority and short-lived lease checks before forwarding a projected event. The current Book lease receiver (`brain/mygpt_brain/book_bridge.py`) authenticates explicit selected content for a TestModel reply; it does **not** yet emit this study-event stream. This spike does not infer an event from a screenshot or accept arbitrary HTTP JSON as Book authority. Only opaque `book-lease://` references enter the coordinator; text, notes and answers stay in Book.

`CharacterRuntime` receives `QUIET`, `PAUSED`, `NEEDS_INPUT`, or `GENTLE_CHECK_IN`. A future Live-owned Android renderer maps these cues to a character and animation. The Live repository currently has no runtime contract or production assets to bind. Jonah remains a UI interaction prototype.

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
