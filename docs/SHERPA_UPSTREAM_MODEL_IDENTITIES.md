# Sherpa upstream core-file identity locks

Date: 2026-09-30

MyGPT already generated a deterministic per-file fingerprint manifest after
import. This checkpoint adds a second, upstream-fixed identity gate.

## Streaming zh/en ASR

Upstream model:
`csukuangfj/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20`

Pinned revision:
`98590b7ed6443e77b714204da2757d75e1a642f4`

All four runtime inputs are hard-locked:

| File | Exact bytes | SHA-256 |
| --- | ---: | --- |
| encoder-epoch-99-avg-1.int8.onnx | 181,895,032 | 8fa764187a261844f859d7143ebaa563af5d10adfece4c18a8f414c88cba2a9b |
| decoder-epoch-99-avg-1.onnx | 13,876,452 | 2e3b5ec371f8899ee6acd829fd753ba45772df57a91bdf37cde3136354e7db7d |
| joiner-epoch-99-avg-1.int8.onnx | 3,228,404 | 1ed689c5ed19dbaa725d9d191bb4822b5f4855a39e1ffd28cbc1f340d25b2ee0 |
| tokens.txt | 75,756 | 59aba8873a2ed1e122c25fee421e25f283b63290efbde85c1f01a853d83cb6e6 |

An ASR install/restore is rejected before sherpa receives the paths if any core
file differs.

## Melo zh/en TTS

Upstream model:
`csukuangfj/vits-melo-tts-zh_en`

Pinned model revision:
`a0d5c6a264c0ef92d70d8661d8cc502d79627cd6`

The executable ONNX file is hard-locked:

- `model.onnx`
- exact bytes: `170429550`
- SHA-256:
  `bf30582eb1b012250a35b1a4a80e7dfbcf8485e7bb9de0d95efbbeef0e4ad86d`

The support files `tokens.txt / lexicon.txt / date.fst / phone.fst / number.fst`
remain protected by MyGPT's deterministic app-private fingerprint manifest.
They are not falsely described as upstream-hard-locked until authoritative
digests are pinned for them.

## Layering

Fresh install:
1. strict archive allowlist + decompressed size bounds;
2. upstream hard identity gate;
3. MyGPT deterministic manifest generation;
4. immediate manifest re-verification;
5. staged directory promotion.

Restore:
1. required files present;
2. upstream hard identity gate;
3. deterministic manifest verification/migration;
4. only then create sherpa runtime objects.
