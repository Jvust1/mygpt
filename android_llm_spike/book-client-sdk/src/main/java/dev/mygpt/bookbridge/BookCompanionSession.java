package dev.mygpt.bookbridge;

import java.util.regex.Pattern;

/**
 * In-memory sequence/epoch state for one real Book study session.
 *
 * Sequence counters advance only after Companion V2 returns RESULT_OK.
 * If the Book process is recreated, start a new session id at sequence 1.
 */
public final class BookCompanionSession {
    private static final Pattern ID =
            Pattern.compile("^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$");
    private static final Pattern VERSION =
            Pattern.compile("^[A-Za-z0-9][A-Za-z0-9_.@-]{0,159}$");

    public final String sessionId;
    public final String courseId;
    public final String bookId;
    public final String bookVersion;

    private long contextSequence;
    private boolean contextPending;

    private long studySequence;
    private long studyEpoch;
    private boolean studyActive;
    private boolean studyPending;

    public BookCompanionSession(
            String sessionId,
            String courseId,
            String bookId,
            String bookVersion
    ) {
        this.sessionId = checkedId("sessionId", sessionId);
        this.courseId = checkedId("courseId", courseId);
        this.bookId = checkedId("bookId", bookId);
        if (bookVersion == null || !VERSION.matcher(bookVersion).matches()) {
            throw new IllegalArgumentException("invalid bookVersion");
        }
        this.bookVersion = bookVersion;
    }

    public synchronized long contextSequence() {
        return contextSequence;
    }

    public synchronized long studySequence() {
        return studySequence;
    }

    public synchronized long studyEpoch() {
        return studyEpoch;
    }

    public synchronized boolean studyActive() {
        return studyActive;
    }

    synchronized long reserveContextSequence() {
        if (contextPending) throw new IllegalStateException("Book context delivery already pending");
        contextPending = true;
        return contextSequence + 1L;
    }

    synchronized void finishContextSequence(long reserved, boolean accepted) {
        long expected = contextSequence + 1L;
        if (!contextPending || reserved != expected) {
            throw new IllegalStateException("Book context reservation mismatch");
        }
        contextPending = false;
        if (accepted) contextSequence = reserved;
    }

    synchronized StudyReservation reserveStudyStart(long nowMs) {
        if (studyPending) throw new IllegalStateException("Book study delivery already pending");
        if (studyActive) throw new IllegalStateException("Book study session already active");
        if (nowMs < 1L) throw new IllegalArgumentException("invalid study clock");

        long nextEpoch = Math.max(nowMs, studyEpoch + 1L);
        studyPending = true;
        return new StudyReservation(
                BookCompanionContract.StudyKind.SESSION_STARTED,
                1L,
                nextEpoch
        );
    }

    synchronized StudyReservation reserveStudyEvent(
            BookCompanionContract.StudyKind kind
    ) {
        if (kind == null) throw new IllegalArgumentException("study kind is required");
        if (kind == BookCompanionContract.StudyKind.SESSION_STARTED
                || kind == BookCompanionContract.StudyKind.REVOKE) {
            throw new IllegalArgumentException("use start/revoke methods");
        }
        if (studyPending) throw new IllegalStateException("Book study delivery already pending");
        if (!studyActive) throw new IllegalStateException("Book study session is not active");

        studyPending = true;
        return new StudyReservation(kind, studySequence + 1L, studyEpoch);
    }

    synchronized void finishStudy(StudyReservation reservation, boolean accepted) {
        if (reservation == null) throw new IllegalArgumentException("reservation is required");
        if (!studyPending) throw new IllegalStateException("no pending study delivery");

        studyPending = false;
        if (!accepted) return;

        if (reservation.kind == BookCompanionContract.StudyKind.SESSION_STARTED) {
            studyEpoch = reservation.epoch;
            studySequence = 1L;
            studyActive = true;
            return;
        }

        if (!studyActive
                || reservation.epoch != studyEpoch
                || reservation.sequence != studySequence + 1L) {
            throw new IllegalStateException("Book study reservation mismatch");
        }

        studySequence = reservation.sequence;
        if (reservation.kind == BookCompanionContract.StudyKind.SESSION_ENDED) {
            studyActive = false;
        }
    }

    synchronized void finishRevoke(boolean accepted) {
        if (!accepted) return;
        studyActive = false;
        studyPending = false;
    }

    static final class StudyReservation {
        final BookCompanionContract.StudyKind kind;
        final long sequence;
        final long epoch;

        StudyReservation(
                BookCompanionContract.StudyKind kind,
                long sequence,
                long epoch
        ) {
            this.kind = kind;
            this.sequence = sequence;
            this.epoch = epoch;
        }
    }

    private static String checkedId(String name, String value) {
        if (value == null || !ID.matcher(value).matches()) {
            throw new IllegalArgumentException("invalid " + name);
        }
        return value;
    }
}
