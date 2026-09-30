package dev.mygpt.spike;

import java.util.ArrayList;
import java.util.List;

public final class StudySupervisorRuntimeSmoke {
    public static void main(String[] args) {
        BookContextMailbox mailbox = BookContextMailbox.shared();
        mailbox.resetForTests();

        StudySupervisorRuntime runtime = StudySupervisorRuntime.shared();
        runtime.resetForTests();

        List<CompanionCoordinator.Cue> cues = new ArrayList<>();
        List<String> states = new ArrayList<>();
        StudySupervisorRuntime.Listener listener = (cue, optedIn, status) -> {
            cues.add(cue);
            states.add(status + ":" + optedIn);
        };
        runtime.addListener(listener);

        long now = 1_900_000_000_000L;
        String session = "study-1";
        long epoch = 10L;

        check(runtime.acceptSigned(
                "SESSION_STARTED", session, 1, epoch, now + 60000, now
        ).accepted, "start");
        check(!runtime.isSupervisionOptIn(), "start resets opt-in");
        check(runtime.setSupervisionOptIn(true), "opt-in active session");
        String activeBlock = runtime.snapshot().dataBlock();
        check(activeBlock.contains("STUDY_SUPERVISION_STATE_JSON"), "supervision data block");
        check(activeBlock.contains("\"active\":true"), "active supervision state");
        check(activeBlock.contains("\"opt_in\":true"), "opt-in state");

        BookContextSnapshot context = new BookContextSnapshot(
                session,
                1,
                "course",
                "book",
                "book@v1",
                "section",
                "source",
                repeat('a', 64),
                BookContextSnapshot.Mode.PRACTICE,
                now,
                now + 60000,
                "Practice",
                "Synthetic context"
        );
        mailbox.accept(context, now + 1);

        CompanionCoordinator.Result repeated = runtime.acceptSigned(
                "PRACTICE_REPEATED_ERROR", session, 2, epoch, now + 60000, now + 2
        );
        check(repeated.accepted, "repeated error accepted");
        check(repeated.cue == CompanionCoordinator.Cue.GENTLE_CHECK_IN,
                "opt-in gentle check in");

        CompanionCoordinator.Result help = runtime.acceptSigned(
                "HELP_REQUESTED", session, 3, epoch, now + 60000, now + 3
        );
        check(help.accepted, "help accepted");
        check(help.cue == CompanionCoordinator.Cue.NEEDS_INPUT, "help cue");

        check(runtime.acceptSigned(
                "SESSION_PAUSED", session, 4, epoch, now + 60000, now + 4
        ).cue == CompanionCoordinator.Cue.PAUSED, "pause cue");

        check(runtime.acceptSigned(
                "SESSION_RESUMED", session, 5, epoch, now + 60000, now + 5
        ).cue == CompanionCoordinator.Cue.QUIET, "resume quiet");

        mailbox.clear(session, 2, now + 6, now + 6);
        CompanionCoordinator.Result missingContext = runtime.acceptSigned(
                "CONTEXT_CHANGED", session, 6, epoch, now + 60000, now + 7
        );
        check(!missingContext.accepted, "context event rejected without current context");

        check(runtime.acceptSigned(
                "SESSION_ENDED", session, 6, epoch, now + 60000, now + 8
        ).accepted, "end accepted");
        check(!runtime.hasActiveSession(), "ended inactive");
        check(!runtime.isSupervisionOptIn(), "ended clears opt-in");
        check(runtime.snapshot().dataBlock().contains("\"active\":false"),
                "ended data block inactive");

        runtime.removeListener(listener);
        check(cues.contains(CompanionCoordinator.Cue.GENTLE_CHECK_IN),
                "listener observed gentle cue");
        check(states.stream().anyMatch(value -> value.startsWith("ACCEPTED_HELP_REQUESTED")),
                "listener observed status");

        System.out.println("StudySupervisorRuntimeSmoke PASS");
    }

    private static String repeat(char ch, int count) {
        StringBuilder out = new StringBuilder(count);
        for (int i = 0; i < count; i++) out.append(ch);
        return out.toString();
    }

    private static void check(boolean value, String label) {
        if (!value) throw new AssertionError(label);
    }
}
