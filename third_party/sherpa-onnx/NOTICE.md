# sherpa-onnx attribution

Upstream: https://github.com/k2-fsa/sherpa-onnx  
Pinned upstream commit: `040afe360a38e25daaa325ce8889abf93ea02609`  
License: Apache-2.0

MyGPT directly adapts the Android microphone capture pattern from:

- `android/SherpaOnnxJavaDemo/app/src/main/java/com/k2fsa/sherpa/onnx/service/SpeechSherpaRecognitionService.java`

Local derived/modified files:

- `android_spike/src/main/java/dev/mygpt/spike/VoicePcm.java`
- `android_spike/src/main/java/dev/mygpt/spike/SherpaStreamingDecoder.java`
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
- the streaming decoder adapts the upstream ready/decode/result/endpoint/reset loop, including the 0.8 s endpoint zero-tail, behind a dependency-neutral Engine interface;
- recognizer JNI/AAR files and model weights remain intentionally unbundled.

The upstream Apache-2.0 license is reproduced in
`third_party/sherpa-onnx/LICENSE`.
