# Android integration spike: Book → coordinator → Live cue

This contains a dependency-free Java 8 core and a small Android device test host. The host builds a **synthetic debug APK** to exercise the coordinator. It is not an authenticated Book integration, a Live renderer, or a model/voice implementation. It contains no imported upstream code or assets.

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

## Android test host

`android_spike/app` is a separate package (`dev.mygpt.spike`) with no permissions, no internet access and no automatic model calls. Every button says it simulates Book activity; its authority callback is an in-memory test double that can be revoked. The visible character area is text, not a Live skin. Leaving the Activity foreground or locking the device clears the session and this-session supervision opt-in. A 30-second synthetic event deadline also clears a visible cue without waiting for another button press.

With Android SDK 35, JDK 17 and Gradle 8.13 installed:

```sh
gradle -p android_spike :app:assembleDebug --no-daemon
```

The debug APK appears at `android_spike/app/build/outputs/apk/debug/app-debug.apk`. CI builds and uploads it as a short-lived test artifact. Do not use this package to assess actual Book transport, Live WPK animation, model teaching quality, or cross-app overlays.
