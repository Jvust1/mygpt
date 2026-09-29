package dev.mygpt.spike;

import android.content.Intent;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;

import com.badlogic.gdx.backends.android.AndroidApplication;
import com.badlogic.gdx.backends.android.AndroidApplicationConfiguration;

import java.io.File;
import java.io.InputStream;

/**
 * Installable MyGPT Android companion preview.
 * Book events remain synthetic; the selected Live character is rendered by Spine.
 */
public final class SpikeActivity extends AndroidApplication {
    private static final int OPEN_SKIN_REQUEST = 3714;
    private static final String PREFS = "mygpt_spike";
    private static final String PREF_SKIN_URI = "skin_3714430278_uri";

    private static final int BG = Color.rgb(246, 247, 243);
    private static final int SURFACE = Color.rgb(255, 255, 252);
    private static final int SURFACE_ALT = Color.rgb(239, 243, 238);
    private static final int INK = Color.rgb(38, 48, 44);
    private static final int MUTED = Color.rgb(103, 113, 108);
    private static final int PRIMARY = Color.rgb(63, 100, 84);
    private static final int PRIMARY_SOFT = Color.rgb(226, 237, 231);
    private static final int WARM_SOFT = Color.rgb(246, 236, 230);
    private static final int WARM_INK = Color.rgb(126, 73, 53);
    private static final int HAIRLINE = Color.rgb(226, 230, 225);

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
        styleSystemBars();

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setClipToPadding(false);
        scroll.setVerticalScrollBarEnabled(false);
        scroll.setOverScrollMode(View.OVER_SCROLL_NEVER);
        scroll.setBackgroundColor(BG);

        LinearLayout page = new LinearLayout(this);
        page.setOrientation(LinearLayout.VERTICAL);
        page.setPadding(dp(20), dp(22), dp(20), dp(34));
        scroll.addView(page, new ScrollView.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        setContentView(scroll);

        buildHeader(page);

        TextView sectionCharacter = sectionTitle("陪伴角色");
        page.addView(sectionCharacter, topMargin(22));

        LinearLayout characterCard = card(SURFACE, 24);
        page.addView(characterCard, topMargin(10));

        LinearLayout characterHeader = new LinearLayout(this);
        characterHeader.setOrientation(LinearLayout.VERTICAL);
        characterHeader.setPadding(dp(18), dp(16), dp(18), dp(8));
        characterCard.addView(characterHeader);

        TextView skinMeta = label("LIVE SKIN · SPINE 4.1", 11, MUTED, true);
        skinMeta.setLetterSpacing(0.08f);
        characterHeader.addView(skinMeta);

        character = label("静默陪伴", 22, INK, true);
        character.setPadding(0, dp(2), 0, 0);
        characterHeader.addView(character);

        FrameLayout renderShell = new FrameLayout(this);
        renderShell.setBackground(roundRect(SURFACE_ALT, 20));
        LinearLayout.LayoutParams renderParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(430));
        renderParams.setMargins(dp(12), dp(4), dp(12), 0);
        characterCard.addView(renderShell, renderParams);

        spineApp = new SpineSkinApplication(message ->
                runOnUiThread(() -> setStatus(message)));
        AndroidApplicationConfiguration graphics = new AndroidApplicationConfiguration();
        graphics.useAccelerometer = false;
        graphics.useCompass = false;
        graphics.useGyroscope = false;
        View spineView = initializeForView(spineApp, graphics);
        renderShell.addView(spineView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        LinearLayout statusBox = new LinearLayout(this);
        statusBox.setOrientation(LinearLayout.VERTICAL);
        statusBox.setPadding(dp(14), dp(12), dp(14), dp(12));
        statusBox.setBackground(roundRect(PRIMARY_SOFT, 14));
        LinearLayout.LayoutParams statusBoxParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        statusBoxParams.setMargins(dp(14), dp(12), dp(14), dp(14));
        characterCard.addView(statusBox, statusBoxParams);

        TextView statusLabel = label("当前状态", 11, PRIMARY, true);
        statusLabel.setLetterSpacing(0.04f);
        statusBox.addView(statusLabel);

        status = label("正在准备 3714430278…", 13, INK, false);
        status.setPadding(0, dp(3), 0, 0);
        statusBox.addView(status);

        characterRuntime = new SpineCharacterRuntime(spineApp, character);
        coordinator = new CompanionCoordinator((event, nowMs) -> !revoked, characterRuntime);

        TextView sectionStudy = sectionTitle("学习陪伴");
        page.addView(sectionStudy, topMargin(22));

        LinearLayout studyCard = card(SURFACE, 20);
        page.addView(studyCard, topMargin(10));

        LinearLayout supervisionRow = new LinearLayout(this);
        supervisionRow.setOrientation(LinearLayout.HORIZONTAL);
        supervisionRow.setGravity(Gravity.CENTER_VERTICAL);
        supervisionRow.setPadding(dp(16), dp(14), dp(12), dp(12));
        studyCard.addView(supervisionRow);

        LinearLayout supervisionText = new LinearLayout(this);
        supervisionText.setOrientation(LinearLayout.VERTICAL);
        supervisionRow.addView(supervisionText,
                new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        supervisionText.addView(label("轻量学习提醒", 15, INK, true));
        TextView supervisionHint = label("只在本次演示会话中生效", 12, MUTED, false);
        supervisionHint.setPadding(0, dp(2), 0, 0);
        supervisionText.addView(supervisionHint);

        optIn = new Switch(this);
        optIn.setShowText(false);
        optIn.setOnCheckedChangeListener((button, checked) ->
                coordinator.setSupervisionOptIn(checked));
        supervisionRow.addView(optIn);

        View divider = new View(this);
        divider.setBackgroundColor(HAIRLINE);
        LinearLayout.LayoutParams dividerParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(1));
        dividerParams.setMargins(dp(16), 0, dp(16), 0);
        studyCard.addView(divider, dividerParams);

        Button start = actionButton("开始学习会话", ButtonStyle.PRIMARY, () -> {
            cancelExpiry();
            optIn.setChecked(false);
            revoked = false;
            active = true;
            epoch++;
            sequence = 0;
            send(CompanionCoordinator.Kind.SESSION_STARTED, null);
        });
        LinearLayout.LayoutParams startParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(52));
        startParams.setMargins(dp(14), dp(14), dp(14), dp(8));
        studyCard.addView(start, startParams);

        LinearLayout quickRow = actionRow();
        quickRow.addView(weightedButton("请求帮助", ButtonStyle.SOFT,
                () -> send(CompanionCoordinator.Kind.HELP_REQUESTED, "book-lease://synthetic")));
        quickRow.addView(horizontalGap());
        quickRow.addView(weightedButton("连续出错", ButtonStyle.SOFT,
                () -> send(CompanionCoordinator.Kind.PRACTICE_REPEATED_ERROR,
                        "book-lease://synthetic")));
        studyCard.addView(quickRow, rowMargins());

        LinearLayout pauseRow = actionRow();
        pauseRow.addView(weightedButton("暂停学习", ButtonStyle.OUTLINE,
                () -> send(CompanionCoordinator.Kind.SESSION_PAUSED, null)));
        pauseRow.addView(horizontalGap());
        pauseRow.addView(weightedButton("恢复学习", ButtonStyle.OUTLINE,
                () -> send(CompanionCoordinator.Kind.SESSION_RESUMED, null)));
        studyCard.addView(pauseRow, rowMargins());

        LinearLayout endRow = actionRow();
        endRow.addView(weightedButton("撤销授权", ButtonStyle.WARM,
                () -> clearDemoSession("模拟授权已撤销；会话与提醒许可已清除")));
        endRow.addView(horizontalGap());
        endRow.addView(weightedButton("结束会话", ButtonStyle.WARM,
                () -> send(CompanionCoordinator.Kind.SESSION_ENDED, null)));
        LinearLayout.LayoutParams endParams = rowMargins();
        endParams.setMargins(dp(14), dp(6), dp(14), dp(14));
        studyCard.addView(endRow, endParams);

        TextView sectionRole = sectionTitle("角色设置");
        page.addView(sectionRole, topMargin(22));

        LinearLayout roleCard = card(SURFACE, 20);
        page.addView(roleCard, topMargin(10));

        LinearLayout roleText = new LinearLayout(this);
        roleText.setOrientation(LinearLayout.VERTICAL);
        roleText.setPadding(dp(16), dp(14), dp(16), dp(6));
        roleCard.addView(roleText);
        roleText.addView(label("默认角色 · 3714430278", 15, INK, true));
        TextView roleHint = label("优先自动加载 APK 内置皮肤；手动选择仅用于换皮或调试。", 12, MUTED, false);
        roleHint.setPadding(0, dp(3), 0, 0);
        roleText.addView(roleHint);

        Button skinButton = actionButton("选择其他皮肤包", ButtonStyle.OUTLINE,
                this::openSkinPackage);
        LinearLayout.LayoutParams skinParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(50));
        skinParams.setMargins(dp(14), dp(8), dp(14), dp(14));
        roleCard.addView(skinButton, skinParams);

        LinearLayout previewNote = card(WARM_SOFT, 16);
        LinearLayout.LayoutParams previewParams = topMargin(18);
        page.addView(previewNote, previewParams);
        previewNote.setPadding(dp(14), dp(12), dp(14), dp(12));

        TextView previewTitle = label("开发预览", 12, WARM_INK, true);
        previewNote.addView(previewTitle);
        TextView previewBody = label(
                "Book 事件目前仍是合成测试；Spine Runtime 仅用于私有设备验证。"
                        + "皮肤音频已按项目规则关闭。",
                12, WARM_INK, false);
        previewBody.setPadding(0, dp(3), 0, 0);
        previewNote.addView(previewBody);

        loadBundledOrInstalledSkin();
    }

    private void buildHeader(LinearLayout page) {
        TextView eyebrow = label("MYGPT", 12, PRIMARY, true);
        eyebrow.setLetterSpacing(0.18f);
        page.addView(eyebrow);

        TextView title = label("学习陪伴", 31, INK, true);
        title.setPadding(0, dp(2), 0, 0);
        page.addView(title);

        TextView subtitle = label("Book × MyGPT × Live", 14, MUTED, false);
        subtitle.setPadding(0, dp(2), 0, 0);
        page.addView(subtitle);

        TextView badge = label("3714430278 · 设备预览", 12, PRIMARY, true);
        badge.setGravity(Gravity.CENTER);
        badge.setBackground(roundRect(PRIMARY_SOFT, 14));
        badge.setPadding(dp(12), dp(7), dp(12), dp(7));
        LinearLayout.LayoutParams badgeParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        badgeParams.setMargins(0, dp(12), 0, 0);
        page.addView(badge, badgeParams);
    }

    private File installedSkinDirectory() {
        return new File(new File(getFilesDir(), "skins"), SpinePackageLayout.SKIN_ID);
    }

    private void loadBundledOrInstalledSkin() {
        File installed = installedSkinDirectory();
        new Thread(() -> {
            try {
                String version = SpinePackageLayout.validateInstalled(installed);
                runOnUiThread(() -> {
                    setStatus("已自动加载角色 · Spine " + version);
                    characterRuntime.load(installed);
                });
                return;
            } catch (Throwable ignored) {
            }

            try (InputStream bundled = getAssets().open("3714430278.zip")) {
                SpinePackageLayout.InstalledSkin skin =
                        SpinePackageLayout.install(bundled, installed);
                runOnUiThread(() -> {
                    setStatus("内置角色已就绪 · Spine " + skin.spineVersion
                            + " · " + skin.identityMode);
                    characterRuntime.load(skin.directory);
                });
                return;
            } catch (Throwable ignored) {
                // Development CI APKs may intentionally omit the private deployment asset.
            }

            String persisted = getSharedPreferences(PREFS, MODE_PRIVATE)
                    .getString(PREF_SKIN_URI, null);
            if (persisted != null) {
                runOnUiThread(() -> loadSkin(Uri.parse(persisted), false));
            } else {
                runOnUiThread(() -> setStatus(
                        "此开发 APK 未带内置角色；可在“角色设置”中手动选择。"));
            }
        }, "mygpt-installed-skin-check").start();
    }

    private void openSkinPackage() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        intent.putExtra(Intent.EXTRA_MIME_TYPES,
                new String[]{"application/zip", "application/x-zip", "application/octet-stream"});
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION
                | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
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
        }
        loadSkin(uri, true);
    }

    private void loadSkin(Uri uri, boolean remember) {
        setStatus("正在校验并安装角色包…");
        new Thread(() -> {
            try (InputStream input = getContentResolver().openInputStream(uri)) {
                if (input == null) throw new IllegalStateException("无法打开所选文件");
                File skinRoot = new File(getFilesDir(), "skins");
                File target = new File(skinRoot, SpinePackageLayout.SKIN_ID);
                SpinePackageLayout.InstalledSkin installed =
                        SpinePackageLayout.install(input, target);
                if (remember) {
                    getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                            .putString(PREF_SKIN_URI, uri.toString()).apply();
                }
                runOnUiThread(() -> {
                    setStatus("角色已校验 · Spine " + installed.spineVersion
                            + " · " + installed.identityMode);
                    characterRuntime.load(installed.directory);
                });
            } catch (Throwable error) {
                if (!remember) {
                    getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                            .remove(PREF_SKIN_URI).apply();
                }
                runOnUiThread(() -> setStatus("角色导入失败 · "
                        + error.getClass().getSimpleName() + " · " + safeMessage(error)));
            }
        }, "mygpt-skin-import").start();
    }

    @Override protected void onStop() {
        clearDemoSession("已离开前台 · 本次会话与提醒许可已清除");
        super.onStop();
    }

    private void clearDemoSession(String message) {
        cancelExpiry();
        revoked = true;
        active = false;
        if (coordinator != null) coordinator.revokeSession();
        if (optIn != null) optIn.setChecked(false);
        if (status != null) setStatus(message);
    }

    private void cancelExpiry() {
        if (pendingExpiry != null) expiryHandler.removeCallbacks(pendingExpiry);
        pendingExpiry = null;
    }

    private void scheduleExpiry(long deadlineMs) {
        cancelExpiry();
        pendingExpiry = () -> {
            if (coordinator.expireIfNeeded(System.currentTimeMillis())) {
                clearDemoSession("模拟事件已到期 · 会话与提醒许可已清除");
            } else if (active) {
                scheduleExpiry(deadlineMs);
            }
        };
        expiryHandler.postDelayed(pendingExpiry,
                Math.max(1L, deadlineMs - System.currentTimeMillis()));
    }

    private void send(CompanionCoordinator.Kind kind, String sourceRef) {
        if (!active) {
            setStatus("请先开始学习会话");
            return;
        }
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
        } else if ("SESSION_MISMATCH".equals(result.reason)
                && coordinator.currentCue() == CompanionCoordinator.Cue.QUIET) {
            active = false;
            optIn.setChecked(false);
            cancelExpiry();
        }
        setStatus((result.accepted ? "已接收" : "已拒绝") + " · "
                + friendlyEvent(kind) + " · #" + (sequence + (result.accepted ? 0 : 1)));
    }

    private String friendlyEvent(CompanionCoordinator.Kind kind) {
        switch (kind) {
            case SESSION_STARTED: return "会话开始";
            case PRACTICE_REPEATED_ERROR: return "连续出错";
            case HELP_REQUESTED: return "请求帮助";
            case SESSION_PAUSED: return "学习暂停";
            case SESSION_RESUMED: return "恢复学习";
            case SESSION_ENDED: return "会话结束";
            default: return "学习状态更新";
        }
    }

    private void setStatus(String value) {
        if (status != null) status.setText(value);
    }

    private TextView sectionTitle(String value) {
        TextView text = label(value, 14, INK, true);
        text.setLetterSpacing(0.02f);
        return text;
    }

    private TextView label(String value, int sp, int color, boolean bold) {
        TextView text = new TextView(this);
        text.setText(value);
        text.setTextSize(sp);
        text.setTextColor(color);
        text.setLineSpacing(0, 1.08f);
        if (bold) text.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        return text;
    }

    private LinearLayout card(int color, int radiusDp) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setBackground(roundRect(color, radiusDp));
        if (Build.VERSION.SDK_INT >= 21) card.setElevation(dp(1));
        return card;
    }

    private LinearLayout actionRow() {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        return row;
    }

    private View horizontalGap() {
        View gap = new View(this);
        gap.setLayoutParams(new LinearLayout.LayoutParams(dp(8), dp(1)));
        return gap;
    }

    private Button weightedButton(String title, ButtonStyle style, Runnable action) {
        Button button = actionButton(title, style, action);
        button.setLayoutParams(new LinearLayout.LayoutParams(0, dp(48), 1f));
        return button;
    }

    private Button actionButton(String title, ButtonStyle style, Runnable action) {
        Button button = new Button(this);
        button.setText(title);
        button.setAllCaps(false);
        button.setTextSize(14);
        button.setGravity(Gravity.CENTER);
        button.setPadding(dp(12), 0, dp(12), 0);
        button.setMinHeight(0);
        button.setMinimumHeight(0);
        button.setMinWidth(0);
        button.setMinimumWidth(0);
        button.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        int background;
        int foreground;
        switch (style) {
            case PRIMARY:
                background = PRIMARY;
                foreground = Color.WHITE;
                break;
            case WARM:
                background = WARM_SOFT;
                foreground = WARM_INK;
                break;
            case OUTLINE:
                background = SURFACE_ALT;
                foreground = INK;
                break;
            default:
                background = PRIMARY_SOFT;
                foreground = PRIMARY;
                break;
        }
        button.setTextColor(foreground);
        button.setBackground(rippleBackground(background, 14));
        button.setOnClickListener(v -> action.run());
        return button;
    }

    private GradientDrawable roundRect(int color, int radiusDp) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(color);
        drawable.setCornerRadius(dp(radiusDp));
        return drawable;
    }

    private RippleDrawable rippleBackground(int color, int radiusDp) {
        GradientDrawable base = roundRect(color, radiusDp);
        return new RippleDrawable(
                ColorStateList.valueOf(Color.argb(35, 0, 0, 0)), base, null);
    }

    private LinearLayout.LayoutParams topMargin(int topDp) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.setMargins(0, dp(topDp), 0, 0);
        return params;
    }

    private LinearLayout.LayoutParams rowMargins() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(48));
        params.setMargins(dp(14), dp(6), dp(14), 0);
        return params;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void styleSystemBars() {
        Window window = getWindow();
        window.setStatusBarColor(BG);
        window.setNavigationBarColor(BG);
        int flags = 0;
        if (Build.VERSION.SDK_INT >= 23) flags |= View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
        if (Build.VERSION.SDK_INT >= 26) flags |= View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
        if (flags != 0) window.getDecorView().setSystemUiVisibility(flags);
    }

    private static String safeMessage(Throwable error) {
        String message = error.getMessage();
        return message == null ? "无详细信息" : message;
    }

    private enum ButtonStyle { PRIMARY, SOFT, OUTLINE, WARM }
}
