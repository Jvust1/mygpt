package dev.mygpt.spike;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.Reader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;

/** Actual Gson + reviewed Python fixture parity, no Android/model/device needed. */
public final class AiriActGoldenSmoke {
    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("fixture path required");
        int count = 0;
        try (Reader input = Files.newBufferedReader(Paths.get(args[0]), StandardCharsets.UTF_8)) {
            JsonObject root = JsonParser.parseReader(input).getAsJsonObject();
            for (JsonElement item : root.getAsJsonArray("cases")) {
                JsonObject c = item.getAsJsonObject();
                String id = c.get("id").getAsString();
                String text = c.get("input").isJsonNull() ? null : c.get("input").getAsString();
                boolean rejected = false;
                AiriActEmotionParser.Result result = null;
                try {
                    result = AiriActEmotionParser.parse(text);
                } catch (IllegalArgumentException expected) {
                    rejected = true;
                }
                if (c.has("error")) {
                    require(rejected, id + ": expected rejection");
                } else {
                    require(!rejected, id + ": unexpected rejection");
                    require(result.visibleText.equals(c.get("text").getAsString()), id + ": visible text");
                    require(result.emotion.wireValue.equals(c.get("emotion").getAsString()), id + ": emotion");
                    require(Math.abs(result.intensity - c.get("intensity").getAsDouble()) < 0.000001, id + ": intensity");
                    require(result.markerFound == c.get("marker_found").getAsBoolean(), id + ": marker flag");
                }
                count++;
            }
        }
        System.out.println("AiriActGoldenSmoke PASS: " + count + " Python/Gson parity cases");
    }

    private static void require(boolean value, String label) {
        if (!value) throw new AssertionError(label);
    }
}
