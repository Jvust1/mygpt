package dev.mygpt.spike;

/**
 * Renderer-neutral emotional presentation vocabulary.
 *
 * The wire values are adapted from Project AIRI's MIT-licensed Spine emotion
 * enum so chat, voice and future renderers can share one stable protocol.
 */
public enum PresentationEmotion {
    HAPPY("happy"),
    SAD("sad"),
    ANGRY("angry"),
    THINK("think"),
    SURPRISED("surprised"),
    AWKWARD("awkward"),
    QUESTION("question"),
    CURIOUS("curious"),
    NEUTRAL("neutral");

    public final String wireValue;

    PresentationEmotion(String wireValue) {
        this.wireValue = wireValue;
    }

    public static PresentationEmotion fromWire(String value) {
        if (value != null) {
            for (PresentationEmotion emotion : values()) {
                if (emotion.wireValue.equals(value)) return emotion;
            }
        }
        return NEUTRAL;
    }
}
