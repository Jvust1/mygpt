package dev.mygpt.spike;

import java.util.ArrayList;
import java.util.List;

/** Executable, dependency-free acceptance checks for the Android integration boundary. */
public final class CompanionCoordinatorSmoke {
    private static void check(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }

    public static void main(String[] args) {
        List<CompanionCoordinator.Cue> shown = new ArrayList<>();
        final boolean[] authorized = {true};
        CompanionCoordinator c = new CompanionCoordinator((event, now) -> authorized[0], shown::add);
        check(c.currentCue() == CompanionCoordinator.Cue.QUIET, "quiet default");
        long t = 1_000_000L;
        check(c.accept(e(CompanionCoordinator.Kind.SESSION_STARTED, 1, 1, t + 5000, null), t).accepted,
                "trusted start");
        check(c.accept(e(CompanionCoordinator.Kind.PRACTICE_REPEATED_ERROR, 2, 1, t + 5000, "book-lease://source"), t).cue
                == CompanionCoordinator.Cue.QUIET, "no opt-in, no prompt");
        c.setSupervisionOptIn(true);
        check(c.accept(e(CompanionCoordinator.Kind.PRACTICE_REPEATED_ERROR, 3, 1, t + 5000, "book-lease://source"), t).cue
                == CompanionCoordinator.Cue.GENTLE_CHECK_IN, "opt-in prompt");
        c.setSupervisionOptIn(false);
        check(c.currentCue() == CompanionCoordinator.Cue.QUIET, "immediate opt-out");
        check(!c.accept(e(CompanionCoordinator.Kind.HELP_REQUESTED, 3, 1, t + 5000, "book-lease://source"), t).accepted,
                "duplicate event rejected");
        check(!c.accept(e(CompanionCoordinator.Kind.HELP_REQUESTED, 5, 1, t + 5000, "book-lease://source"), t).accepted,
                "sequence gap rejected");
        check(!c.accept(e(CompanionCoordinator.Kind.HELP_REQUESTED, 4, 1, t, "book-lease://source"), t).accepted,
                "expired event rejected");
        authorized[0] = false;
        check(!c.accept(e(CompanionCoordinator.Kind.HELP_REQUESTED, 4, 1, t + 5000, "book-lease://source"), t).accepted,
                "revoked authority rejected");
        authorized[0] = true;
        check(c.accept(e(CompanionCoordinator.Kind.HELP_REQUESTED, 4, 1, t + 5000, "book-lease://source"), t).cue
                == CompanionCoordinator.Cue.NEEDS_INPUT, "explicit help cue");
        check(c.accept(e(CompanionCoordinator.Kind.SESSION_PAUSED, 5, 1, t + 5000, null), t).cue
                == CompanionCoordinator.Cue.PAUSED, "pause");
        check(!c.accept(e(CompanionCoordinator.Kind.CONTEXT_CHANGED, 6, 1, t + 5000, "book-lease://source"), t).accepted,
                "paused cannot accept context");
        check(c.accept(e(CompanionCoordinator.Kind.SESSION_RESUMED, 6, 1, t + 5000, null), t).cue
                == CompanionCoordinator.Cue.QUIET, "resume quiet");
        check(!c.accept(e(CompanionCoordinator.Kind.HELP_REQUESTED, 7, 2, t + 5000, "book-lease://source"), t).accepted,
                "epoch mismatch");
        check(c.accept(e(CompanionCoordinator.Kind.SESSION_ENDED, 7, 1, t + 5000, null), t).accepted,
                "end");
        check(c.currentCue() == CompanionCoordinator.Cue.QUIET, "end quiet");
        check(!c.accept(e(CompanionCoordinator.Kind.SESSION_STARTED, 1, 1, t + 5000, null), t).accepted,
                "ended epoch cannot restart");
        check(c.accept(e(CompanionCoordinator.Kind.SESSION_STARTED, 1, 2, t + 5000, null), t).accepted,
                "new epoch can start");
        check(!c.accept(e(CompanionCoordinator.Kind.HELP_REQUESTED, 2, 2, t + 5000, "raw text"), t).accepted,
                "source must be opaque Book reference");
        check(c.accept(e(CompanionCoordinator.Kind.HELP_REQUESTED, 2, 2, t + 5000,
                "book-lease://source"), t).cue == CompanionCoordinator.Cue.NEEDS_INPUT, "new session help");
        c.revokeSession();
        check(c.currentCue() == CompanionCoordinator.Cue.QUIET, "revocation immediately quiets cue");
        check(!c.accept(e(CompanionCoordinator.Kind.HELP_REQUESTED, 3, 2, t + 5000,
                "book-lease://source"), t).accepted, "revoked session cannot continue");
        check(shown.contains(CompanionCoordinator.Cue.GENTLE_CHECK_IN), "renderer called");
        System.out.println("PASS: Android companion boundary smoke");
    }

    private static CompanionCoordinator.BookEvent e(CompanionCoordinator.Kind kind, long seq,
            long epoch, long expiry, String ref) {
        return new CompanionCoordinator.BookEvent(kind, "study-1", seq, epoch, expiry, ref);
    }
}
