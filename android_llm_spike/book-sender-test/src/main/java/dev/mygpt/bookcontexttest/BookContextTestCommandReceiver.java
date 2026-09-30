package dev.mygpt.bookcontexttest;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

import dev.mygpt.bookbridge.BookCompanionClient;
import dev.mygpt.bookbridge.BookCompanionContract;
import dev.mygpt.bookbridge.BookCompanionSession;
import dev.mygpt.bookbridge.BookContextPayload;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/**
 * Synthetic ADB-command entry point for physical-device bridge acceptance.
 *
 * All nested Book -> Companion deliveries use the reusable Book client SDK.
 * ADB only triggers this test app; Android still evaluates the test APK's
 * signing certificate against Companion V2's signature permission.
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

    private static final String BOOK_RESULT_FILE = "adb-book-result.txt";
    private static final String STUDY_RESULT_FILE = "adb-study-result.txt";

    private static final Object LOCK = new Object();
    private static BookCompanionSession session;

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
                clearContext(context, pending);
                return;
            }
            if (ACTION_STUDY_START.equals(action)) {
                startStudy(context, pending);
                return;
            }
            if (ACTION_STUDY_HELP.equals(action)) {
                sendStudy(
                        context,
                        pending,
                        BookCompanionContract.StudyKind.HELP_REQUESTED
                );
                return;
            }
            if (ACTION_STUDY_PAUSE.equals(action)) {
                sendStudy(
                        context,
                        pending,
                        BookCompanionContract.StudyKind.SESSION_PAUSED
                );
                return;
            }
            if (ACTION_STUDY_RESUME.equals(action)) {
                sendStudy(
                        context,
                        pending,
                        BookCompanionContract.StudyKind.SESSION_RESUMED
                );
                return;
            }
            if (ACTION_STUDY_REPEATED_ERROR.equals(action)) {
                sendStudy(
                        context,
                        pending,
                        BookCompanionContract.StudyKind.PRACTICE_REPEATED_ERROR
                );
                return;
            }
            if (ACTION_STUDY_END.equals(action)) {
                sendStudy(
                        context,
                        pending,
                        BookCompanionContract.StudyKind.SESSION_ENDED
                );
                return;
            }
            if (ACTION_STUDY_REVOKE.equals(action)) {
                revokeStudy(context, pending);
                return;
            }

            writeAndFinish(
                    context,
                    pending,
                    BOOK_RESULT_FILE,
                    "command=unknown\naccepted=false\n"
            );
        } catch (Throwable error) {
            String resultFile = action != null && action.contains("STUDY")
                    ? STUDY_RESULT_FILE
                    : BOOK_RESULT_FILE;
            writeAndFinish(
                    context,
                    pending,
                    resultFile,
                    "command=" + safe(action)
                            + "\naccepted=false"
                            + "\nerror=" + error.getClass().getSimpleName()
                            + "\n"
            );
        }
    }

    private static void sendFreshSyntheticContext(
            Context context,
            PendingResult pending
    ) {
        long now = System.currentTimeMillis();
        String sessionId = "adb-" + now;
        String body =
                "这是通过可复用 Book client SDK 发送的合成上下文。"
                + "它不是教材原文，只用于签名权限、sequence 与 SDK 验收。";

        BookCompanionSession next = new BookCompanionSession(
                sessionId,
                "functional-analysis-test",
                "synthetic-book",
                "test@v1"
        );
        synchronized (LOCK) {
            session = next;
        }

        BookContextPayload payload = new BookContextPayload(
                "functional-analysis-test",
                "synthetic-book",
                "test@v1",
                "ch1-s1",
                "adb-sdk-synthetic-1",
                sha256(body),
                BookCompanionContract.Mode.LEARN,
                "SDK synthetic section 1",
                body,
                120_000L
        );

        BookCompanionClient client = new BookCompanionClient(context);
        String preflight = client.preflight().status.name();
        client.sendContext(
                next,
                payload,
                result -> {
                    if (!result.accepted) {
                        synchronized (LOCK) {
                            if (session == next) session = null;
                        }
                    }
                    writeResult(
                            context,
                            BOOK_RESULT_FILE,
                            "command=context"
                                    + "\nsdk=true"
                                    + "\npreflight=" + preflight
                                    + "\nsession=" + sessionId
                                    + "\nsequence=" + next.contextSequence()
                                    + "\nsection_id=ch1-s1"
                                    + "\nresult_code=" + result.resultCode
                                    + "\nstatus=" + result.status
                                    + "\naccepted=" + result.accepted
                                    + "\n"
                    );
                    pending.finish();
                }
        );
    }

    private static void clearContext(
            Context context,
            PendingResult pending
    ) {
        final BookCompanionSession active = requireSession();
        BookCompanionClient client = new BookCompanionClient(context);
        String preflight = client.preflight().status.name();
        client.clearContext(
                active,
                result -> {
                    writeResult(
                            context,
                            BOOK_RESULT_FILE,
                            "command=clear"
                                    + "\nsdk=true"
                                    + "\npreflight=" + preflight
                                    + "\nsession=" + active.sessionId
                                    + "\nsequence=" + active.contextSequence()
                                    + "\nresult_code=" + result.resultCode
                                    + "\nstatus=" + result.status
                                    + "\naccepted=" + result.accepted
                                    + "\n"
                    );
                    if (result.accepted) {
                        synchronized (LOCK) {
                            if (session == active) session = null;
                        }
                    }
                    pending.finish();
                }
        );
    }

    private static void startStudy(
            Context context,
            PendingResult pending
    ) {
        final BookCompanionSession active = requireSession();
        BookCompanionClient client = new BookCompanionClient(context);
        String preflight = client.preflight().status.name();
        client.startStudy(
                active,
                120_000L,
                result -> finishStudyResult(
                        context,
                        pending,
                        active,
                        "SESSION_STARTED",
                        preflight,
                        result
                )
        );
    }

    private static void sendStudy(
            Context context,
            PendingResult pending,
            BookCompanionContract.StudyKind kind
    ) {
        final BookCompanionSession active = requireSession();
        BookCompanionClient client = new BookCompanionClient(context);
        String preflight = client.preflight().status.name();
        client.sendStudyEvent(
                active,
                kind,
                120_000L,
                result -> finishStudyResult(
                        context,
                        pending,
                        active,
                        kind.name(),
                        preflight,
                        result
                )
        );
    }

    private static void revokeStudy(
            Context context,
            PendingResult pending
    ) {
        final BookCompanionSession active = requireSession();
        BookCompanionClient client = new BookCompanionClient(context);
        String preflight = client.preflight().status.name();
        client.revokeStudy(
                active,
                result -> finishStudyResult(
                        context,
                        pending,
                        active,
                        "REVOKE",
                        preflight,
                        result
                )
        );
    }

    private static void finishStudyResult(
            Context context,
            PendingResult pending,
            BookCompanionSession active,
            String command,
            String preflight,
            BookCompanionClient.DeliveryResult result
    ) {
        writeResult(
                context,
                STUDY_RESULT_FILE,
                "command=" + command
                        + "\nsdk=true"
                        + "\npreflight=" + preflight
                        + "\nsession=" + active.sessionId
                        + "\nsequence=" + active.studySequence()
                        + "\nepoch=" + active.studyEpoch()
                        + "\nactive=" + active.studyActive()
                        + "\nresult_code=" + result.resultCode
                        + "\nstatus=" + result.status
                        + "\naccepted=" + result.accepted
                        + "\n"
        );
        pending.finish();
    }

    private static BookCompanionSession requireSession() {
        synchronized (LOCK) {
            if (session == null) {
                throw new IllegalStateException("no_active_sdk_session");
            }
            return session;
        }
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
