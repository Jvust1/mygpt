package dev.mygpt.spike;

import java.util.LinkedHashSet;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Process-local signed-Book study supervision runtime.
 *
 * Android signature permission is enforced before BookStudySignalReceiver calls
 * this class. This runtime adds sequence/epoch/TTL/context checks and maps only
 * explicit Book events to quiet-first companion cues.
 */
public final class StudySupervisorRuntime {
    public interface Listener {
        void onSupervisionChanged(
                CompanionCoordinator.Cue cue,
                boolean supervisionOptIn,
                String status
        );
    }

    private static final Pattern ID =
            Pattern.compile("^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$");
    private static final long MAX_TTL_MS = 300000L;

    private static final StudySupervisorRuntime SHARED =
            new StudySupervisorRuntime();

    private final Set<Listener> listeners = new LinkedHashSet<>();

    private CompanionCoordinator coordinator;
    private CompanionCoordinator.Cue currentCue;
    private String activeSessionId;
    private boolean supervisionOptIn;
    private String lastStatus = "IDLE";

    private StudySupervisorRuntime() {
        rebuildCoordinator();
    }

    public static StudySupervisorRuntime shared() {
        return SHARED;
    }

    public synchronized void addListener(Listener listener) {
        if (listener == null) throw new IllegalArgumentException("listener is required");
        listeners.add(listener);
        notifyOne(listener);
    }

    public synchronized void removeListener(Listener listener) {
        if (listener != null) listeners.remove(listener);
    }

    public synchronized CompanionCoordinator.Cue currentCue() {
        return currentCue;
    }

    public synchronized boolean hasActiveSession() {
        return activeSessionId != null;
    }

    public synchronized boolean isSupervisionOptIn() {
        return supervisionOptIn;
    }

    /**
     * User-controlled. Supervision opt-in is valid only inside an active session.
     */
    public synchronized boolean setSupervisionOptIn(boolean enabled) {
        if (activeSessionId == null) {
            supervisionOptIn = false;
            lastStatus = "NO_ACTIVE_SESSION";
            notifyAllListeners();
            return false;
        }
        supervisionOptIn = enabled;
        coordinator.setSupervisionOptIn(enabled);
        lastStatus = enabled ? "SUPERVISION_OPTED_IN" : "SUPERVISION_OPTED_OUT";
        currentCue = coordinator.currentCue();
        notifyAllListeners();
        return true;
    }

    public synchronized CompanionCoordinator.Result acceptSigned(
            String kindWire,
            String sessionId,
            long sequence,
            long epoch,
            long expiresAtMs,
            long nowMs
    ) {
        if (kindWire == null) throw new IllegalArgumentException("kind is required");
        if (sessionId == null || !ID.matcher(sessionId).matches()) {
            throw new IllegalArgumentException("invalid study session id");
        }
        if (sequence < 1L || epoch < 1L) {
            throw new IllegalArgumentException("invalid study event sequence/epoch");
        }
        long ttl = expiresAtMs - nowMs;
        if (ttl <= 0L || ttl > MAX_TTL_MS) {
            throw new IllegalArgumentException("invalid study event TTL");
        }

        CompanionCoordinator.Kind kind;
        try {
            kind = CompanionCoordinator.Kind.valueOf(kindWire);
        } catch (IllegalArgumentException error) {
            throw new IllegalArgumentException("invalid study event kind") ;
        }

        BookContextSnapshot context = BookContextMailbox.shared().current(nowMs);
        String sourceRef = null;
        if (requiresContext(kind) && context != null
                && sessionId.equals(context.sessionId)) {
            sourceRef = context.coordinatorReference();
        }

        CompanionCoordinator.BookEvent event =
                new CompanionCoordinator.BookEvent(
                        kind,
                        sessionId,
                        sequence,
                        epoch,
                        expiresAtMs,
                        sourceRef
                );

        CompanionCoordinator.Result result = coordinator.accept(event, nowMs);
        currentCue = coordinator.currentCue();

        if (result.accepted) {
            if (kind == CompanionCoordinator.Kind.SESSION_STARTED) {
                activeSessionId = sessionId;
                supervisionOptIn = false;
            } else if (kind == CompanionCoordinator.Kind.SESSION_ENDED) {
                activeSessionId = null;
                supervisionOptIn = false;
            }
            lastStatus = "ACCEPTED_" + kind.name();
        } else {
            lastStatus = "REJECTED_" + result.reason;
        }

        notifyAllListeners();
        return result;
    }

    public synchronized void revokeSignedSession() {
        coordinator.revokeSession();
        activeSessionId = null;
        supervisionOptIn = false;
        currentCue = coordinator.currentCue();
        lastStatus = "SESSION_REVOKED";
        notifyAllListeners();
    }

    public synchronized void resetForTests() {
        listeners.clear();
        activeSessionId = null;
        supervisionOptIn = false;
        lastStatus = "IDLE";
        rebuildCoordinator();
    }

    private void rebuildCoordinator() {
        coordinator = new CompanionCoordinator(
                this::isCurrentBookAuthority,
                cue -> {
                    synchronized (StudySupervisorRuntime.this) {
                        currentCue = cue;
                    }
                }
        );
        currentCue = coordinator.currentCue();
    }

    private boolean isCurrentBookAuthority(
            CompanionCoordinator.BookEvent event,
            long nowMs
    ) {
        if (!requiresContext(event.kind)) {
            return true;
        }
        BookContextSnapshot context = BookContextMailbox.shared().current(nowMs);
        return context != null
                && event.sessionId.equals(context.sessionId)
                && event.sourceRef != null
                && event.sourceRef.equals(context.coordinatorReference());
    }

    private static boolean requiresContext(CompanionCoordinator.Kind kind) {
        return kind == CompanionCoordinator.Kind.CONTEXT_CHANGED
                || kind == CompanionCoordinator.Kind.HELP_REQUESTED
                || kind == CompanionCoordinator.Kind.PRACTICE_REPEATED_ERROR;
    }

    private void notifyAllListeners() {
        Listener[] snapshot = listeners.toArray(new Listener[0]);
        for (Listener listener : snapshot) {
            notifyOne(listener);
        }
    }

    private void notifyOne(Listener listener) {
        try {
            listener.onSupervisionChanged(
                    currentCue,
                    supervisionOptIn,
                    lastStatus
            );
        } catch (RuntimeException ignored) {
            // UI listener failures never alter the accepted signed event.
        }
    }
}
