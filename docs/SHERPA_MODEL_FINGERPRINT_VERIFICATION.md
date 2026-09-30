# Sherpa fingerprint verification and migration

Imported ASR/TTS model fingerprints are now an integrity gate, not only evidence.

On fresh import:
1. required core files are extracted into staging;
2. `mygpt-model-manifest.txt` is generated;
3. the manifest is immediately recomputed/verified against the staged files;
4. only a verified staging directory is promoted.

On app restore:
- all required core files must exist;
- if a v1 fingerprint manifest exists, it is recomputed and must match exactly;
- if the model was installed by an older MyGPT build before fingerprint v1,
  MyGPT performs a one-time app-private migration by generating the manifest,
  then verifies it;
- a mismatched/tampered model is treated as unavailable and is not handed to
  sherpa-onnx.

The manifest contains hashes/sizes only and the final evidence collector copies
the manifest, not model weights.
