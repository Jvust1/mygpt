package dev.mygpt.spike;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.Reader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

/** Real Java score path against actual sklearn fixtures, no Android/model dependency. */
public final class LexicalMemoryScorerSmoke {
    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("oracle fixture path required");
        int cases = 0;
        double maxError = 0.0;
        try (Reader reader = Files.newBufferedReader(Paths.get(args[0]), StandardCharsets.UTF_8)) {
            JsonObject root = JsonParser.parseReader(reader).getAsJsonObject();
            require(root.get("version").getAsString().equals("1.9.1"), "sklearn version");
            require(root.get("source_commit").getAsString().equals("bbf8863a869f118a1a42422d8cc67ec6c07f2fe0"), "source identity");
            for (JsonElement item : root.getAsJsonArray("cases")) {
                JsonObject c = item.getAsJsonObject();
                String id = c.get("id").getAsString();
                String query = c.get("query").getAsString();
                List<String> documents = new ArrayList<String>();
                for (JsonElement text : c.getAsJsonArray("documents")) documents.add(text.getAsString());
                require(LexicalMemoryScorer.normalize(query).equals(c.get("normalized_query").getAsString()), id + " query normalization");
                JsonArray normalized = c.getAsJsonArray("normalized_documents");
                for (int i = 0; i < documents.size(); i++)
                    require(LexicalMemoryScorer.normalize(documents.get(i)).equals(normalized.get(i).getAsString()), id + " document normalization");
                double[] scores = LexicalMemoryScorer.score(query, documents);
                JsonArray expected = c.getAsJsonArray("scores");
                require(scores.length == expected.size(), id + " result length");
                for (int i = 0; i < scores.length; i++) {
                    double error = Math.abs(scores[i] - expected.get(i).getAsDouble());
                    require(error <= 1e-12 && Double.isFinite(scores[i]), id + " score " + i + " error " + error);
                    maxError = Math.max(maxError, error);
                }
                cases++;
            }
        }
        require(cases == 109, "complete sklearn fixture count");
        rejects(new Runnable() { public void run() { LexicalMemoryScorer.score(null, Collections.<String>emptyList()); }});
        rejects(new Runnable() { public void run() { LexicalMemoryScorer.score(repeat("x", 4001), Collections.<String>emptyList()); }});
        rejects(new Runnable() { public void run() { LexicalMemoryScorer.score("q", null); }});
        rejects(new Runnable() { public void run() { LexicalMemoryScorer.score("q", Arrays.asList((String) null)); }});
        rejects(new Runnable() { public void run() { LexicalMemoryScorer.score("q", Arrays.asList(repeat("x", 1001))); }});
        rejects(new Runnable() { public void run() { LexicalMemoryScorer.score("q", Collections.nCopies(101, "q")); }});
        String full = repeat("数学", 500);
        double[] bound = LexicalMemoryScorer.score(repeat("数学", 2000), Collections.nCopies(100, full));
        require(bound.length == 100, "candidate ceiling accepted");
        for (double value : bound) require(value > 0.99 && value <= 1.0, "maximum lexical self similarity");
        require(LexicalMemoryScorer.score("??", Arrays.asList("private memory"))[0] == 0.0, "no punctuation recall");
        System.out.println("LexicalMemoryScorerSmoke PASS: " + cases + " actual sklearn cases; max error=" + maxError);
    }

    private static String repeat(String s, int count) {
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < count; i++) out.append(s);
        return out.toString();
    }
    private static void rejects(Runnable action) {
        try { action.run(); } catch (IllegalArgumentException expected) { return; }
        throw new AssertionError("expected bounded-input rejection");
    }
    private static void require(boolean value, String label) {
        if (!value) throw new AssertionError(label);
    }
}
