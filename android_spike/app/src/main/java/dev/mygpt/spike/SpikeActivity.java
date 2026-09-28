package dev.mygpt.spike;

import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;

import com.badlogic.gdx.backends.android.AndroidApplication;
import com.badlogic.gdx.backends.android.AndroidApplicationConfiguration;

import java.io.File;
import java.io.InputStream;

/** Installable device harness. Book events remain synthetic; Live skin 3714430278 can now be imported and rendered. */
public final class SpikeActivity extends AndroidApplication {
    private static final int OPEN_SKIN_REQUEST = 3714;
    private static final String PREFS = "mygpt_spike";
    private static final String PREF_SKIN_URI = "skin_3714430278_uri";

    private CompanionCoordinator coordinator;
    private TextView character;
    private TextView status;
    private Switch optIn;
    private SpineSkinApplication spineApp;
    private SpineCharacterRuntime characterRuntime;
    private final Handler expiryHandler = new Handler(Looper.getMainLooper());
    private Runnable pendingExpiry;
    private long epoch;
    private long sequence;
    private boolean active;
    private boolean revoked;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);

        LinearLayout column = new LinearLayout(this);
        column.setOrientation(LinearLayout.VERTICAL);
        column.setPadding(24, 32, 24, 32);
        column.setBackgroundColor(Color.rgb(247, 245, 239));
        ScrollView scroll = new ScrollView(this);
        scroll.addView(column);
        setContentView(scroll);

        TextView title = label("MyGPT · 3714430278 Android 渲染测试", 24, Color.rgb(43, 54, 43));
        column.addView(title);
        TextView notice = label("Book 事件仍为合成测试；人物包使用已解密 3714430278.zip。"
                + " Spine Runtime 当前仅用于私有调试评估。", 14, Color.rgb(120, 63, 41));
        column.addView(notice);

        character = label("3714430278 · 静默陪伴", 18, Color.rgb(52, 91, 70));
        character.setGravity(Gravity.CENTER);
        character.setPadding(16, 16, 16, 16);
        column.addView(character, new LinearLayout.LayoutParams(-1, 80));

        status = label("请选择 3714430278.zip；选择一次后会记住该文件授权。", 14, Color.DKGRAY);
        column.addView(status);

        spineApp = new SpineSkinApplication(message -> runOnUiThread(() -> status.setText(message)));
        AndroidApplicationConfiguration graphics = new AndroidApplicationConfiguration();
        graphics.useAccelerometer = false;
        graphics.useCompass = false;
        graphics.useGyroscope = false;
        View spineView = initializeForView(spineApp, graphics);
        column.addView(spineView, new LinearLayout.LayoutParams(-1, 760));

        characterRuntime = new SpineCharacterRuntime(spineApp, character);
        coordinator = new CompanionCoordinator((event, nowMs) -> !revoked, characterRuntime);

        addButton(column, "选择 / 更换 3714430278.zip", this::openSkinPackage);

        optIn = new Switch(this);
        optIn.setText("允许轻量学习提醒（仅本次演示）");
        optIn.setOnCheckedChangeListener((button, checked) -> coordinator.setSupervisionOptIn(checked));
        column.addView(optIn);

        addButton(column, "开始模拟 Book 会话", () -> {
            cancelExpiry();
            optIn.setChecked(false);
            revoked = false;
            active = true;
            epoch++;
            sequence = 0;
            send(CompanionCoordinator.Kind.SESSION_STARTED, null);
        });
        addButton(column, "模拟练习连续出错", () -> send(CompanionCoordinator.Kind.PRACTICE_REPEATED_ERROR,
                "book-lease://synthetic"));
        addButton(column, "主动请求帮助", () -> send(CompanionCoordinator.Kind.HELP_REQUESTED,
                "book-lease://synthetic"));
        addButton(column, "暂停学习", () -> send(CompanionCoordinator.Kind.SESSION_PAUSED, null));
        addButton(column, "恢复学习", () -> send(CompanionCoordinator.Kind.SESSION_RESUMED, null));
        addButton(column, "撤销模拟授权", () ->
                clearDemoSession("模拟授权已撤销；会话与提醒许可已清除"));
        addButton(column, "结束会话", () -> send(CompanionCoordinator.Kind.SESSION_ENDED, null));

        String persisted = getSharedPreferences(PREFS, MODE_PRIVATE).getString(PREF_SKIN_URI, null);
        if (persisted != null) loadSkin(Uri.parse(persisted), false);
    }

    private void openSkinPackage() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        intent.putExtra(Intent.EXTRA_MIME_TYPES,
                new String[]{"application/zip", "application/x-zip", "application/octet-stream"});
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
        startActivityForResult(intent, OPEN_SKIN_REQUEST);
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != OPEN_SKIN_REQUEST || resultCode != RESULT_OK || data == null
                || data.getData() == null) return;
        Uri uri = data.getData();
        try {
            int flags = data.getFlags() & (Intent.FLAG_GRANT_READ_URI_PERMISSION
                    | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            getContentResolver().takePersistableUriPermission(uri, flags);
        } catch (SecurityException ignored) {
            // Some providers do not offer persistable grants; current-session loading can still proceed.
        }
        loadSkin(uri, true);
    }

    private void loadSkin(Uri uri, boolean remember) {
        status.setText("正在校验并安装 3714430278.zip…");
        new Thread(() -> {
            try (InputStream input = getContentResolver().openInputStream(uri)) {
                if (input == null) throw new IllegalStateException("无法打开所选文件");
                File target = new File(new File(getFilesDir(), "skins"), SpinePackageLayout.SKIN_ID);
                SpinePackageLayout.InstalledSkin installed = SpinePackageLayout.install(input, target);
                if (remember) {
                    getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                            .putString(PREF_SKIN_URI, uri.toString()).apply();
                }
                runOnUiThread(() -> {
                    status.setText("校验通过 · Spine " + installed.spineVersion + " · SHA " + installed.archiveSha256.substring(0, 12) + "… · 正在进入渲染器");
                    characterRuntime.load(installed.directory);
                });
            } catch (Throwable error) {
                if (!remember) getSharedPreferences(PREFS, MODE_PRIVATE).edit().remove(PREF_SKIN_URI).apply();
                runOnUiThread(() -> status.setText("3714430278 导入失败："
                        + error.getClass().getSimpleName() + " · " + safeMessage(error)));
            }
        }, "mygpt-skin-import").start();
    }

    @Override protected void onStop() {
        clearDemoSession("演示已离开前台；会话与提醒许可已清除");
        super.onStop();
    }

    private void clearDemoSession(String message) {
        cancelExpiry();
        revoked = true;
        active = false;
        if (coordinator != null) coordinator.revokeSession();
        if (optIn != null) optIn.setChecked(false);
        if (status != null) status.setText(message);
    }

    private void cancelExpiry() {
        if (pendingExpiry != null) expiryHandler.removeCallbacks(pendingExpiry);
        pendingExpiry = null;
    }

    private void scheduleExpiry(long deadlineMs) {
        cancelExpiry();
        pendingExpiry = () -> {
            if (coordinator.expireIfNeeded(System.currentTimeMillis())) {
                clearDemoSession("模拟事件已到期；会话与提醒许可已清除");
            } else if (active) {
                scheduleExpiry(deadlineMs);
            }
        };
        expiryHandler.postDelayed(pendingExpiry,
                Math.max(1L, deadlineMs - System.currentTimeMillis()));
    }

    private void send(CompanionCoordinator.Kind kind, String sourceRef) {
        if (!active) { status.setText("请先开始模拟会话"); return; }
        long now = System.currentTimeMillis();
        CompanionCoordinator.BookEvent event = new CompanionCoordinator.BookEvent(
                kind, "synthetic-session", sequence + 1, epoch, now + 30000, sourceRef);
        CompanionCoordinator.Result result = coordinator.accept(event, now);
        if (result.accepted) {
            sequence++;
            if (kind == CompanionCoordinator.Kind.SESSION_ENDED) {
                active = false;
                cancelExpiry();
                optIn.setChecked(false);
            } else {
                scheduleExpiry(event.expiresAtMs);
            }
        } else if ("SESSION_MISMATCH".equals(result.reason) && coordinator.currentCue()
                == CompanionCoordinator.Cue.QUIET) {
            active = false;
            optIn.setChecked(false);
            cancelExpiry();
        }
        status.setText((result.accepted ? "已接收：" : "已拒绝：") + result.reason
                + " · " + kind.name() + " · 序号 " + (sequence + (result.accepted ? 0 : 1)));
    }

    private TextView label(String value, int sp, int color) {
        TextView text = new TextView(this);
        text.setText(value);
        text.setTextSize(sp);
        text.setTextColor(color);
        text.setPadding(0, 12, 0, 12);
        return text;
    }

    private void addButton(LinearLayout parent, String title, Runnable action) {
        Button button = new Button(this);
        button.setText(title);
        button.setAllCaps(false);
        button.setOnClickListener((View ignored) -> action.run());
        parent.addView(button, new LinearLayout.LayoutParams(-1, -2));
    }

    private static String safeMessage(Throwable error) {
        String message = error.getMessage();
        return message == null ? "无详细信息" : message;
    }
}
