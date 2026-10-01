# Sherpa restore threading

Fingerprint verification recomputes SHA-256 over large ASR/TTS core files.
Those reads must never run on the Android UI thread.

Companion V2 now restores/verifies sherpa ASR and Melo TTS inside
`Dispatchers.IO`. The standalone Voice Spike performs the same restore check
on a dedicated worker thread.

Until verification finishes, the corresponding controls remain disabled and the
UI reports verification state. A missing/mismatched fingerprint produces an
unavailable model state rather than handing unverified files to sherpa.

Companion V2 also rejects a current user message above the prompt-budget
`MAX_USER_CHARS` limit before memory lookup or JNI.
