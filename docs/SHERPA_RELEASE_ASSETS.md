# Sherpa release asset downloader

The older sherpa ASR/TTS GitHub release assets used by Companion V2 do not expose
a digest through GitHub's release API. MyGPT therefore does **not** invent or
claim an archive SHA.

Instead the downloader fixes:
- repository: `k2-fsa/sherpa-onnx`;
- release tag and release ID;
- immutable release asset ID;
- asset filename;
- exact archive byte length.

Then the Android installer performs the stronger trust decision after extraction:
- ASR: all four runtime core files must match pinned bytes + SHA-256;
- TTS: executable `model.onnx` must match pinned bytes + SHA-256;
- all installed runtime files are also written to/reverified from the local
  deterministic fingerprint manifest.

## Fixed release assets

ASR:
- tag `asr-models`
- release ID `130628817`
- asset ID `170453803`
- file `sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20.tar.bz2`
- exact bytes `511274346`

TTS:
- tag `tts-models`
- release ID `130612623`
- asset ID `203769960`
- file `vits-melo-tts-zh_en.tar.bz2`
- exact bytes `167006755`

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\android_llm_spike\scripts\download_sherpa_model.ps1 -Kind asr
powershell -ExecutionPolicy Bypass -File .\android_llm_spike\scripts\download_sherpa_model.ps1 -Kind tts
```

Default storage prefers `My Drive/AI-Model-Vault/mygpt/voice_models`, then
falls back to local app data.
