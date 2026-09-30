# Automated signed Book supervision sender

The test-only Book sender exposes ADB-triggerable commands that issue nested
same-signature study broadcasts from the sender app UID:

- AUTOMATED_STUDY_START_V1
- AUTOMATED_STUDY_HELP_V1
- AUTOMATED_STUDY_PAUSE_V1
- AUTOMATED_STUDY_RESUME_V1
- AUTOMATED_STUDY_REPEATED_ERROR_V1
- AUTOMATED_STUDY_END_V1
- AUTOMATED_STUDY_REVOKE_V1

Results are written to the sender app-private file
`files/adb-study-result.txt`.

The sender cannot enable MyGPT supervision. The Companion button remains the
only opt-in path and exposes the stable accessibility marker
`TOGGLE_STUDY_SUPERVISION` solely for device acceptance automation.

The Companion supervision status includes ASCII evidence markers:
- `SUPERVISION_STATUS=<status>`
- `SUPERVISION_CUE=<cue>`
- `SUPERVISION_OPT_IN=<true|false>`

This test surface must not be copied into the real Book application.
