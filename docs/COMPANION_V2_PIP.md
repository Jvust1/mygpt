# Companion V2 Picture-in-Picture companion mode

Date: 2026-09-30

Companion V2 now has an explicit "进入陪伴小窗" action that uses Android's native
Picture-in-Picture API.

## Why PiP first

PiP provides a real cross-application visible companion window without adding:

- SYSTEM_ALERT_WINDOW;
- Accessibility;
- screen capture;
- a background overlay service.

That makes it a lower-permission first step toward the final "Book + floating
companion" experience.

## Behavior

- user explicitly taps the PiP button;
- PiP uses a 1:1 aspect ratio;
- while in PiP, the Activity hides every surface except the Spine render shell;
- 3714430278 remains visible above Book/other apps;
- expanding the PiP restores the full local chat/model/voice/memory UI;
- no auto-enter is enabled;
- leaving the Activity normally still stops microphone/TTS and cancels active
  generation, while a visible PiP session is not treated as fully backgrounded.

## Current gate

Code only until Companion V2 builds and is device-tested on Xiaomi 14.

Acceptance should verify:

1. PiP entry succeeds after 3714430278 is loaded;
2. only the character render surface is visible in PiP;
3. Book can be opened behind the PiP window;
4. Spine animation continues without GL/context corruption;
5. expanding returns to the complete UI;
6. closing PiP releases/stops runtime work according to Activity lifecycle;
7. no SYSTEM_ALERT_WINDOW permission exists in the installed package.
