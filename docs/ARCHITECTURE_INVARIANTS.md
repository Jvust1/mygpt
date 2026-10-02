# Architecture Invariants

1. **Book-first perception.** When learning occurs inside Book, Book semantic state is the primary perception source. Do not use vision to rediscover information Book already knows.
2. **Semantic context before pixels.** Preferred order: Book semantic context → OS/App activity signals → user-declared context → opt-in screen vision as fallback.
3. **Presence does not imply continuous cloud inference.** Local/event-driven sensing should keep the system aware while cloud-model calls occur only when useful.
4. **mygpt is orchestration, not a data lake.** Book remains authoritative for learning content, StudyMate for study/device signals, ChatContextVault for protected relationship history.
5. **ChatContextVault remains gated.** No raw conversation corpus is copied into mygpt. Access must respect ChatContextVault's own current-session authentication gate.
6. **Shadow is simulation.** Shadow output is visibly labeled and grounded in retrieved history; uncertainty must be surfaced rather than invented.
7. **Privacy by default.** Private messaging content, credentials, financial screens, password fields, and unrelated personal content are excluded from capture/upload by default.
8. **Ask when perception is ambiguous.** A static page can mean deep thought, paper work, or distraction. The system must ask instead of pretending certainty.
9. **No autonomous phone control in MVP.** v0.1 focuses on see/understand/speak, not arbitrary tapping, typing, or sending messages.
10. **Human agency over optimization.** The system may support, question, or suggest, but should not manipulate the user into dependence or displace real-world relationships.
11. **Evidence-backed learning state.** Reading time alone is weak evidence. Recall, explanation, practice performance, and repeated concept behavior are stronger evidence of mastery.
12. **Cost is an architectural constraint.** Presence should remain affordable through local processing, event-driven updates, and bounded cloud use.
