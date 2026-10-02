# mygpt — Project North Star

## Mission

mygpt is a long-term companion and learning orchestrator. Its goal is not to maximize check-in metrics or screen surveillance. Its goal is to understand enough context to know when to stay quietly present, when to teach, when to encourage, when to call the user back from distraction, and when to simply talk.

The core product promise is:

> During study, thinking, and ordinary life, the user should not feel that every effort must be carried alone. mygpt should provide low-pressure presence, grounded supervision, learning help, and emotional support while preserving privacy, autonomy, and real-world relationships.

## Product identity

mygpt is a new, independent companion identity. It is not a replacement for any real person.

It may optionally provide a clearly labeled Shadow mode grounded in ChatContextVault history, but Shadow output must remain explicitly simulated and must never be represented as the real person speaking.

## Final product form

The intended final product is an Android companion that works alongside the Book Android app.

The responsibility split is:

- **Book Android** — the learning surface and authoritative source of structured study context: what the user is reading, learning, reviewing, practicing, where they are in the material, and relevant study-state events.
- **Live** — the authoritative source of companion character skins and visual presentation assets. mygpt should be able to use Live characters/skins as the visible companion rather than treating the current Jonah prototype as the final character system.
- **mygpt** — the companion brain and orchestration layer: conversation, teaching assistance, encouragement, supervision, intervention timing, state interpretation, and the decision about when the character should stay quiet, talk, remind, or actively supervise.

The visible character should feel continuously present while the user studies in Book, be available for ordinary conversation, and supervise study without turning the product into punitive surveillance. Supervision should primarily use Book semantic context and explicit/local device signals, escalate gradually, and ask the user when evidence is ambiguous.

The current Jonah surface remains useful as an implementation and interaction prototype, but it is not the final character-content source. The final character system should consume Live-provided skins through a clear interface so character appearance can evolve independently from mygpt reasoning and Book learning data.

## Learning goal

The learning loop is:

Book structured context → study session → low-cost activity signals → selective intervention → retrieval / explanation / recall checks → learning-state update → next study step.

The system should remember how the user learned, not only how many minutes they studied.

## Presence model

Default behavior is quiet presence.

The companion should move between:
- Silent Presence
- Light Companion
- Study Coach
- Active Supervisor

Intervention intensity should be driven by evidence and context, not a fixed notification timer.

## Non-goals

- No always-on invasive surveillance as the default.
- No autonomous control of unrelated apps in the first product stages.
- No impersonation of a real person.
- No diagnosis or replacement of professional mental-health care.
- No engagement-maximizing behavior designed to isolate the user from real relationships.
- No gamification-first design where streaks and scores become the core product.
