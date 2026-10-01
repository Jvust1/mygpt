# Companion V2 on-device LLM benchmark

Companion V2 exposes an explicit **运行本机模型基准** button after a GGUF is
loaded. It calls the pinned llama.cpp Android benchmark with:

- prompt processing: 128 tokens
- generation: 64 steps
- parallel sequences: 1
- repetitions: 1

The app records only local device measurements:

- GGUF filename, byte size and imported SHA-256
- benchmark wall-clock time
- process PSS before/after
- native heap before/after
- Java used heap before/after
- Android thermal status before/after
- llama.cpp's returned prompt-processing / token-generation table

The latest report is stored app-private at
`files/benchmark-last.txt`. No network permission exists in Companion V2 and
the benchmark report is not uploaded.

This benchmark is a screening measurement, not final model acceptance. Xiaomi 14
model selection should also consider first-token latency during real chat,
sustained multi-turn temperature, OOM/crash behavior and reply quality.
