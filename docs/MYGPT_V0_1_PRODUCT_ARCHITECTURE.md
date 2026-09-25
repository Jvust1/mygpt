# mygpt v0.1 Product Architecture

## 1. Core idea

mygpt should act like a quiet, context-aware study companion rather than a timer or surveillance app.

The first version should know:
- what the user is studying inside Book;
- where they are in the current learning flow;
- when they meaningfully switch, pause, return, or struggle;
- when to remain silent;
- when to teach, ask, encourage, or lightly call the user back.

## 2. Context pipeline

Preferred perception order:

```
Book semantic state
  ↓
StudyMate / Android app-state signals
  ↓
User-declared context
  ↓
Optional session-scoped screen vision
  ↓
mygpt reasoning / intervention
```

## 3. Book StudyContext

A future Book connector should expose a compact snapshot similar to:

```json
{
  "session_id": "...",
  "course_id": "...",
  "book_id": "...",
  "chapter_id": "...",
  "section_id": "...",
  "mode": "preview|learn|review|practice",
  "active_source_id": "...",
  "expanded_source_ids": [],
  "scroll_y": 0,
  "entered_at": "...",
  "dwell_ms": 0
}
```

Optional learning evidence may include:
- practice item/result;
- review preset/filter;
- recall attempt;
- source reopen/revisit patterns;
- concept IDs when Book gains a canonical concept layer.

## 4. Event stream

Useful events:

```
SESSION_STARTED
SECTION_ENTERED
MODE_CHANGED
SOURCE_OPENED
SOURCE_REOPENED
SCROLL_BURST
LONG_DWELL
PRACTICE_ATTEMPTED
PRACTICE_RESULT
BOOK_LEFT
BOOK_RETURNED
SESSION_ENDED
```

Events should be semantic and bounded. Avoid streaming raw UI state at high frequency.

## 5. Companion state

```
SILENT_PRESENCE
LIGHT_COMPANION
STUDY_COACH
ACTIVE_SUPERVISOR
ORDINARY_CHAT
EMOTIONAL_SUPPORT
SHADOW_MODE
```

Transitions are policy decisions made from evidence, current conversation, user preference, and explicit commands.

## 6. Ambiguity

Example: no Book interaction for 15 minutes.

Possible interpretations:
- deep reading;
- paper calculation;
- distraction;
- interruption.

Correct behavior is not automatic accusation. mygpt may ask:
"还在纸上算，还是卡住了？"

## 7. Low-cost Android signals

When useful, an Android bridge may expose:
- foreground package;
- screen on/off;
- lock/unlock;
- Book foreground/background;
- idle/return timing;
- explicit study-session lifecycle.

These signals do not require raw screen upload.

## 8. Screen-vision fallback

Only when semantic/app signals are insufficient:
- explicit user permission per capture session;
- capture only learning-relevant content;
- local filtering/redaction first where practical;
- block or suppress sensitive contexts;
- send selected frames, not continuous full-frame video by default.

## 9. Learning memory

mygpt should track evidence-oriented learning state, e.g.:

```
ConceptState
- seen
- understood_estimate
- recall_strength
- application_strength
- common_mistakes
- last_reviewed
- evidence_refs
```

Book remains the content authority; mygpt stores the learner-facing interpretation and interaction history.

## 10. ChatContextVault / Shadow

Shadow mode:
- requires ChatContextVault's own access gate;
- retrieves only relevant historical context;
- distinguishes evidence from inference;
- clearly labels output as simulation;
- does not invent current thoughts, feelings, or relationship status;
- does not become the default mygpt personality.

## 11. Emotional support

mygpt may:
- listen;
- help the user name and organize feelings;
- distinguish companionship from problem-solving;
- offer structured reflection when asked;
- encourage appropriate real-world support when needed.

It must not diagnose or claim to replace professional care.

## 12. v0.1 acceptance target

During a 30-minute Book study session:
1. mygpt knows the current chapter/section/mode without screen recognition.
2. It can answer context-dependent questions such as "这里为什么这样？".
3. It remains quiet during normal progress.
4. It notices meaningful transitions or probable difficulty.
5. It asks rather than assumes when evidence is ambiguous.
6. It can perform a recall check grounded in the just-studied material.
7. No continuous screen upload is required.
