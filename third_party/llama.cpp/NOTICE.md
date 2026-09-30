# llama.cpp attribution

Upstream: https://github.com/ggml-org/llama.cpp  
Pinned upstream commit: `ba0ba54d93b25faf1e149f4ccedd3e9d84798563`  
License: MIT (Copyright (c) 2023-2026 The ggml authors)

MyGPT directly adapts the Android inference lifecycle/concurrency design from:

- `examples/llama.android/lib/src/main/java/com/arm/aichat/InferenceEngine.kt`
- `examples/llama.android/lib/src/main/java/com/arm/aichat/internal/InferenceEngineImpl.kt`
- `examples/llama.android/lib/src/main/java/com/arm/aichat/internal/gguf/GgufMetadataReaderImpl.kt`

Local derived/modified files:

- `android_spike/src/main/java/dev/mygpt/spike/LocalLlmEngine.java`
- `android_spike/src/main/java/dev/mygpt/spike/SerializedLocalLlmEngine.java`
- `android_spike/src/main/java/dev/mygpt/spike/GgufModelProbe.java`
- `android_spike/src/main/java/dev/mygpt/spike/GgufModelInstaller.java`

Material changes in MyGPT:

- Kotlin Flow/StateFlow are replaced by a small Java-8 interface and Future-based
  serialized executor so the contract can compile inside the current Java spike;
- the actual llama.cpp JNI/C++ backend is **not** copied or claimed integrated yet;
- model operations are still constrained to one worker thread, mirroring upstream;
- explicit lifecycle states cover load, system prompt, generation, unload, error,
  cancellation and terminal destruction;
- model paths must point to existing readable files;
- no model weights are bundled;
- the backend interface is intentionally replaceable until a Xiaomi 14 benchmark
  justifies shipping llama.cpp native code.

The upstream MIT license is reproduced in `third_party/llama.cpp/LICENSE`.

- MyGPT adds an app-private installer around the GGUF probe: bounded streaming
  copy, SHA-256 addressing, temporary-file cleanup, duplicate detection and
  post-copy format verification. This installer is MyGPT integration code.
