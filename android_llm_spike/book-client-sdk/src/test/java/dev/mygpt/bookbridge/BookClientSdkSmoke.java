package dev.mygpt.bookbridge;

public final class BookClientSdkSmoke {
    public static void main(String[] args) {
        BookCompanionSession session = new BookCompanionSession(
                "study-1",
                "course",
                "book",
                "book@v1"
        );

        BookContextPayload payload = new BookContextPayload(
                "course",
                "book",
                "book@v1",
                "section",
                "source",
                repeat('a', 64),
                BookCompanionContract.Mode.LEARN,
                "Title",
                "Synthetic structured context",
                120000L
        );
        payload.requireIdentity(session);

        long c1 = session.reserveContextSequence();
        check(c1 == 1L, "first context sequence");
        session.finishContextSequence(c1, false);
        check(session.contextSequence() == 0L, "rejected context does not advance");

        long c1Retry = session.reserveContextSequence();
        check(c1Retry == 1L, "rejected sequence can retry");
        session.finishContextSequence(c1Retry, true);
        check(session.contextSequence() == 1L, "accepted context advances");

        long c2 = session.reserveContextSequence();
        check(c2 == 2L, "second context sequence");
        session.finishContextSequence(c2, true);

        long now = 2_000_000_000_000L;
        BookCompanionSession.StudyReservation start = session.reserveStudyStart(now);
        check(start.sequence == 1L, "study start sequence");
        session.finishStudy(start, false);
        check(!session.studyActive(), "rejected start inactive");

        BookCompanionSession.StudyReservation startRetry =
                session.reserveStudyStart(now + 1L);
        check(startRetry.sequence == 1L, "study start retry sequence");
        session.finishStudy(startRetry, true);
        check(session.studyActive(), "accepted study active");
        check(session.studySequence() == 1L, "accepted study sequence");

        BookCompanionSession.StudyReservation help =
                session.reserveStudyEvent(BookCompanionContract.StudyKind.HELP_REQUESTED);
        check(help.sequence == 2L, "help sequence");
        session.finishStudy(help, false);
        check(session.studySequence() == 1L, "rejected help does not advance");

        BookCompanionSession.StudyReservation helpRetry =
                session.reserveStudyEvent(BookCompanionContract.StudyKind.HELP_REQUESTED);
        check(helpRetry.sequence == 2L, "help retry");
        session.finishStudy(helpRetry, true);
        check(session.studySequence() == 2L, "accepted help advances");

        BookCompanionSession.StudyReservation end =
                session.reserveStudyEvent(BookCompanionContract.StudyKind.SESSION_ENDED);
        session.finishStudy(end, true);
        check(!session.studyActive(), "end inactive");

        expectFailure(() -> new BookContextPayload(
                "different-course",
                "book",
                "book@v1",
                "section",
                "source",
                repeat('b', 64),
                BookCompanionContract.Mode.LEARN,
                "",
                "x",
                120000L
        ).requireIdentity(session), "identity mismatch");

        System.out.println("BookClientSdkSmoke PASS");
    }

    private static String repeat(char ch, int count) {
        StringBuilder out = new StringBuilder(count);
        for (int i = 0; i < count; i++) out.append(ch);
        return out.toString();
    }

    private static void expectFailure(Runnable action, String label) {
        try {
            action.run();
            throw new AssertionError("expected failure: " + label);
        } catch (IllegalArgumentException expected) {
            // pass
        }
    }

    private static void check(boolean value, String label) {
        if (!value) throw new AssertionError(label);
    }
}
