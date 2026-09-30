package dev.mygpt.spike;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.util.Collections;

/** Real Book JSON projection and UTF-8 boundary checks, with synthetic context only. */
public final class BookUnicodeBudgetSmoke {
    private static final String PAIR = "\uD840\uDC00";
    public static void main(String[] args) throws Exception {
        BookContextSnapshot fixed = context("a" + repeat(PAIR, 100), "b" + repeat(PAIR, 2000));
        CompanionPromptBudget.Result result = compose("current", fixed, 5200);
        JsonObject block = check(result, fixed, "current");
        require(block.get("title").getAsString().length() == 179, "title omits one unit rather than split pair");
        require(block.get("text").getAsString().length() == 2799, "body omits one unit rather than split pair");
        require(block.get("title_truncated").getAsBoolean() && block.get("text_truncated").getAsBoolean(), "accurate fixed truncation flags");
        require(result.bookTextChars == 2799, "accurate decoded body accounting");

        // Exercise the production renderer at exactly zero/one/two units, not a duplicate algorithm.
        Method render = CompanionPromptBudget.class.getDeclaredMethod("renderBook", BookContextSnapshot.class, int.class);
        render.setAccessible(true);
        BookContextSnapshot adjacent = context("", repeat(PAIR, 3));
        for (int budget = 0; budget <= 6; budget++) {
            String rendered = (String) render.invoke(null, adjacent, budget);
            JsonObject data = parse(rendered);
            String text = data.get("text").getAsString();
            require(text.length() == budget - budget % 2, "adjacent pair boundary " + budget);
            require(wellFormed(rendered), "well-formed zero/one-unit renderer");
            require(data.get("title").getAsString().isEmpty() && !data.get("title_truncated").getAsBoolean(), "empty title preserved");
            require(data.get("text_truncated").getAsBoolean() == (text.length() < adjacent.text.length()), "small truncation flag");
        }
        BookContextSnapshot bmp = context("T", "x");
        JsonObject bmpData = parse((String) render.invoke(null, bmp, 1));
        require(bmpData.get("text").getAsString().equals("x") && !bmpData.get("text_truncated").getAsBoolean(), "one-unit BMP retained");

        int projections = 0;
        for (int shift = 0; shift < 4; shift++) {
            String title = repeat("x", shift) + repeat(PAIR, 150);
            String original = repeat("y", shift) + repeat(PAIR + "[<>]\\\"", 650);
            BookContextSnapshot book = context(title, original);
            for (int cap = 1024; cap <= 5200; cap += 13) {
                String user = "current mathematical symbol \uD835\uDD4F";
                check(compose(user, book, cap), book, user);
                projections++;
            }
        }
        String fullUser = repeat(PAIR, 2000);
        check(compose(fullUser, fixed, 5200), fixed, fullUser);
        require(fixed.title.equals("a" + repeat(PAIR, 100)) && fixed.text.equals("b" + repeat(PAIR, 2000)), "source context unchanged");
        System.out.println("BookUnicodeBudgetSmoke PASS: fixed/0..6-unit boundaries; " + projections + " dynamic projections; full user UTF-8 preserved");
    }

    private static JsonObject check(CompanionPromptBudget.Result result, BookContextSnapshot book, String user) {
        require(result.prompt.length() <= result.maxPromptChars, "hard UTF-16 cap");
        require(result.prompt.endsWith("[USER_MESSAGE]\n" + user), "full current user retained");
        require(wellFormed(result.prompt), "prompt does not contain split surrogate pairs");
        require(result.prompt.equals(new String(result.prompt.getBytes(StandardCharsets.UTF_8), StandardCharsets.UTF_8)), "UTF-8 roundtrip preserves prompt");
        JsonObject data = parse(result.prompt);
        String title = data.get("title").getAsString();
        String text = data.get("text").getAsString();
        require(book.title.startsWith(title) && book.text.startsWith(text), "projection preserves exact prefixes");
        require(title.length() <= 180 && text.length() <= 2800, "Book-specific ceilings");
        require(data.get("title_truncated").getAsBoolean() == (title.length() < book.title.length()), "title flag");
        require(data.get("text_truncated").getAsBoolean() == (text.length() < book.text.length()), "text flag");
        require(result.bookTextChars == text.length(), "decoded UTF-16 count");
        require(result.bookTextTruncated == (text.length() < book.text.length()), "result truncation flag");
        require(data.get("source_sha256").getAsString().equals(book.sourceSha256), "source reference untouched");
        require(result.prompt.indexOf("[/BOOK_SIGNED_CONTEXT_JSON]") == result.prompt.lastIndexOf("[/BOOK_SIGNED_CONTEXT_JSON]"), "one real Book boundary");
        return data;
    }
    private static JsonObject parse(String prompt) {
        int start = prompt.indexOf('\n') + 1;
        int end = prompt.indexOf("\n[/BOOK_SIGNED_CONTEXT_JSON]", start);
        return JsonParser.parseString(prompt.substring(start, end)).getAsJsonObject();
    }
    private static CompanionPromptBudget.Result compose(String user, BookContextSnapshot context, int budget) {
        return CompanionPromptBudget.compose(user, context, "{}", Collections.<CompanionPromptBudget.MemorySnippet>emptyList(), Collections.<CompanionPromptBudget.HistoryTurn>emptyList(), budget);
    }
    private static BookContextSnapshot context(String title, String body) {
        return new BookContextSnapshot("study-1", 1, "course", "book", "v1", "section", "source", repeat("a", 64), BookContextSnapshot.Mode.LEARN, 2100000000000L, 2100000120000L, title, body);
    }
    private static boolean wellFormed(String text) {
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (Character.isHighSurrogate(c)) {
                if (++i >= text.length() || !Character.isLowSurrogate(text.charAt(i))) return false;
            } else if (Character.isLowSurrogate(c)) return false;
        }
        return true;
    }
    private static String repeat(String value, int count) {
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < count; i++) out.append(value);
        return out.toString();
    }
    private static void require(boolean value, String label) { if (!value) throw new AssertionError(label); }
}
