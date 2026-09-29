package dev.mygpt.spike;

import java.util.Objects;

/** Pure Java 8 core for a future Android host. No Android permission or network dependency. */
public final class CompanionCoordinator {
    public enum Kind {
        SESSION_STARTED, CONTEXT_CHANGED, SESSION_PAUSED, SESSION_RESUMED,
        SESSION_ENDED, HELP_REQUESTED, PRACTICE_REPEATED_ERROR
    }

    public enum Cue { QUIET, PAUSED, NEEDS_INPUT, GENTLE_CHECK_IN }

    /** A trusted Book adapter must authenticate and project the event before calling accept. */
    public static final class BookEvent {
        public final Kind kind;
        public final String sessionId;
        public final long sequence;
        public final long epoch;
        public final long expiresAtMs;
        public final String sourceRef;

        public BookEvent(Kind kind, String sessionId, long sequence, long epoch,
                         long expiresAtMs, String sourceRef) {
            this.kind = Objects.requireNonNull(kind, "kind");
            this.sessionId = Objects.requireNonNull(sessionId, "sessionId");
            this.sequence = sequence;
            this.epoch = epoch;
            this.expiresAtMs = expiresAtMs;
            this.sourceRef = sourceRef;
        }
    }

    /** Live owns assets and rendering. The coordinator emits only a presentation cue. */
    public interface CharacterRuntime {
        void show(Cue cue);
    }

    public interface VerifiedBookPort {
        /** Must reject unauthenticated, revoked, or tampered Book events. */
        boolean isCurrent(BookEvent event, long nowMs);
    }

    public static final class Result {
        public final boolean accepted;
        public final String reason;
        public final Cue cue;
        private Result(boolean accepted, String reason, Cue cue) {
            this.accepted = accepted;
            this.reason = reason;
            this.cue = cue;
        }
    }

    private static final long CHECK_IN_COOLDOWN_MS = 10 * 60 * 1000L;
    private final VerifiedBookPort book;
    private final CharacterRuntime character;
    private String sessionId;
    private long epoch;
    private long lastSequence;
    private long expiresAtMs = Long.MIN_VALUE;
    private long lastCheckInMs = Long.MIN_VALUE;
    private boolean paused;
    private boolean supervisionOptIn;
    private Cue cue = Cue.QUIET;

    public CompanionCoordinator(VerifiedBookPort book, CharacterRuntime character) {
        this.book = Objects.requireNonNull(book, "book");
        this.character = Objects.requireNonNull(character, "character");
        character.show(Cue.QUIET);
    }

    /** User controlled, local setting. Disabling it immediately hides an unsolicited prompt. */
    public synchronized void setSupervisionOptIn(boolean enabled) {
        supervisionOptIn = enabled;
        if (!enabled && cue == Cue.GENTLE_CHECK_IN) present(Cue.QUIET);
    }

    public synchronized Cue currentCue() { return cue; }

    /** The trusted host calls this immediately when Book revokes or disconnects. */
    public synchronized void revokeSession() {
        sessionId = null;
        expiresAtMs = Long.MIN_VALUE;
        paused = false;
        supervisionOptIn = false;
        present(Cue.QUIET);
    }

    /** Expiry also clears a visible cue when no further Book event arrives. */
    public synchronized boolean expireIfNeeded(long nowMs) {
        if (sessionId == null || nowMs < expiresAtMs) return false;
        revokeSession();
        return true;
    }

    public synchronized Result accept(BookEvent event, long nowMs) {
        Objects.requireNonNull(event, "event");
        expireIfNeeded(nowMs);
        if (nowMs < 0 || event.expiresAtMs <= nowMs || event.sequence < 1 || event.epoch < 1
                || event.sessionId.isEmpty()) return reject("INVALID_OR_EXPIRED");
        if (!book.isCurrent(event, nowMs)) return reject("BOOK_AUTHORITY_REJECTED");

        if (event.kind == Kind.SESSION_STARTED) {
            if (event.sequence != 1 || (epoch != 0 && event.epoch <= epoch))
                return reject("STALE_SESSION");
            sessionId = event.sessionId;
            epoch = event.epoch;
            lastSequence = 1;
            expiresAtMs = event.expiresAtMs;
            lastCheckInMs = Long.MIN_VALUE;
            paused = false;
            supervisionOptIn = false;
            present(Cue.QUIET);
            return acceptResult();
        }
        if (sessionId == null || !sessionId.equals(event.sessionId) || epoch != event.epoch)
            return reject("SESSION_MISMATCH");
        if (event.sequence != lastSequence + 1) return reject("REPLAY_OR_GAP");
        if (requiresContext(event.kind) && (event.sourceRef == null
                || !event.sourceRef.startsWith("book-lease://") || event.sourceRef.length() > 1800))
            return reject("SOURCE_REF_REQUIRED");
        if (paused && event.kind != Kind.SESSION_RESUMED && event.kind != Kind.SESSION_ENDED)
            return reject("SESSION_PAUSED");

        // No source body, note, answer, screenshot, or provider input is stored here.
        lastSequence = event.sequence;
        expiresAtMs = event.expiresAtMs;
        switch (event.kind) {
            case SESSION_PAUSED:
                paused = true;
                present(Cue.PAUSED);
                break;
            case SESSION_RESUMED:
            case CONTEXT_CHANGED:
                paused = false;
                present(Cue.QUIET);
                break;
            case HELP_REQUESTED:
                present(Cue.NEEDS_INPUT);
                break;
            case PRACTICE_REPEATED_ERROR:
                if (supervisionOptIn && (lastCheckInMs == Long.MIN_VALUE
                        || nowMs - lastCheckInMs >= CHECK_IN_COOLDOWN_MS)) {
                    lastCheckInMs = nowMs;
                    present(Cue.GENTLE_CHECK_IN);
                } else present(Cue.QUIET);
                break;
            case SESSION_ENDED:
                revokeSession();
                break;
            default:
                throw new IllegalStateException("Unhandled event: " + event.kind);
        }
        return acceptResult();
    }

    private static boolean requiresContext(Kind kind) {
        return kind == Kind.CONTEXT_CHANGED || kind == Kind.HELP_REQUESTED
                || kind == Kind.PRACTICE_REPEATED_ERROR;
    }

    private void present(Cue next) {
        if (next != cue) {
            cue = next;
            character.show(next);
        }
    }

    private Result reject(String reason) { return new Result(false, reason, cue); }
    private Result acceptResult() { return new Result(true, "ACCEPTED", cue); }
}
