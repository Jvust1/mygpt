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
 * ADB invokes this exported receiver, but the nested Book-context broadcast is
 * sent by this app's UID. Therefore Companion V2 still enforces the real
 * signature permission between the two installed APKs.
 */
public final class BookContextTestCommandReceiver extends BroadcastReceiver {
    public static final String ACTION_SEND =
            "dev.mygpt.bookcontexttest.action.AUTOMATED_SEND_CONTEXT_V1";
    public static final String ACTION_CLEAR =
            "dev.mygpt.bookcontexttest.action.AUTOMATED_CLEAR_CONTEXT_V1";

    private static final String TARGET_PACKAGE = "dev.mygpt.companionv2";
    private static final String TARGET_ACTION =
            "dev.mygpt.companionv2.action.BOOK_CONTEXT_V1";
    private static final String TARGET_CLEAR =
            "dev.mygpt.companionv2.action.BOOK_CONTEXT_CLEAR_V1";

    private static final String PREFS = "book_context_test_sender";
    private static final String KEY_SESSION = "session";
    private static final String KEY_SEQUENCE = "sequence";
    private static final String KEY_SECTION = "section";
    private static final String RESULT_FILE = "adb-book-result.txt";

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
            writeResult(context, "command=unknown\naccepted=false\n");
        } catch (Throwable error) {
            writeResult(
                    context,
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
            writeResult(
                    context,
                    "command=clear\naccepted=false\nerror=no_active_test_session\n"
            );
            pending.finish();
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
                "clear",
                session,
                sequence,
                ""
        );
    }

    private static void sendOrdered(
            Context context,
            Intent target,
            PendingResult pending,
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

    private static void writeResult(Context context, String value) {
        File target = new File(context.getFilesDir(), RESULT_FILE);
        File temp = new File(context.getFilesDir(), RESULT_FILE + ".tmp");

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
