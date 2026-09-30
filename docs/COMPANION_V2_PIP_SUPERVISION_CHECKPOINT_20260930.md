# Companion V2 PiP + quiet-supervision checkpoint — 2026-09-30

Exact head: `4d26563d8c03453f27c9a31186a484004d6d1535`  
Draft PR: #15  
Main modified: no  
Book/Live repositories modified: no

## Cross-App companion

Native Android PiP is implemented as an explicit, skin-gated 1:1 character-only surface. It avoids overlay/accessibility permissions and is intended to remain visible above Book.

## Book context

Same-signature explicit-package broadcasts feed a process-memory-only mailbox. Companion receives live in-process notifications and each LLM turn marks current Book state fresh or unavailable.

## Study supervision

Accepted signed events:
SESSION_STARTED, CONTEXT_CHANGED, SESSION_PAUSED, SESSION_RESUMED,
SESSION_ENDED, HELP_REQUESTED, PRACTICE_REPEATED_ERROR, REVOKE.

Policy:
- quiet by default;
- HELP -> NEEDS_INPUT;
- PAUSE -> PAUSED;
- resume/context -> QUIET;
- repeated error -> GENTLE_CHECK_IN only with local per-session MyGPT opt-in and 10-minute cooldown;
- end/revoke -> QUIET + opt-in reset.

No inactivity inference or screen monitoring.

## Automated local acceptance

`build_and_install_companion_v2.ps1` now performs source/toolchain/signature gates, Book negative/positive/clear gates and invokes `test_companion_supervision.ps1`.

The supervision script verifies sender authority and user agency with ADB UI automation. It persists a test-only PASS marker for later evidence collection.

## Remote CI

Current exact-head hosted jobs still have runner_id=0 and zero steps, so they provide no build/test result.

## Next

Execute the Windows + Xiaomi 14 path, import 3714430278/GGUF/sherpa model packages, test PiP/local chat/voice/TTS/memory, run benchmark and collect evidence. Real Book producer adoption follows only after this local gate passes.
