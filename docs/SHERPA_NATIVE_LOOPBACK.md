# Sherpa native TTS -> ASR loopback gate

After both fixed sherpa model packages are imported, the debug-only
`DebugVoiceLoopbackActivity` performs an in-memory native execution gate:

1. create Melo zh/en OfflineTts using the same `SherpaMeloTtsFactory` as production;
2. synthesize the fixed phrase: `你好，今天一起学习。`;
3. keep generated float PCM in memory only;
4. linearly resample to 16 kHz when required;
5. feed 100 ms chunks into the production `SherpaStreamingAsrEngine`;
6. feed bounded silence to encourage endpoint detection;
7. require non-empty ASR text.

Evidence:
- TTS sample rate/sample count/time;
- 16 kHz ASR input sample count/time;
- endpoint boolean;
- ASR transcript;
- `audio_persisted=false`.

The automatic gate requires actual TTS samples and a non-empty ASR transcript.
It does **not** require an exact transcript match, because the purpose is native
execution/integration validation rather than ASR accuracy scoring.

No speaker or microphone is used in this gate. Real microphone capture and
audible TTS playback remain separate Xiaomi 14 experience gates.


The final evidence collector re-parses the loopback JSON whenever a PASS marker
exists. It requires non-empty TTS/ASR sample counts, non-empty transcript,
`completed=true`, and `audio_persisted=false`. A stale/inconsistent PASS
marker therefore cannot silently pass the final evidence summary.
