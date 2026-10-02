package dev.mygpt.spike;

import android.os.Handler;
import android.os.Looper;
import android.widget.TextView;

import java.io.File;
import java.util.List;

/** Bridges mygpt cues and explicit visual controls to the multi-form Spine renderer. */
public final class SpineCharacterRuntime implements CompanionCoordinator.CharacterRuntime {
    private final SpineSkinApplication renderer;
    private final TextView fallback;
    private final Handler main = new Handler(Looper.getMainLooper());
    private int cycleIndex;

    public SpineCharacterRuntime(SpineSkinApplication renderer, TextView fallback) {
        this.renderer = renderer;
        this.fallback = fallback;
    }

    public void load(File directory) {
        cycleIndex = 0;
        renderer.requestLoad(directory);
    }

    public void switchForm(SkinCapabilityCatalog.Form form) {
        cycleIndex = 0;
        renderer.requestForm(form);
        main.post(() -> fallback.setText(formLabel(form) + " · 切换中"));
    }

    public void playIdle() {
        SkinCapabilityCatalog.Form form = renderer.currentForm();
        renderer.requestAnimation(SkinCapabilityCatalog.idle(form));
        main.post(() -> fallback.setText(formLabel(form) + " · 待机"));
    }

    public void playPrimaryAction() {
        SkinCapabilityCatalog.Form form = renderer.currentForm();
        String action = SkinCapabilityCatalog.primaryAction(form);
        renderer.requestAnimation(action);
        main.post(() -> fallback.setText(formLabel(form) + " · " + action));
    }

    public void playReaction() {
        SkinCapabilityCatalog.Form form = renderer.currentForm();
        String action = SkinCapabilityCatalog.reaction(form);
        renderer.requestAnimation(action);
        main.post(() -> fallback.setText(formLabel(form) + " · " + action));
    }

    public void cycleAction() {
        SkinCapabilityCatalog.Form form = renderer.currentForm();
        List<String> actions = SkinCapabilityCatalog.actions(form);
        if (actions.isEmpty()) return;
        String action = actions.get(cycleIndex % actions.size());
        cycleIndex++;
        renderer.requestAnimation(action);
        main.post(() -> fallback.setText(formLabel(form) + " · " + action));
    }

    public void showEmotion(PresentationEmotion emotion) {
        SkinCapabilityCatalog.Form form = renderer.currentForm();
        String animation = SkinCapabilityCatalog.emotionAnimation(form, emotion);
        renderer.requestAnimation(animation);
        main.post(() -> fallback.setText(
                formLabel(form) + " · " + emotion.wireValue + " · " + animation));
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

    private static String formLabel(SkinCapabilityCatalog.Form form) {
        switch (form) {
            case AIM: return "AIM";
            case COVER: return "COVER";
            default: return "DEFAULT";
        }
    }
}
