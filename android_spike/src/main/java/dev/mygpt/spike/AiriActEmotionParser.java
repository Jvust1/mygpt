package dev.mygpt.spike;

import com.google.gson.Strictness;
import com.google.gson.stream.JsonReader;
import com.google.gson.stream.JsonToken;

import java.io.IOException;
import java.io.StringReader;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * AIRI presentation parsing at the on-device reply boundary.
 *
 * Emotion normalization is adapted from moeru-ai/airi queues.ts at
 * b40e3e87b149ea5fb75d4944440493829e601411, MIT, copyright 2024-PRESENT Neko Ayaka.
 * The bounded quote-aware scanner mirrors the reviewed Python MyGPT port.
 * JSON is decoded with Gson 2.14.0's strict streaming reader, not reflection.
 * See third_party/airi and third_party/gson for exact sources and licenses.
 * No marker may execute a tool, delay, action or permission change.
 */
public final class AiriActEmotionParser {
    private static final int MAX_TEXT_CHARS = 16000;
    private static final int MAX_MARKER_BYTES = 768;
    private static final Pattern ACT_START = Pattern.compile(
            "<\\|ACT(?![\\p{L}\\p{N}_])", Pattern.CASE_INSENSITIVE);
    private static final Pattern PARTIAL_TAIL = Pattern.compile(
            "<\\|(?:A|AC)?$", Pattern.CASE_INSENSITIVE);

    public static final class Result {
        public final String visibleText;
        public final PresentationEmotion emotion;
        public final float intensity;
        public final boolean markerFound;

        Result(String visibleText, PresentationEmotion emotion, float intensity, boolean markerFound) {
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
        if (text == null || text.length() > MAX_TEXT_CHARS) {
            throw new IllegalArgumentException("invalid ACT reply size");
        }
        StringBuilder visible = new StringBuilder();
        ParsedEmotion last = new ParsedEmotion(PresentationEmotion.NEUTRAL, 1.0f);
        boolean found = false;
        int cursor = 0;
        Matcher marker = ACT_START.matcher(text);
        while (marker.find(cursor)) {
            found = true;
            visible.append(text, cursor, marker.start());
            int end = envelopeEnd(text, marker.end());
            if (end < 0) {
                cursor = text.length();
                break;
            }
            String payload = trimLeading(text.substring(marker.end(), end));
            if (payload.startsWith(":")) payload = trimLeading(payload.substring(1));
            ParsedEmotion parsed = parsePayload(payload);
            if (parsed != null) last = parsed;
            cursor = end + 2;
        }
        visible.append(text, cursor, text.length());
        String clean = visible.toString();
        Matcher partial = PARTIAL_TAIL.matcher(clean);
        if (partial.find()) {
            clean = clean.substring(0, partial.start());
            found = true;
        }
        return new Result(clean, last.emotion, last.intensity, found);
    }

    private static int envelopeEnd(String text, int start) {
        boolean quoted = false;
        boolean escaped = false;
        for (int index = start; index < text.length(); index++) {
            char value = text.charAt(index);
            if (quoted) {
                if (escaped) escaped = false;
                else if (value == '\\') escaped = true;
                else if (value == '"') quoted = false;
            } else if (value == '"') {
                quoted = true;
            } else if (value == '|' && index + 1 < text.length() && text.charAt(index + 1) == '>') {
                return index;
            }
        }
        return -1;
    }

    private static ParsedEmotion parsePayload(String payload) {
        if (payload.getBytes(StandardCharsets.UTF_8).length > MAX_MARKER_BYTES
                || payload.startsWith("\uFEFF")) return null;
        try (JsonReader reader = new JsonReader(new StringReader(payload))) {
            reader.setStrictness(Strictness.STRICT);
            reader.setNestingLimit(25);
            Object parsed = readJson(reader, 0);
            if (!(parsed instanceof Map) || reader.peek() != JsonToken.END_DOCUMENT) return null;
            Object emotion = ((Map<?, ?>) parsed).get("emotion");
            String name;
            float intensity = 1.0f;
            if (emotion instanceof String) {
                name = (String) emotion;
            } else if (emotion instanceof Map && ((Map<?, ?>) emotion).get("name") instanceof String) {
                Map<?, ?> object = (Map<?, ?>) emotion;
                name = (String) object.get("name");
                Object number = object.get("intensity");
                if (number instanceof Number) {
                    // Huge JSON integers are valid; clamp them as AIRI/Python do.
                    double value = ((Number) number).doubleValue();
                    intensity = (float) Math.min(1.0, Math.max(0.0, value));
                }
            } else {
                return null;
            }
            PresentationEmotion known = knownEmotion(name);
            return known == null ? null : new ParsedEmotion(known, intensity);
        } catch (IOException | IllegalStateException | IllegalArgumentException invalid) {
            return null;
        }
    }

    private static Object readJson(JsonReader reader, int depth) throws IOException {
        if (depth > 24) throw new IOException("ACT JSON nesting limit");
        switch (reader.peek()) {
            case BEGIN_OBJECT:
                reader.beginObject();
                Map<String, Object> object = new LinkedHashMap<String, Object>();
                while (reader.hasNext()) {
                    String key = scalarString(reader.nextName());
                    if (object.containsKey(key)) throw new IOException("duplicate ACT JSON key");
                    object.put(key, readJson(reader, depth + 1));
                }
                reader.endObject();
                return object;
            case BEGIN_ARRAY:
                reader.beginArray();
                List<Object> array = new ArrayList<Object>();
                while (reader.hasNext()) array.add(readJson(reader, depth + 1));
                reader.endArray();
                return array;
            case STRING:
                return scalarString(reader.nextString());
            case NUMBER:
                String literal = reader.nextString();
                if (literal.indexOf('.') < 0 && literal.indexOf('e') < 0 && literal.indexOf('E') < 0) {
                    return new BigInteger(literal);
                }
                double number = Double.parseDouble(literal);
                if (Double.isNaN(number) || Double.isInfinite(number)) {
                    throw new IOException("nonfinite ACT JSON number");
                }
                return number;
            case BOOLEAN:
                return reader.nextBoolean();
            case NULL:
                reader.nextNull();
                return null;
            default:
                throw new IOException("invalid ACT JSON value");
        }
    }

    private static String scalarString(String value) throws IOException {
        for (int index = 0; index < value.length(); index++) {
            char c = value.charAt(index);
            if (Character.isHighSurrogate(c)) {
                if (index + 1 >= value.length() || !Character.isLowSurrogate(value.charAt(++index))) {
                    throw new IOException("invalid ACT Unicode scalar");
                }
            } else if (Character.isLowSurrogate(c)) {
                throw new IOException("invalid ACT Unicode scalar");
            }
        }
        return value;
    }

    private static boolean whitespace(int codePoint) {
        return Character.isWhitespace(codePoint) || Character.isSpaceChar(codePoint) || codePoint == 0x85;
    }

    private static String trimLeading(String value) {
        int start = 0;
        while (start < value.length() && whitespace(value.codePointAt(start))) {
            start += Character.charCount(value.codePointAt(start));
        }
        return value.substring(start);
    }

    private static PresentationEmotion knownEmotion(String value) {
        String normalized = trimLeading(value);
        int end = normalized.length();
        while (end > 0 && whitespace(normalized.codePointBefore(end))) {
            end -= Character.charCount(normalized.codePointBefore(end));
        }
        normalized = normalized.substring(0, end).toLowerCase(Locale.ROOT);
        for (PresentationEmotion emotion : PresentationEmotion.values()) {
            if (emotion.wireValue.equals(normalized)) return emotion;
        }
        return null;
    }
}
