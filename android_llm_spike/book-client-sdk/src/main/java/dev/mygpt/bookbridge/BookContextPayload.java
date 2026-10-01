package dev.mygpt.bookbridge;

import java.util.regex.Pattern;

/**
 * Validated Book semantic payload. It contains no Android dependency and stores
 * no data by itself.
 */
public final class BookContextPayload {
    private static final Pattern ID =
            Pattern.compile("^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$");
    private static final Pattern VERSION =
            Pattern.compile("^[A-Za-z0-9][A-Za-z0-9_.@-]{0,159}$");
    private static final Pattern SHA256 =
            Pattern.compile("^[0-9a-f]{64}$");

    public final String courseId;
    public final String bookId;
    public final String bookVersion;
    public final String sectionId;
    public final String sourceId;
    public final String sourceSha256;
    public final BookCompanionContract.Mode mode;
    public final String title;
    public final String text;
    public final long ttlMs;

    public BookContextPayload(
            String courseId,
            String bookId,
            String bookVersion,
            String sectionId,
            String sourceId,
            String sourceSha256,
            BookCompanionContract.Mode mode,
            String title,
            String text,
            long ttlMs
    ) {
        this.courseId = checkedId("courseId", courseId);
        this.bookId = checkedId("bookId", bookId);
        this.bookVersion = checkedVersion(bookVersion);
        this.sectionId = checkedId("sectionId", sectionId);
        this.sourceId = checkedId("sourceId", sourceId);

        if (sourceSha256 == null || !SHA256.matcher(sourceSha256).matches()) {
            throw new IllegalArgumentException("invalid sourceSha256");
        }
        this.sourceSha256 = sourceSha256;

        if (mode == null) throw new IllegalArgumentException("mode is required");
        this.mode = mode;

        this.title = checkedText("title", title == null ? "" : title, 500, true);
        this.text = checkedText("text", text, 6000, false);

        if (ttlMs < 1L || ttlMs > 300000L) {
            throw new IllegalArgumentException("ttlMs must be in 1..300000");
        }
        this.ttlMs = ttlMs;
    }

    void requireIdentity(BookCompanionSession session) {
        if (!courseId.equals(session.courseId)
                || !bookId.equals(session.bookId)
                || !bookVersion.equals(session.bookVersion)) {
            throw new IllegalArgumentException(
                    "Book context identity does not match the active session");
        }
    }

    private static String checkedId(String name, String value) {
        if (value == null || !ID.matcher(value).matches()) {
            throw new IllegalArgumentException("invalid " + name);
        }
        return value;
    }

    private static String checkedVersion(String value) {
        if (value == null || !VERSION.matcher(value).matches()) {
            throw new IllegalArgumentException("invalid bookVersion");
        }
        return value;
    }

    private static String checkedText(
            String name,
            String value,
            int maxChars,
            boolean allowEmpty
    ) {
        if (value == null) throw new IllegalArgumentException(name + " is required");
        if (!allowEmpty && value.trim().isEmpty()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        if (value.length() > maxChars) {
            throw new IllegalArgumentException(name + " too long");
        }
        for (int i = 0; i < value.length(); i++) {
            char ch = value.charAt(i);
            if (ch < 32 && ch != '\n' && ch != '\r' && ch != '\t') {
                throw new IllegalArgumentException(name + " contains control characters");
            }
        }
        return value;
    }
}
