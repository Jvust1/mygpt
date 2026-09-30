# Companion V2 signed-state expiry ticker

Book semantic context and signed study-supervision events already carry bounded
TTL values. Companion V2 now actively applies those expiries while the Activity
is visible, including native Picture-in-Picture mode.

Implementation:
- one main-thread Handler tick every 1 second;
- no network polling;
- no screen reading;
- no Accessibility;
- no background service;
- no wake lock.

Each tick:
1. asks StudySupervisorRuntime to expire its signed session if its latest event
   deadline has passed;
2. reads BookContextMailbox.current(now), which clears expired Book semantic
   context;
3. refreshes the visible Book status.

A supervision expiry clears the active session, clears local supervision
opt-in, sets status SESSION_EXPIRED, and presents QUIET.

The ticker stops when Companion is truly backgrounded outside PiP and on
Activity destruction. It remains active while PiP is visibly presenting the
companion.

Entering PiP explicitly stops microphone capture first. TTS/generation may
finish while the character remains visible, but PiP never creates implicit
microphone recording.
