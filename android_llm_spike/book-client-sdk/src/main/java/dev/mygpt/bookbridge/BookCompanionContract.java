package dev.mygpt.bookbridge;

/** Public wire constants shared by Book-side producers. */
public final class BookCompanionContract {
    public static final String TARGET_PACKAGE = "dev.mygpt.companionv2";
    public static final String PERMISSION =
            "dev.mygpt.companionv2.permission.BOOK_CONTEXT";

    public static final String ACTION_CONTEXT =
            "dev.mygpt.companionv2.action.BOOK_CONTEXT_V1";
    public static final String ACTION_CONTEXT_CLEAR =
            "dev.mygpt.companionv2.action.BOOK_CONTEXT_CLEAR_V1";
    public static final String ACTION_STUDY_EVENT =
            "dev.mygpt.companionv2.action.BOOK_STUDY_EVENT_V1";

    private BookCompanionContract() {}

    public enum Mode {
        PREVIEW("preview"),
        LEARN("learn"),
        REVIEW("review"),
        PRACTICE("practice");

        public final String wireValue;

        Mode(String wireValue) {
            this.wireValue = wireValue;
        }
    }

    public enum StudyKind {
        SESSION_STARTED,
        CONTEXT_CHANGED,
        SESSION_PAUSED,
        SESSION_RESUMED,
        SESSION_ENDED,
        HELP_REQUESTED,
        PRACTICE_REPEATED_ERROR,
        REVOKE
    }
}
