# Xiaomi 14 local GGUF benchmark candidates

No model is the default before device evidence.

All candidates are Apache-2.0 GGUFs from `ggml-org`. Each candidate is fixed by
**four identities**:

1. Hugging Face repository;
2. immutable upstream commit;
3. exact byte length;
4. full-file SHA-256.

The pinned llama.cpp commit
`ba0ba54d93b25faf1e149f4ccedd3e9d84798563` contains Qwen3 and Qwen3.5
architecture support.

| ID | Model | Quant | Exact bytes | Upstream file commit | Purpose |
| --- | --- | --- | ---: | --- | --- |
| speed | Qwen3.5-0.8B | Q4_0 | 563,036,064 | `9447f74101aeb4e93621884dfa36ee8effb8831b` | latency/RAM floor |
| balanced | Qwen3-1.7B | Q4_K_M | 1,282,439,264 | `daeb8e2d528a760970442092f6bf1e55c3b659eb` | balance candidate |
| quality | Qwen3-4B | Q4_K_M | 2,497,280,640 | `2f3b082b1356a6123f7ed71e65aea340da25d53c` | quality ceiling candidate |

Source identity was rechecked against Hugging Face LFS/Xet pointer metadata on
2026-09-30. The downloader uses **commit-pinned resolve URLs**, not mutable
`resolve/main`.

Use:

```powershell
powershell -ExecutionPolicy Bypass -File .\android_llm_spike\scripts\download_llm_candidate.ps1 -Candidate balanced
```

The downloader prefers a mounted
`My Drive/AI-Model-Vault/mygpt/llm_candidates` directory, otherwise falls back
to local app data. It resumes downloads when possible and accepts a candidate
only after both **exact byte length and SHA-256** match.

The sidecar `.mygpt-manifest.txt` records the pinned upstream commit, source
URL, expected/actual bytes and SHA-256.

Companion V2 recognizes these SHA identities in the UI/benchmark report.
Each in-app benchmark writes both `benchmark-last.txt` and a per-SHA
`benchmark-<sha16>.txt`, so results survive later candidate tests.

The final evidence collector attempts to collect all three known candidate
benchmark files and reports `benchmark_matrix_count`.

Selection must consider at least:
- prompt-processing speed;
- text-generation speed;
- PSS/native/Java memory;
- thermal before/after;
- subjective Chinese companion/teaching quality on the same prompt set.

Do not choose a default from parameter count or desktop benchmark alone.
