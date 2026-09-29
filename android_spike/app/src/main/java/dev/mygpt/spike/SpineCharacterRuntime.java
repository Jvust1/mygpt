package dev.mygpt.spike;

import android.os.Handler;
import android.os.Looper;
import android.widget.TextView;

import java.io.File;

/** Bridges coordinator cues to the Spine renderer while retaining a readable text fallback. */
public final class SpineCharacterRuntime implements CompanionCoordinator.CharacterRuntime {
    private final SpineSkinApplication renderer;
    private final TextView fallback;
    private final Handler main = new Handler(Looper.getMainLooper());

    public SpineCharacterRuntime(SpineSkinApplication renderer, TextView fallback) {
        this.renderer = renderer;
        this.fallback = fallback;
    }

    public void load(File directory) {
        renderer.requestLoad(directory);
    }

    @Override public void show(CompanionCoordinator.Cue cue) {
        renderer.requestCue(cue);
        main.post(() -> fallback.setText(cueText(cue)));
    }

    private static String cueText(CompanionCoordinator.Cue cue) {
        switch (cue) {
            case PAUSED: return "学习暂停";
            case NEEDS_INPUT: return "等待提问";
            case GENTLE_CHECK_IN: return "轻提醒";
            default: return "静默陪伴";
        }
    }
}
