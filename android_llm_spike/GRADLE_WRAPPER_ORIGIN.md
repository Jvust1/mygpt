# Gradle wrapper origin

The android_llm_spike wrapper is pinned to Gradle 8.14.3.

- gradle-wrapper.jar, gradle-wrapper.properties and Unix gradlew are copied from
  ggml-org/llama.cpp at ba0ba54d93b25faf1e149f4ccedd3e9d84798563,
  path examples/llama.android/.
- gradlew.bat is the standard Gradle Windows launcher copied from the pinned
  sherpa-onnx Android demo.

The launcher scripts carry the Apache-2.0 Gradle wrapper header. The distribution
URL is fixed in gradle-wrapper.properties.