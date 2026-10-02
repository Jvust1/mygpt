# MyGPT on-device llama.cpp bridge

This isolated Gradle build wires MyGPT to the pinned full llama.cpp Android
binding under `third_party/llama.cpp/upstream`.

Why it is separate from `android_spike`:

- llama.cpp upstream Android library currently requires minSdk 33;
- it builds with Java/Kotlin 17;
- it pins NDK 29.0.13113456 and CMake 3.31.6;
- the current Spine/device spike intentionally remains Java 8 / minSdk 24.

The bridge exposes model load, approved system prompt, token generation,
benchmark, unload and destroy. It does not bundle any GGUF model and does not
select a default model.

Build:

```sh
gradle -p android_llm_spike :bridge:assembleRelease
```

The source pin is the git submodule commit recorded in
`third_party/llama.cpp/NOTICE.md`.

The [bounded native CI gate](../docs/LLAMA_NATIVE_BUILD_GATE_20261002.md) builds
this existing library, bridge and local app without models or private assets.
Its explicit CI-only stable-NDK override and metadata-only evidence do not
change normal local builds or establish inference/device acceptance.
