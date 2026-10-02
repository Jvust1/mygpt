# Android TTS completion ownership

Base: voice receipt recovery PR #46,
`1ad4cd148254752a9ae4b0cf5adfcbe826f53748`.
This hardens the existing voice flow, not a new upstream/framework adoption.

## Missing behavior and failing regression

`CompanionV2Activity.speakReply` guarded success by an epoch but left failure
unguarded. An older failure could call `stopTtsPlayback` and overwrite a newer
utterance's status. New utterances also reused the same epoch until a stop/toggle.

Completion ownership was isolated into the production `VoiceOutputCompletion`
helper and wired into those exact Activity callbacks. With the previous
unguarded failure branch retained, the new JVM regression failed:
`stale failure must not stop the newer output or replace its status`.
After the ownership fix, that same production-helper regression passes.
This is a JVM callback/effect reproduction, not an Android Activity/AudioTrack run.

## Current ownership rule

- Every utterance gets a fresh in-memory object lease, without numeric wraparound
- Stop and toggle invalidate any current lease; destroy closes the owner permanently
- Both success and failure callbacks must own the current lease before changing status or stopping output
- Completion consumes the lease before its callback, preventing duplicate effects
- Reentrant invalidation/new utterance and throwing callbacks do not erase a newer lease
- Synchronous callback admission and invalidation are serialized; an already-admitted
  callback may finish before invalidation acknowledges, but no old callback is admitted afterward

The production Activity uses the helper for creation, IO preflight, both completion
callbacks, stop/toggle and destroy. A source-wiring regression catches restoration
of the old unguarded failure path. The backend, engine settings and permissions
are unchanged.

This reuses the already-integrated Pipecat turn-invalidation pattern in Java.
The existing source pin is `49dea682fb84bfc515d881d00dfeaaa9e9f1075f`, BSD-2-Clause;
Pipecat had 16,098 stars at the 2026-09-30 check. Exact full license and notices
now accompany the shared helper in all four direct/inherited Android consumers.
There is no Android dependency on the Python SDK.

## Verification and limits

The actual JVM helper tests out-of-order success/failure, stop/toggle invalidation,
repeated cancellation, independent owners, reentrant completion, callback errors,
atomic admitted-callback ordering and destruction. Synthetic callback effects
stand in for `stopTtsPlayback` and status writes. The shared runner has 22 Java
entrypoints; root Python 65 tests pass, including production-wiring guards.

Local Java 21 source/target-only evidence is distinct from the hosted Java 8/17
API/runtime gates. Kotlin/Android Activity compilation, native engine admission,
AudioTrack/JNI cancellation, audible playback and physical devices are not proven
by these tests. The existing preflight-to-engine-call timing and native backend
lifetime remain outside this completion-only change; no new physical cancellation
or exactly-once audio guarantee is claimed.
