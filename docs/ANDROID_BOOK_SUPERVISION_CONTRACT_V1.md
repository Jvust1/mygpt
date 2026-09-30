# Signed Book study supervision contract v1

Companion V2 accepts explicit study-state signals from a same-signature Book
application through:

`dev.mygpt.companionv2.action.BOOK_STUDY_EVENT_V1`

The receiver uses the existing signature permission:

`dev.mygpt.companionv2.permission.BOOK_CONTEXT`

## Accepted event kinds

- SESSION_STARTED
- CONTEXT_CHANGED
- SESSION_PAUSED
- SESSION_RESUMED
- SESSION_ENDED
- HELP_REQUESTED
- PRACTICE_REPEATED_ERROR
- REVOKE

Required extras for normal events:
- kind
- session_id
- sequence
- epoch
- expires_at_ms

TTL must be positive and <= 5 minutes.

CONTEXT_CHANGED, HELP_REQUESTED and PRACTICE_REPEATED_ERROR are accepted only
when an unexpired signed Book context exists for the same session. MyGPT creates
the opaque `book-lease://signed/...` reference itself; the sender cannot inject
a source body or source_ref into the supervision runtime.

## Quiet-first policy

- SESSION_STARTED -> QUIET
- CONTEXT_CHANGED / SESSION_RESUMED -> QUIET
- SESSION_PAUSED -> PAUSED
- HELP_REQUESTED -> NEEDS_INPUT
- PRACTICE_REPEATED_ERROR -> GENTLE_CHECK_IN only when the user has explicitly
  opted into supervision for the active session and the 10-minute cooldown has
  elapsed
- SESSION_ENDED / REVOKE -> QUIET and opt-in cleared

No inactivity timer, screen reading or attention inference is used.

The opt-in is local MyGPT state and resets on a new/end/revoked session.
