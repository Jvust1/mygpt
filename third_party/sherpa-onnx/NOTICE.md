# sherpa-onnx attribution

Upstream: https://github.com/k2-fsa/sherpa-onnx  
Pinned upstream commit: `040afe360a38e25daaa325ce8889abf93ea02609`  
License: Apache-2.0

MyGPT directly adapts the Android microphone capture pattern from:

- `android/SherpaOnnxJavaDemo/app/src/main/java/com/k2fsa/sherpa/onnx/service/SpeechSherpaRecognitionService.java`

Local derived/modified files:

- `android_spike/src/main/java/dev/mygpt/spike/VoicePcm.java`
- `android_spike/app/src/main/java/dev/mygpt/spike/VoiceCaptureSession.java`

Material changes in MyGPT:

- the sherpa recognizer/model initialization is intentionally not copied yet;
- capture is isolated behind a listener interface so sherpa-onnx, whisper.cpp,
  or another local ASR engine can be benchmarked later;
- the session never requests permission by itself;
- no audio is written to disk;
- the caller must obtain RECORD_AUDIO permission through an explicit user action;
- lifecycle stop/release is idempotent and bounded;
- PCM normalization is covered by a Java-8 smoke test.

The upstream Apache-2.0 license is reproduced in
`third_party/sherpa-onnx/LICENSE`.


Additional TTS adaptation:
- `android_voice_spike/app/src/main/java/dev/mygpt/voicespike/SherpaMeloTtsModelInstaller.java`
- `android_voice_spike/app/src/main/java/dev/mygpt/voicespike/SherpaMeloTtsEngine.java`

The TTS path follows sherpa-onnx's Android `OfflineTts` + `AudioTrack`
streaming pattern for the `vits-melo-tts-zh_en` model. MyGPT keeps model
weights external, preserves README/LICENSE from imported model ZIPs when
present, streams samples directly to AudioTrack, and does not save generated
speech audio to disk.
