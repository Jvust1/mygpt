# Decision Ledger

## D001 — mygpt is the companion/orchestrator
mygpt is the user-facing long-term companion. Book, StudyMate, and ChatContextVault remain separate authoritative systems with clear boundaries.

## D002 — companionship outranks check-in gamification
The product is not primarily a streak tracker. Quiet presence, useful intervention, teaching, encouragement, and conversation are the core experience.

## D003 — Book-first perception
For Book-based learning, structured Book state is superior to screen recognition and is the default input to mygpt.

## D004 — screen vision is fallback, not foundation
Screen capture is reserved for unsupported external learning contexts and requires explicit session-scoped permission.

## D005 — event-driven awareness
Local state changes and semantic events should trigger reasoning. The system should not stream every screen frame to a cloud model.

## D006 — learning evidence hierarchy
Time-on-page is weak evidence. Recall, explanation, practice behavior, and repeated concept interactions should carry more weight in learning-state estimates.

## D007 — ambiguity must be conversationally resolved
When signals cannot distinguish paper study, deep thinking, and distraction, mygpt asks the user rather than asserting a hidden state.

## D008 — Shadow is explicit simulation
ChatContextVault may ground an optional Shadow mode, but the system must not impersonate the real person or imply simulated messages are authentic.

## D009 — mygpt keeps its own identity
Ordinary emotional support and companionship are delivered by mygpt itself, not by continuously roleplaying the Shadow persona.

## D010 — no autonomous UI control in v0.1
The first version focuses on perception, understanding, and conversation. Arbitrary UI automation is deliberately deferred.

## D011 — privacy exclusion zones
Private messages, credentials, financial screens, password fields, and unrelated personal information are excluded by default from capture/upload.

## D012 — affordable continuous presence
Continuous presence should mostly be local and event-driven; expensive cloud reasoning or real-time voice sessions are invoked only when useful.

## D013 — real relationships are not competitors
The product must not frame itself as the only entity that understands the user or push the user away from real-world relationships.

## D014 — Jonah is the first companion surface candidate
Use the already validated Jonah sprite as mygpt's initial visual companion. Keep the renderer framework-neutral until a production host is selected. The component accepts explicit states and emits user actions; product logic remains outside the visual layer.

## D015 — mobile app surface before system overlay
First validate Jonah inside the mygpt mobile surface with touch, safe-area, reduced-motion, and hide/restore behavior. Treat an Android cross-application floating window as a separate Android Studio milestone with explicit OS permission and physical-device acceptance evidence.

## D016 — imported local content remains explicitly unverified
Local files/manual text can be useful before a production Book/Android bridge is available, but user-supplied bytes must never be silently promoted to authenticated Book facts. Intake is default-off, one-record/bounded, preview-and-consent driven, and uses a separate `USER_SUPPLIED_UNVERIFIED` context/reference namespace.

## D017 — recovery is an explicit product requirement
A runnable candidate is not considered recoverable only because GitHub contains files. Checkpoints should provide a deterministic source-only bundle from an immutable commit, an externally recorded SHA-256, a read-only environment doctor, an explicit launcher, and clean-directory recovery evidence. Launchers must not auto-install dependencies, inherit provider credentials, or silently enable intake/provider capabilities.

## D018 — integrate stale review lines by capability, not by state-file overwrite
When an older review branch contains useful additive runtime capability but also replaces newer project-state documents, create a fresh non-default integration branch from the newer accepted baseline and transplant only the bounded runtime/test capability. Preserve the old branch as provenance; do not resolve review-stack conflicts by overwriting current state or rewriting history.

## D019 — final mobile product pairs mygpt with Book Android
The final product target is an Android companion that works alongside the Book Android app. Book remains the learning surface and authoritative structured study-context source; mygpt consumes bounded Book context/events to understand the current learning situation.

## D020 — Live is the authoritative character-skin source
The final visible companion should use character skins and presentation assets from the separate Live project. The current Jonah component is retained as a validated interaction prototype, not as the final character-content authority. mygpt must not silently fork or duplicate Live's authoritative skin collection.

## D021 — mygpt owns conversation and supervision behavior
mygpt is responsible for conversation, teaching assistance, encouragement, supervision and intervention policy. Character appearance comes from Live and learning truth comes from Book. Supervision should be evidence-driven and graduated from silent presence to reminders or active supervision; ambiguous states should be resolved conversationally rather than by asserting that the user is distracted.

## D022 — upstream adoption is broad in research and narrow in shipping dependencies
mygpt maintains a broad upstream registry across Android, local AI, voice, supervision, memory and character runtimes so mature open-source work is continuously reused. “Adopt” does not mean bulk-vendoring every repository. Production dependencies must remain small, replaceable and explicitly version/license/security checked; restricted/copyleft projects remain reference-only until a separate decision permits their integration. The canonical registry is `governance/open_source_sources.json` and the adoption plan is `docs/OPEN_SOURCE_ADOPTION.md`.

