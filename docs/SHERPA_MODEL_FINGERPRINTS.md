# Sherpa model fingerprint manifests

Every successful ASR/TTS model import now creates
`mygpt-model-manifest.txt` inside the app-private installed model directory.

Format:

```text
schema=mygpt.model-fingerprint.v1
kind=<model role>
runtime=sherpa-onnx-v1.13.8
file=<name>    bytes=<size>    sha256=<digest>
...
```

The manifest is generated **before** the staging directory is promoted to the
final install path. An install without a complete fingerprint manifest is not
considered restorable.

Fingerprinted core files:

ASR:
- encoder-epoch-99-avg-1.int8.onnx
- decoder-epoch-99-avg-1.onnx
- joiner-epoch-99-avg-1.int8.onnx
- tokens.txt

TTS:
- model.onnx
- tokens.txt
- lexicon.txt
- date.fst
- phone.fst
- number.fst

The final Xiaomi 14 evidence collector copies both manifests when present.
Model weights remain app-private and are not uploaded by this collector.
