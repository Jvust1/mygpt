# PR #15 current checkpoint — 2026-09-30

Exact head: `907208ac0db090635fcf1fc342223ad51f97fdaa`

Current companion surface:
- 3714430278 Spine;
- shared Character Card from `brain/personas/3714430278.json`;
- native PiP;
- local llama.cpp GGUF;
- sherpa local ASR/TTS;
- explicit long-term memory;
- bounded recent conversation continuity;
- same-signature live Book context;
- same-signature quiet-first study supervision.

Supervision signals never directly become model instructions and do not trigger
an autonomous LLM call. MyGPT-local opt-in remains the gate for repeated-error
gentle prompts.

The Windows/Xiaomi acceptance path now automatically verifies:
1. exact source/toolchain/upstream pins;
2. Companion/Book-sender same signing certificate;
3. adb-shell Book context rejection;
4. same-signature Book context accept + clear;
5. adb-shell study-event rejection;
6. signed study-event lifecycle;
7. repeated-error QUIET before local opt-in;
8. device UI tap of MyGPT supervision opt-in;
9. repeated-error GENTLE_CHECK_IN only afterward.

No exact-head device result exists yet.
