package dev.mygpt.bookcontexttest;

import android.app.Activity;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/**
 * Synthetic ADB-command entry point for physical-device bridge acceptance.
 *
 * ADB invokes this exported receiver, but nested Book broadcasts are sent by
 * this app's UID, so Companion V2 still enforces its real signature permission.
 */
public final class BookContextTestCommandReceiver extends BroadcastReceiver {
    public static final String ACTION_SEND =
            "dev.mygpt.bookcontexttest.action.AUTOMATED_SEND_CONTEXT_V1";
    public static final String ACTION_CLEAR =
            "dev.mygpt.bookcontexttest.action.AUTOMATED_CLEAR_CONTEXT_V1";

    public static final String ACTION_STUDY_START =
            "dev.mygpt.bookcontexttest.action.AUTOMATED_STUDY_START_V1";
    public static final String ACTION_STUDY_HELP =
            "dev.mygpt.bookcontexttest.action.AUTOMATED_STUDY_HELP_V1";
    public static final String ACTION_STUDY_PAUSE =
            "dev.mygpt.bookcontexttest.action.AUTOMATED_STUDY_PAUSE_V1";
    public static final String ACTION_STUDY_RESUME =
            "dev.mygpt.bookcontexttest.action.AUTOMATED_STUDY_RESUME_V1";
    public static final String ACTION_STUDY_REPEATED_ERROR =
            "dev.mygpt.bookcontexttest.action.AUTOMATED_STUDY_REPEATED_ERROR_V1";
    public static final String ACTION_STUDY_END =
            "dev.mygpt.bookcontexttest.action.AUTOMATED_STUDY_END_V1";
    public static final String ACTION_STUDY_REVOKE =
            "dev.mygpt.bookcontexttest.action.AUTOMATED_STUDY_REVOKE_V1";

    private static final String TARGET_PACKAGE = "dev.mygpt.companionv2";
    private static final String TARGET_ACTION =
            "dev.mygpt.companionv2.action.BOOK_CONTEXT_V1";
    private static final String TARGET_CLEAR =
            "dev.mygpt.companionv2.action.BOOK_CONTEXT_CLEAR_V1";
    private static final String TARGET_STUDY =
            "dev.mygpt.companionv2.action.BOOK_STUDY_EVENT_V1";

    private static final String PREFS = "book_context_test_sender";
    private static final String KEY_SESSION = "session";
    private static final String KEY_SEQUENCE = "sequence";
    private static final String KEY_SECTION = "section";
    private static final String KEY_STUDY_SEQUENCE = "study_sequence";
    private static final String KEY_STUDY_EPOCH = "study_epoch";

    private static final String BOOK_RESULT_FILE = "adb-book-result.txt";
    private static final String STUDY_RESULT_FILE = "adb-study-result.txt";

    @Override
    public void onReceive(Context context, Intent intent) {
        final PendingResult pending = goAsync();
        final String action = intent == null ? null : intent.getAction();

        try {
            if (ACTION_SEND.equals(action)) {
                sendFreshSyntheticContext(context, pending);
                return;
            }
            if (ACTION_CLEAR.equals(action)) {
                sendClear(context, pending);
                return;
            }
            if (ACTION_STUDY_START.equals(action)) {
                sendStudyStart(context, pending);
                return;
            }
            if (ACTION_STUDY_HELP.equals(action)) {
                sendStudyEvent(context, pending, "HELP_REQUESTED", true);
                return;
            }
            if (ACTION_STUDY_PAUSE.equals(action)) {
                sendStudyEvent(context, pending, "SESSION_PAUSED", false);
                return;
            }
            if (ACTION_STUDY_RESUME.equals(action)) {
                sendStudyEvent(context, pending, "SESSION_RESUMED", false);
                return;
            }
            if (ACTION_STUDY_REPEATED_ERROR.equals(action)) {
                sendStudyEvent(context, pending, "PRACTICE_REPEATED_ERROR", true);
                return;
            }
            if (ACTION_STUDY_END.equals(action)) {
                sendStudyEvent(context, pending, "SESSION_ENDED", false);
                return;
            }
            if (ACTION_STUDY_REVOKE.equals(action)) {
                sendStudyRevoke(context, pending);
                return;
            }

            writeResult(
                    context,
                    BOOK_RESULT_FILE,
                    "command=unknown\naccepted=false\n"
            );
        } catch (Throwable error) {
            String resultFile = action != null && action.contains("STUDY")
                    ? STUDY_RESULT_FILE
                    : BOOK_RESULT_FILE;
            writeResult(
                    context,
                    resultFile,
                    "command=" + safe(action)
                            + "\naccepted=false"
                            + "\nerror=" + error.getClass().getSimpleName()
                            + "\n"
            );
        }
        pending.finish();
    }

    private static void sendFreshSyntheticContext(
            Context context,
            PendingResult pending
    ) {
        long now = System.currentTimeMillis();
        String session = "adb-" + now;
        long sequence = 1L;
        int section = 1;
        String sectionId = "ch1-s1";
        String sourceId = "adb-synthetic-1";
        String body =
                "这是同签名测试 sender 通过 ADB 自动触发的合成 Book 上下文。"
                + "它不是教材原文，只用于 signature permission 与时序验收。";

        SharedPreferences prefs =
                context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        prefs.edit()
                .putString(KEY_SESSION, session)
                .putLong(KEY_SEQUENCE, sequence)
                .putInt(KEY_SECTION, section)
                .putLong(KEY_STUDY_SEQUENCE, 0L)
                .putLong(KEY_STUDY_EPOCH, 0L)
                .apply();

        Intent target = new Intent(TARGET_ACTION);
        target.setPackage(TARGET_PACKAGE);
        target.putExtra("session_id", session);
        target.putExtra("sequence", sequence);
        target.putExtra("course_id", "functional-analysis-test");
        target.putExtra("book_id", "synthetic-book");
        target.putExtra("book_version", "test@v1");
        target.putExtra("section_id", sectionId);
        target.putExtra("source_id", sourceId);
        target.putExtra("source_sha256", sha256(body));
        target.putExtra("mode", "learn");
        target.putExtra("captured_at_ms", now);
        target.putExtra("expires_at_ms", now + 120_000L);
        target.putExtra("title", "ADB synthetic section 1");
        target.putExtra("text", body);

        sendOrdered(
                context,
                target,
                pending,
                BOOK_RESULT_FILE,
                "context",
                session,
                sequence,
                sectionId
        );
    }

    private static void sendClear(Context context, PendingResult pending) {
        SharedPreferences prefs =
                context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String session = prefs.getString(KEY_SESSION, null);
        long previous = prefs.getLong(KEY_SEQUENCE, 0L);

        if (session == null || previous < 1L) {
            writeAndFinish(
                    context,
                    pending,
                    BOOK_RESULT_FILE,
                    "command=clear\naccepted=false\nerror=no_active_test_session\n"
            );
            return;
        }

        long sequence = previous + 1L;
        prefs.edit().putLong(KEY_SEQUENCE, sequence).apply();

        Intent target = new Intent(TARGET_CLEAR);
        target.setPackage(TARGET_PACKAGE);
        target.putExtra("session_id", session);
        target.putExtra("sequence", sequence);
        target.putExtra("occurred_at_ms", System.currentTimeMillis());

        sendOrdered(
                context,
                target,
                pending,
                BOOK_RESULT_FILE,
                "clear",
                session,
                sequence,
                ""
        );
    }

    private static void sendStudyStart(Context context, PendingResult pending) {
        SharedPreferences prefs =
                context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String session = prefs.getString(KEY_SESSION, null);
        if (session == null) {
            writeAndFinish(
                    context,
                    pending,
                    STUDY_RESULT_FILE,
                    "command=SESSION_STARTED\naccepted=false\nerror=no_context_session\n"
            );
            return;
        }

        long epoch = System.currentTimeMillis();
        if (epoch < 1L) epoch = 1L;

        prefs.edit()
                .putLong(KEY_STUDY_EPOCH, epoch)
                .putLong(KEY_STUDY_SEQUENCE, 1L)
                .apply();

        Intent target = studyIntent(
                session,
                "SESSION_STARTED",
                1L,
                epoch,
                System.currentTimeMillis() + 120_000L
        );
        sendOrdered(
                context,
                target,
                pending,
                STUDY_RESULT_FILE,
                "SESSION_STARTED",
                session,
                1L,
                ""
        );
    }

    private static void sendStudyEvent(
            Context context,
            PendingResult pending,
            String kind,
            boolean needsFreshContext
    ) {
        SharedPreferences prefs =
                context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String session = prefs.getString(KEY_SESSION, null);
        long epoch = prefs.getLong(KEY_STUDY_EPOCH, 0L);
        long previous = prefs.getLong(KEY_STUDY_SEQUENCE, 0L);

        if (session == null || epoch < 1L || previous < 1L) {
            writeAndFinish(
                    context,
                    pending,
                    STUDY_RESULT_FILE,
                    "command=" + kind
                            + "\naccepted=false\nerror=no_active_study_session\n"
            );
            return;
        }

        if (needsFreshContext) {
            // The Companion is authoritative for context freshness. This flag is
            // only recorded in the test result; it does not bypass that check.
        }

        long next = previous + 1L;
        prefs.edit().putLong(KEY_STUDY_SEQUENCE, next).apply();

        Intent target = studyIntent(
                session,
                kind,
                next,
                epoch,
                System.currentTimeMillis() + 120_000L
        );
        sendOrdered(
                context,
                target,
                pending,
                STUDY_RESULT_FILE,
                kind,
                session,
                next,
                ""
        );
    }

    private static void sendStudyRevoke(
            Context context,
            PendingResult pending
    ) {
        Intent target = new Intent(TARGET_STUDY);
        target.setPackage(TARGET_PACKAGE);
        target.putExtra("kind", "REVOKE");
        sendOrdered(
                context,
                target,
                pending,
                STUDY_RESULT_FILE,
                "REVOKE",
                "",
                0L,
                ""
        );
    }

    private static Intent studyIntent(
            String session,
            String kind,
            long sequence,
            long epoch,
            long expiresAtMs
    ) {
        Intent target = new Intent(TARGET_STUDY);
        target.setPackage(TARGET_PACKAGE);
        target.putExtra("kind", kind);
        target.putExtra("session_id", session);
        target.putExtra("sequence", sequence);
        target.putExtra("epoch", epoch);
        target.putExtra("expires_at_ms", expiresAtMs);
        return target;
    }

    private static void sendOrdered(
            Context context,
            Intent target,
            PendingResult pending,
            String resultFile,
            String command,
            String session,
            long sequence,
            String sectionId
    ) {
        Handler main = new Handler(Looper.getMainLooper());

        context.sendOrderedBroadcast(
                target,
                null,
                new BroadcastReceiver() {
                    @Override
                    public void onReceive(Context resultContext, Intent ignored) {
                        int code = getResultCode();
                        boolean accepted = code == Activity.RESULT_OK;
                        writeResult(
                                resultContext,
                                resultFile,
                                "command=" + command
                                        + "\nsession=" + session
                                        + "\nsequence=" + sequence
                                        + "\nsection_id=" + sectionId
                                        + "\nresult_code=" + code
                                        + "\naccepted=" + accepted
                                        + "\n"
                        );
                        pending.finish();
                    }
                },
                main,
                Activity.RESULT_CANCELED,
                null,
                null
        );
    }

    private static void writeAndFinish(
            Context context,
            PendingResult pending,
            String file,
            String value
    ) {
        writeResult(context, file, value);
        pending.finish();
    }

    private static void writeResult(
            Context context,
            String fileName,
            String value
    ) {
        File target = new File(context.getFilesDir(), fileName);
        File temp = new File(context.getFilesDir(), fileName + ".tmp");

        try (FileOutputStream output = new FileOutputStream(temp, false)) {
            output.write(value.getBytes(StandardCharsets.UTF_8));
            output.flush();
            output.getFD().sync();
        } catch (IOException ignored) {
            return;
        }

        if (target.exists() && !target.delete()) {
            temp.delete();
            return;
        }
        if (!temp.renameTo(target)) {
            temp.delete();
        }
    }

    private static String sha256(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder out = new StringBuilder(64);
            for (byte b : hash) {
                out.append(String.format("%02x", b & 0xFF));
            }
            return out.toString();
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException(impossible);
        }
    }

    private static String safe(String value) {
        return value == null ? "null" : value.replace("\n", "").replace("\r", "");
    }
}
