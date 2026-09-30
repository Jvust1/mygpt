package dev.mygpt.spike;

/**
 * Process-memory-only Book context mailbox.
 *
 * Accepted contexts are never written to disk. Sequence/session state remains
 * in memory only to reject stale/replayed deliveries while the process lives.
 */
public final class BookContextMailbox {
    private static final BookContextMailbox SHARED = new BookContextMailbox();

    private BookContextSnapshot current;
    private String lastSessionId;
    private String lastIdentityKey;
    private long lastSequence;
    private long lastCapturedAtMs;

    public static BookContextMailbox shared() {
        return SHARED;
    }

    public synchronized BookContextSnapshot accept(
            BookContextSnapshot next,
            long nowMs
    ) {
        if (next == null) throw new IllegalArgumentException("Book context is required");
        next.requireFresh(nowMs);

        if (lastSessionId == null) {
            if (next.sequence != 1L) {
                throw new IllegalArgumentException("new Book session must start at sequence 1");
            }
        } else if (lastSessionId.equals(next.sessionId)) {
            if (next.sequence != lastSequence + 1L) {
                throw new IllegalArgumentException("Book sequence gap or replay");
            }
            if (!lastIdentityKey.equals(next.identityKey())) {
                throw new IllegalArgumentException("Book identity changed within session");
            }
            if (next.capturedAtMs < lastCapturedAtMs) {
                throw new IllegalArgumentException("Book context time reversal");
            }
        } else {
            if (next.sequence != 1L) {
                throw new IllegalArgumentException("new Book session must start at sequence 1");
            }
            if (next.capturedAtMs < lastCapturedAtMs) {
                throw new IllegalArgumentException("stale Book session replacement");
            }
        }

        current = next;
        lastSessionId = next.sessionId;
        lastIdentityKey = next.identityKey();
        lastSequence = next.sequence;
        lastCapturedAtMs = next.capturedAtMs;
        return next;
    }

    public synchronized boolean clear(
            String sessionId,
            long sequence,
            long occurredAtMs,
            long nowMs
    ) {
        if (sessionId == null || sessionId.isEmpty()) {
            throw new IllegalArgumentException("sessionId is required");
        }
        if (lastSessionId == null || !lastSessionId.equals(sessionId)) {
            return false;
        }
        if (sequence != lastSequence + 1L) {
            throw new IllegalArgumentException("Book clear sequence gap or replay");
        }
        if (occurredAtMs < lastCapturedAtMs) {
            throw new IllegalArgumentException("Book clear time reversal");
        }
        if (occurredAtMs > nowMs + 5000L) {
            throw new IllegalArgumentException("Book clear is from the future");
        }

        current = null;
        lastSequence = sequence;
        lastCapturedAtMs = occurredAtMs;
        return true;
    }

    public synchronized BookContextSnapshot current(long nowMs) {
        if (current == null) return null;
        if (nowMs >= current.expiresAtMs) {
            current = null;
            return null;
        }
        return current;
    }

    public synchronized void resetForTests() {
        current = null;
        lastSessionId = null;
        lastIdentityKey = null;
        lastSequence = 0L;
        lastCapturedAtMs = 0L;
    }
}
