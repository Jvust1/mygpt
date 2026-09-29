package dev.mygpt.spike;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;

/** Normalized visual capability catalog for Live skin 3714430278. No audio capabilities. */
public final class SkinCapabilityCatalog {
    public enum Form { DEFAULT, AIM, COVER }

    private static final List<String> DEFAULT_ACTIONS = Collections.unmodifiableList(Arrays.asList(
            "idle", "action", "etc", "no", "pain", "sad", "smile", "special", "surprise",
            "talk_start", "talk_end"
    ));
    private static final List<String> AIM_ACTIONS = Collections.unmodifiableList(Arrays.asList(
            "aim_idle", "aim_fire", "aim_hit", "aim_skill_fire", "to_aim", "to_cover"
    ));
    private static final List<String> COVER_ACTIONS = Collections.unmodifiableList(Arrays.asList(
            "cover_idle", "cover_reload", "cover_hit", "cover_stun", "to_aim", "to_cover"
    ));

    private SkinCapabilityCatalog() {}

    public static List<String> actions(Form form) {
        switch (form) {
            case AIM: return AIM_ACTIONS;
            case COVER: return COVER_ACTIONS;
            default: return DEFAULT_ACTIONS;
        }
    }

    public static String idle(Form form) {
        switch (form) {
            case AIM: return "aim_idle";
            case COVER: return "cover_idle";
            default: return "idle";
        }
    }

    public static String skeleton(Form form) {
        switch (form) {
            case AIM: return "misc_01.bin";
            case COVER: return "misc_08.bin";
            default: return "skeleton.bin";
        }
    }

    public static String atlas(Form form) {
        switch (form) {
            case AIM: return "misc_02.atlas";
            case COVER: return "misc_03.atlas";
            default: return "c610_00.atlas";
        }
    }

    public static String authoredTransition(Form from, Form to) {
        if (from == Form.AIM && to == Form.COVER) return "to_cover";
        if (from == Form.COVER && to == Form.AIM) return "to_aim";
        return null;
    }

    public static boolean contains(Form form, String animation) {
        return animation != null && actions(form).contains(animation);
    }

    public static String primaryAction(Form form) {
        switch (form) {
            case AIM: return "aim_fire";
            case COVER: return "cover_reload";
            default: return "action";
        }
    }

    public static String reaction(Form form) {
        switch (form) {
            case AIM: return "aim_hit";
            case COVER: return "cover_hit";
            default: return "smile";
        }
    }
}
