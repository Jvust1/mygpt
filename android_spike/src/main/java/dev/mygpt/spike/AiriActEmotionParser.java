package dev.mygpt.spike;

import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Parser for AIRI-style <|ACT:{...}|> presentation markers.
 *
 * The protocol shape is adapted from Project AIRI's MIT-licensed
 * packages/stage-ui/src/composables/queues.ts. MyGPT intentionally supports
 * only the narrow emotion payload needed by the Android companion.
 */
public final class AiriActEmotionParser {
    private static final int MAX_TEXT_CHARS = 16000;
    private static final int MAX_MARKER_CHARS = 768;

    private static final Pattern ACT_MARKER = Pattern.compile(
            "<\\|ACT\\s*(?::\\s*)?(\\{[\\s\\S]{0," + MAX_MARKER_CHARS + "}\\})\\|>",
            Pattern.CASE_INSENSITIVE
    );
    private static final Pattern EMOTION_STRING = Pattern.compile(
            "\\"emotion\\"\\s*:\\s*\\"([^\\"]{1,32})\\"",
            Pattern.CASE_INSENSITIVE
    );
    private static final Pattern EMOTION_OBJECT = Pattern.compile(
            "\\"emotion\\"\\s*:\\s*\\{([^{}]{0,512})\\}",
            Pattern.CASE_INSENSITIVE
    );
    private static final Pattern NAME = Pattern.compile(
            "\\"name\\"\\s*:\\s*\\"([^\\"]{1,32})\\"",
            Pattern.CASE_INSENSITIVE
    );
    private static final Pattern INTENSITY = Pattern.compile(
            "\\"intensity\\"\\s*:\\s*(-?(?:\\d+(?:\\.\\d+)?|\\.\\d+))",
            Pattern.CASE_INSENSITIVE
    );

    public static final class Result {
        public final String visibleText;
        public final PresentationEmotion emotion;
        public final float intensity;
        public final boolean markerFound;

        Result(
                String visibleText,
                PresentationEmotion emotion,
                float intensity,
                boolean markerFound
        ) {
            this.visibleText = visibleText;
            this.emotion = emotion;
            this.intensity = intensity;
            this.markerFound = markerFound;
        }
    }

    private static final class ParsedEmotion {
        final PresentationEmotion emotion;
        final float intensity;

        ParsedEmotion(PresentationEmotion emotion, float intensity) {
            this.emotion = emotion;
            this.intensity = intensity;
        }
    }

    private AiriActEmotionParser() {}

    public static Result parse(String text) {
        if (text == null) throw new IllegalArgumentException("text is required");
        if (text.length() > MAX_TEXT_CHARS) {
            throw new IllegalArgumentException("text exceeds ACT parser limit");
        }

        Matcher marker = ACT_MARKER.matcher(text);
        StringBuffer visible = new StringBuffer();
        ParsedEmotion last = null;
        boolean found = false;

        while (marker.find()) {
            found = true;
            ParsedEmotion parsed = parsePayload(marker.group(1));
            if (parsed != null) last = parsed;
            // ACT markers are machine-control syntax and are never shown to the user.
            marker.appendReplacement(visible, "");
        }
        marker.appendTail(visible);

        PresentationEmotion emotion =
                last == null ? PresentationEmotion.NEUTRAL : last.emotion;
        float intensity = last == null ? 1.0f : last.intensity;
        return new Result(visible.toString(), emotion, intensity, found);
    }

    private static ParsedEmotion parsePayload(String payload) {
        Matcher direct = EMOTION_STRING.matcher(payload);
        if (direct.find()) {
            PresentationEmotion emotion = knownEmotion(direct.group(1));
            return emotion == null ? null : new ParsedEmotion(emotion, 1.0f);
        }

        Matcher object = EMOTION_OBJECT.matcher(payload);
        if (!object.find()) return null;
        String body = object.group(1);

        Matcher name = NAME.matcher(body);
        if (!name.find()) return null;
        PresentationEmotion emotion = knownEmotion(name.group(1));
        if (emotion == null) return null;

        float intensity = 1.0f;
        Matcher number = INTENSITY.matcher(body);
        if (number.find()) {
            try {
                intensity = Float.parseFloat(number.group(1));
            } catch (NumberFormatException ignored) {
                intensity = 1.0f;
            }
        }
        if (Float.isNaN(intensity) || Float.isInfinite(intensity)) intensity = 1.0f;
        intensity = Math.max(0.0f, Math.min(1.0f, intensity));
        return new ParsedEmotion(emotion, intensity);
    }

    private static PresentationEmotion knownEmotion(String value) {
        if (value == null) return null;
        String normalized = value.trim().toLowerCase(Locale.ROOT);
        for (PresentationEmotion emotion : PresentationEmotion.values()) {
            if (emotion.wireValue.equals(normalized)) return emotion;
        }
        return null;
    }
}
