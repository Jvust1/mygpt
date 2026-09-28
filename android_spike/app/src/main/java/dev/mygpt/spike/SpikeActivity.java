package dev.mygpt.spike;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;

/** Installable device harness. Every Book event here is explicitly synthetic. */
public final class SpikeActivity extends Activity {
    private CompanionCoordinator coordinator;
    private TextView character;
    private TextView status;
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

        TextView title = label("MyGPT · Android 集成测试", 25, Color.rgb(43, 54, 43));
        column.addView(title);
        TextView notice = label("仅合成事件演示。未接入 Book Android、Live 角色、模型或语音。", 15,
                Color.rgb(120, 63, 41));
        column.addView(notice);
        character = label("静默陪伴", 27, Color.rgb(52, 91, 70));
        character.setGravity(Gravity.CENTER);
        character.setPadding(16, 40, 16, 40);
        character.setBackgroundColor(Color.rgb(229, 237, 225));
        column.addView(character, new LinearLayout.LayoutParams(-1, 170));
        status = label("等待模拟会话", 15, Color.DKGRAY);
        column.addView(status);

        coordinator = new CompanionCoordinator((event, nowMs) -> !revoked,
                cue -> character.setText(cueText(cue)));
        Switch optIn = new Switch(this);
        optIn.setText("允许轻量学习提醒（仅本次演示）");
        optIn.setOnCheckedChangeListener((button, checked) -> coordinator.setSupervisionOptIn(checked));
        column.addView(optIn);

        addButton(column, "开始模拟 Book 会话", () -> {
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
        addButton(column, "撤销模拟授权", () -> {
            revoked = true;
            active = false;
            coordinator.revokeSession();
            status.setText("模拟授权已撤销；会话已清除并返回静默状态");
        });
        addButton(column, "结束会话", () -> {
            send(CompanionCoordinator.Kind.SESSION_ENDED, null);
            active = false;
        });
    }

    private void send(CompanionCoordinator.Kind kind, String sourceRef) {
        if (!active) { status.setText("请先开始模拟会话"); return; }
        long now = System.currentTimeMillis();
        CompanionCoordinator.BookEvent event = new CompanionCoordinator.BookEvent(
                kind, "synthetic-session", sequence + 1, epoch, now + 30000, sourceRef);
        CompanionCoordinator.Result result = coordinator.accept(event, now);
        if (result.accepted) sequence++;
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

    private String cueText(CompanionCoordinator.Cue cue) {
        switch (cue) {
            case PAUSED: return "学习暂停中";
            case NEEDS_INPUT: return "我在这里 · 等待提问";
            case GENTLE_CHECK_IN: return "要一起看看哪里卡住了吗？";
            default: return "静默陪伴";
        }
    }
}
