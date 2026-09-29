package dev.mygpt.spike;

public final class SkinCapabilityCatalogSmoke {
    public static void main(String[] args) {
        require("idle".equals(SkinCapabilityCatalog.idle(SkinCapabilityCatalog.Form.DEFAULT)),
                "default idle");
        require("aim_idle".equals(SkinCapabilityCatalog.idle(SkinCapabilityCatalog.Form.AIM)),
                "aim idle");
        require("cover_idle".equals(SkinCapabilityCatalog.idle(SkinCapabilityCatalog.Form.COVER)),
                "cover idle");
        require("to_cover".equals(SkinCapabilityCatalog.authoredTransition(
                SkinCapabilityCatalog.Form.AIM, SkinCapabilityCatalog.Form.COVER)),
                "aim to cover authored transition");
        require("to_aim".equals(SkinCapabilityCatalog.authoredTransition(
                SkinCapabilityCatalog.Form.COVER, SkinCapabilityCatalog.Form.AIM)),
                "cover to aim authored transition");
        require(SkinCapabilityCatalog.contains(
                SkinCapabilityCatalog.Form.DEFAULT, "special"), "default special action");
        require(SkinCapabilityCatalog.contains(
                SkinCapabilityCatalog.Form.AIM, "aim_skill_fire"), "aim skill action");
        require(SkinCapabilityCatalog.contains(
                SkinCapabilityCatalog.Form.COVER, "cover_stun"), "cover stun action");
        require(SkinCapabilityCatalog.authoredTransition(
                SkinCapabilityCatalog.Form.DEFAULT, SkinCapabilityCatalog.Form.AIM) == null,
                "default to aim is direct until authored transition is discovered");
        require(PresentationEmotion.fromWire("happy") == PresentationEmotion.HAPPY,
                "emotion wire mapping");
        require(PresentationEmotion.fromWire("unknown") == PresentationEmotion.NEUTRAL,
                "unknown emotion fail-safe");
        require("smile".equals(SkinCapabilityCatalog.emotionAnimation(
                SkinCapabilityCatalog.Form.DEFAULT, PresentationEmotion.HAPPY)),
                "emotion happy");
        require("sad".equals(SkinCapabilityCatalog.emotionAnimation(
                SkinCapabilityCatalog.Form.DEFAULT, PresentationEmotion.SAD)),
                "emotion sad");
        require("surprise".equals(SkinCapabilityCatalog.emotionAnimation(
                SkinCapabilityCatalog.Form.DEFAULT, PresentationEmotion.SURPRISED)),
                "emotion surprise");
        require("idle".equals(SkinCapabilityCatalog.emotionAnimation(
                SkinCapabilityCatalog.Form.DEFAULT, PresentationEmotion.ANGRY)),
                "unsupported emotion does not guess");
        require("aim_idle".equals(SkinCapabilityCatalog.emotionAnimation(
                SkinCapabilityCatalog.Form.AIM, PresentationEmotion.HAPPY)),
                "non-default form does not guess");
        System.out.println("SkinCapabilityCatalogSmoke PASS");
    }

    private static void require(boolean value, String label) {
        if (!value) throw new AssertionError(label);
    }
}
