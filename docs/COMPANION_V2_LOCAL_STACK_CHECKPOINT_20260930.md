# Companion V2 all-local stack checkpoint — 2026-09-30

## Identity

- Repository: `Jvust/mygpt`
- Branch: `feat/airi-chat-memory-brain-20260929`
- Draft PR: #15
- Base: `feat/spine-3714430278-runtime-refresh-20260929`
- Exact head: `a83680c1810242d541941b6c2b1a361c8d00bf71`
- Main modified: no
- Auto-merge: no

## Product advance

The candidate now contains one code path for a phone-local companion:

```text
typed text
   or
explicit RECORD_AUDIO -> sherpa streaming ASR
             ↓
   relevant explicit local memory
             ↓
      llama.cpp Android JNI
             ↓
 visible reply + AIRI ACT emotion
        ↓                 ↓
 optional local TTS    3714430278 Spine
```

## Upstream pins

| Upstream | Pin/runtime | License | Role |
|---|---|---|---|
| moeru-ai/airi | b40e3e87... | MIT | conversation authority, Character Card, emotion + ACT protocol |
| mem0ai/mem0 | 94c3fe9f... | Apache-2.0 | explicit memory lifecycle/audit |
| ggml-org/llama.cpp | ba0ba54d... | MIT | full Android JNI/GGUF source |
| k2-fsa/sherpa-onnx | source 040afe36..., runtime v1.13.8 / 11afbd00... | Apache-2.0 | streaming ASR + local TTS |
| princekin-f/EasyFloat | 1a652260... | Apache-2.0 | in-app drag/snap core only |
| Apache Commons Compress | 1.28.0 | Apache-2.0 | ZIP/TAR.BZ2/TAR.GZ model archive reader |

## Android boundaries

Companion V2 module: `android_llm_spike/companion`.

- minSdk 33; targetSdk 36; arm64-v8a.
- Manifest permission: RECORD_AUDIO only.
- No INTERNET permission.
- No SYSTEM_ALERT_WINDOW permission.
- No broad storage permission.
- Skin/model files selected through SAF and installed app-private.
- Raw microphone audio is not written to disk.
- TTS samples are streamed to AudioTrack and are not saved.
- TTS is default-off.
- Chat transcript is not automatically persisted as long-term memory.

## Model inputs

- Skin: validated decrypted `3714430278.zip`.
- LLM: GGUF; header validation + bounded copy + SHA-256 content identity.
- ASR: sherpa bilingual streaming Zipformer model package.
- TTS: `vits-melo-tts-zh_en` model package.
- Accepted ASR/TTS archive formats: ZIP, TAR.BZ2, TAR.GZ.
- README/LICENSE from selected sherpa model packages are retained when present.

## Memory

Android store: `LocalCompanionMemoryStore.kt`.

- explicit add only;
- relevant recall;
- update with audit history;
- delete with audit;
- `purge` full erasure of active memory + history;
- typed commands: `:remember`, `:memories`, `:update`, `:history`, `:forget`;
- voice transcripts bypass memory commands and are not auto-stored.

## Validation status

Earlier narrow local evidence remains valid for its exact scope. Current exact-head Android artifacts are not yet executed because GitHub Actions cannot allocate runners. Representative exact-head runs all have runner_id=0 and zero steps:
- llama: 36659174083
- sherpa: 36659174123
- Android boundary: 36659174091

Therefore current Companion V2 APK / Voice Spike APK / llama AAR status is **NOT EXECUTED**, not PASS and not code FAIL.

## Next gate

1. Run exact-head builds on a functioning runner.
2. Install Companion V2 on Xiaomi 14.
3. Import 3714430278, a compatible GGUF, sherpa ASR package and optional Melo TTS package.
4. Validate typed chat, voice ASR, explicit memory, local reply, ACT emotion, Spine reaction, TTS, background/reopen.
5. Benchmark speed/RAM/thermal behavior and choose a default GGUF only after device measurements.
6. Connect authenticated real Book Android semantic context after the local stack is accepted.
