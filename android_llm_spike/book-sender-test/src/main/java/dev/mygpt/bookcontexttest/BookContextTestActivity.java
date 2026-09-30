package dev.mygpt.bookcontexttest;

import android.app.Activity;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/**
 * Synthetic same-signature producer used only to validate the Companion V2
 * Book-context receiver on a physical device.
 */
public final class BookContextTestActivity extends Activity {
    private static final String TARGET_PACKAGE = "dev.mygpt.companionv2";
    private static final String PERMISSION =
            "dev.mygpt.companionv2.permission.BOOK_CONTEXT";
    private static final String ACTION_CONTEXT =
            "dev.mygpt.companionv2.action.BOOK_CONTEXT_V1";
    private static final String ACTION_CLEAR =
            "dev.mygpt.companionv2.action.BOOK_CONTEXT_CLEAR_V1";

    private static final String PREFS = "book_context_test_sender";
    private static final String KEY_SESSION = "session";
    private static final String KEY_SEQUENCE = "sequence";
    private static final String KEY_SECTION = "section";

    private final Handler main = new Handler(Looper.getMainLooper());

    private TextView status;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);

        ScrollView scroll = new ScrollView(this);
        LinearLayout page = new LinearLayout(this);
        page.setOrientation(LinearLayout.VERTICAL);
        page.setPadding(dp(18), dp(22), dp(18), dp(28));
        scroll.addView(page);
        setContentView(scroll);

        TextView title = text("Book Context Test Sender", 25);
        page.addView(title);
        page.addView(text(
                "Synthetic producer only · same debug signature required", 13));

        status = text("准备就绪。先安装 Companion V2，再安装本测试 APK。", 13);
        status.setPadding(0, dp(14), 0, dp(10));
        page.addView(status);

        page.addView(button("新建测试学习会话", this::newSession));
        page.addView(button("发送新鲜 Book 上下文", this::sendFreshContext));
        page.addView(button("切换到下一节并发送", this::sendNextSection));
        page.addView(button("清除当前 Book 上下文", this::sendClear));
    }

    private void newSession() {
        String session = "test-" + System.currentTimeMillis();
        getSharedPreferences(PREFS, MODE_PRIVATE)
                .edit()
                .putString(KEY_SESSION, session)
                .putLong(KEY_SEQUENCE, 0L)
                .putInt(KEY_SECTION, 1)
                .apply();
        status.setText("新会话：" + session + " · 下一条 sequence=1");
    }

    private void sendFreshContext() {
        ensureSession();
        int section = getSharedPreferences(PREFS, MODE_PRIVATE)
                .getInt(KEY_SECTION, 1);
        sendContext(section);
    }

    private void sendNextSection() {
        ensureSession();
        int section = getSharedPreferences(PREFS, MODE_PRIVATE)
                .getInt(KEY_SECTION, 1) + 1;
        getSharedPreferences(PREFS, MODE_PRIVATE)
                .edit()
                .putInt(KEY_SECTION, section)
                .apply();
        sendContext(section);
    }

    private void sendContext(int section) {
        String session = getSharedPreferences(PREFS, MODE_PRIVATE)
                .getString(KEY_SESSION, null);
        long sequence = nextSequence();
        long now = System.currentTimeMillis();
        String sectionId = "ch1-s" + section;
        String sourceId = "synthetic-" + section;
        String body = "这是同签名测试 Book App 发送的合成教材上下文，第 "
                + section + " 节。它不是教材原文，只用于 Android 桥接验收。";

        Intent intent = new Intent(ACTION_CONTEXT);
        intent.setPackage(TARGET_PACKAGE);
        intent.putExtra("session_id", session);
        intent.putExtra("sequence", sequence);
        intent.putExtra("course_id", "functional-analysis-test");
        intent.putExtra("book_id", "synthetic-book");
        intent.putExtra("book_version", "test@v1");
        intent.putExtra("section_id", sectionId);
        intent.putExtra("source_id", sourceId);
        intent.putExtra("source_sha256", sha256(body));
        intent.putExtra("mode", "learn");
        intent.putExtra("captured_at_ms", now);
        intent.putExtra("expires_at_ms", now + 120_000L);
        intent.putExtra("title", "Synthetic section " + section);
        intent.putExtra("text", body);

        sendOrdered(intent, "context seq=" + sequence + " " + sectionId);
    }

    private void sendClear() {
        ensureSession();
        String session = getSharedPreferences(PREFS, MODE_PRIVATE)
                .getString(KEY_SESSION, null);
        long sequence = nextSequence();

        Intent intent = new Intent(ACTION_CLEAR);
        intent.setPackage(TARGET_PACKAGE);
        intent.putExtra("session_id", session);
        intent.putExtra("sequence", sequence);
        intent.putExtra("occurred_at_ms", System.currentTimeMillis());

        sendOrdered(intent, "clear seq=" + sequence);
    }

    private void sendOrdered(Intent intent, String label) {
        sendOrderedBroadcast(
                intent,
                null,
                new BroadcastReceiver() {
                    @Override
                    public void onReceive(Context context, Intent resultIntent) {
                        int code = getResultCode();
                        status.setText(
                                label + " · result=" + code
                                        + (code == Activity.RESULT_OK
                                        ? " · MyGPT accepted"
                                        : " · rejected/not installed")
                        );
                    }
                },
                main,
                Activity.RESULT_CANCELED,
                null,
                null
        );
    }

    private void ensureSession() {
        if (getSharedPreferences(PREFS, MODE_PRIVATE)
                .getString(KEY_SESSION, null) == null) {
            newSession();
        }
    }

    private long nextSequence() {
        long old = getSharedPreferences(PREFS, MODE_PRIVATE)
                .getLong(KEY_SEQUENCE, 0L);
        long next = old + 1L;
        getSharedPreferences(PREFS, MODE_PRIVATE)
                .edit()
                .putLong(KEY_SEQUENCE, next)
                .apply();
        return next;
    }

    private static String sha256(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder out = new StringBuilder(64);
            for (byte b : hash) out.append(String.format("%02x", b & 0xFF));
            return out.toString();
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException(impossible);
        }
    }

    private TextView text(String value, int sp) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(sp);
        return view;
    }

    private Button button(String value, Runnable action) {
        Button button = new Button(this);
        button.setText(value);
        button.setAllCaps(false);
        button.setOnClickListener(v -> action.run());
        button.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        ));
        return button;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
