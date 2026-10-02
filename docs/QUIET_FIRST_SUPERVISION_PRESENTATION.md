# Quiet-first supervision presentation

Companion V2 does not autonomously call the LLM when Book study signals arrive.

Instead, accepted signed study events produce a bounded presentation cue and a
fixed low-pressure local message:

- QUIET: current companion stays quiet;
- PAUSED: "学习已暂停，我安静等你回来。";
- NEEDS_INPUT: asks the user to send the blocked point for Book-grounded help;
- GENTLE_CHECK_IN: after local opt-in + cooldown, offers to split the repeated
  practice difficulty into one small step.

These messages are deterministic UI copy, not model generations.

Every later user chat turn also carries a lower-authority
`STUDY_SUPERVISION_STATE_JSON` block with active/session/opt-in/cue/status.
The local model is explicitly instructed not to infer emotion, motivation,
attention or personality from this state and not to treat the cue as an
instruction.

This keeps supervision explainable, user-controlled and quiet by default.
