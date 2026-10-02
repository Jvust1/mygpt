# sherpa-onnx Android runtime pin

Two identities are intentionally tracked separately:

- **Research/source submodule:** \`040afe360a38e25daaa325ce8889abf93ea02609\`
- **Voice Spike runtime dependency:** \`v1.13.8\`
  - tag commit: \`11afbd009a7f8c08f4bcf2fc1b265d0df4670fbf\`
  - Gradle coordinate:
    \`com.github.k2-fsa.sherpa-onnx:sherpa-onnx:v1.13.8\`

The Voice Spike uses the tagged v1.13.8 Android/JNI runtime because that is the
upstream-published dependency used by the corresponding Java Android demo.
The newer source submodule remains the research/reference pin and is not falsely
claimed to be byte-identical to the v1.13.8 runtime binary.

No ASR model weights are committed to this repository.
