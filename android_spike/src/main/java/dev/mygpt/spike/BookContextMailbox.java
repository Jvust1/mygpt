package dev.mygpt.spike;

import java.util.LinkedHashSet;
import java.util.Set;

/**
 * Process-memory-only Book context mailbox.
 *
 * Accepted contexts are never written to disk. Sequence/session state remains
 * in memory only to reject stale/replayed deliveries while the process lives.
 */
public final class BookContextMailbox {
    public interface Listener {
        void onBookContextChanged(BookContextSnapshot current);
    }

    private static final BookContextMailbox SHARED = new BookContextMailbox();

    private final Set<Listener> listeners = new LinkedHashSet<>();

    private BookContextSnapshot current;
    private String lastSessionId;
    private String lastIdentityKey;
    private long lastSequence;
    private long lastCapturedAtMs;

    public static BookContextMailbox shared() {
        return SHARED;
    }

    public synchronized void addListener(Listener listener) {
        if (listener == null) throw new IllegalArgumentException("listener is required");
        listeners.add(listener);
    }

    public synchronized void removeListener(Listener listener) {
        if (listener != null) listeners.remove(listener);
    }

    public BookContextSnapshot accept(
            BookContextSnapshot next,
            long nowMs
    ) {
        BookContextSnapshot accepted;
        Listener[] snapshot;
        synchronized (this) {
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
            accepted = next;
            snapshot = listeners.toArray(new Listener[0]);
        }
        notifyListeners(snapshot, accepted);
        return accepted;
    }

    public boolean clear(
            String sessionId,
            long sequence,
            long occurredAtMs,
            long nowMs
    ) {
        Listener[] snapshot;
        synchronized (this) {
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
            snapshot = listeners.toArray(new Listener[0]);
        }
        notifyListeners(snapshot, null);
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
        listeners.clear();
    }

    private static void notifyListeners(
            Listener[] listeners,
            BookContextSnapshot current
    ) {
        for (Listener listener : listeners) {
            try {
                listener.onBookContextChanged(current);
            } catch (RuntimeException ignored) {
                // A UI/listener bug must not roll back a valid Book context update.
            }
        }
    }
}
