package dev.mygpt.spike;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Bounded char_wb TF-IDF/cosine port from scikit-learn, used by Android memory search.
 * Source bbf8863a869f118a1a42422d8cc67ec6c07f2fe0: text.py _char_wb_ngrams,
 * TfidfTransformer.fit/transform and pairwise.py cosine_similarity.
 * Copyright (c) 2007-2026 The scikit-learn developers. BSD-3-Clause.
 * See third_party/scikit-learn/LICENSE and NOTICE.md; bundled Android notices.
 *
 * Fixed configuration: ngrams (2,3), smooth IDF, sublinear TF, L2 normalization.
 * Sparse maps replace NumPy/SciPy. No model, network or persisted index is needed.
 */
public final class LexicalMemoryScorer {
    public static final int MAX_QUERY_CHARS = 4000;
    public static final int MAX_DOCUMENT_CHARS = 1000;
    public static final int MAX_CANDIDATES = 100;

    private LexicalMemoryScorer() { }

    /** Fit only candidate documents; transform the full query without refitting IDF. */
    public static double[] score(String query, List<String> documents) {
        if (query == null || query.length() > MAX_QUERY_CHARS)
            throw new IllegalArgumentException("invalid lexical query size");
        if (documents == null || documents.size() > MAX_CANDIDATES)
            throw new IllegalArgumentException("invalid lexical candidate count");
        List<Map<String, Integer>> counts = new ArrayList<Map<String, Integer>>();
        Map<String, Integer> documentFrequency = new LinkedHashMap<String, Integer>();
        for (String document : documents) {
            if (document == null || document.length() > MAX_DOCUMENT_CHARS)
                throw new IllegalArgumentException("invalid lexical document size");
            Map<String, Integer> count = ngrams(normalize(document));
            counts.add(count);
            for (String term : count.keySet()) increment(documentFrequency, term);
        }
        double[] result = new double[documents.size()];
        if (documentFrequency.isEmpty()) return result;
        Map<String, Double> idf = new LinkedHashMap<String, Double>();
        double samples = documents.size() + 1.0;
        for (Map.Entry<String, Integer> item : documentFrequency.entrySet())
            idf.put(item.getKey(), Math.log(samples / (item.getValue() + 1.0)) + 1.0);
        Map<String, Double> queryVector = normalizedVector(ngrams(normalize(query)), idf);
        for (int i = 0; i < counts.size(); i++) {
            Map<String, Double> vector = normalizedVector(counts.get(i), idf);
            double dot = 0.0;
            for (Map.Entry<String, Double> item : vector.entrySet()) {
                Double queryWeight = queryVector.get(item.getKey());
                if (queryWeight != null) dot += queryWeight * item.getValue();
            }
            result[i] = Math.min(1.0, Math.max(0.0, dot));
        }
        return result;
    }

    /** MyGPT preprocessing: only Unicode letters/numbers are lexical evidence. */
    static String normalize(String text) {
        String lower = text.toLowerCase(Locale.ROOT);
        StringBuilder result = new StringBuilder();
        boolean separator = false;
        for (int i = 0; i < lower.length();) {
            int point = lower.codePointAt(i);
            i += Character.charCount(point);
            int type = Character.getType(point);
            boolean word = Character.isLetterOrDigit(point)
                    || type == Character.LETTER_NUMBER || type == Character.OTHER_NUMBER;
            if (word) {
                if (separator && result.length() > 0) result.append(' ');
                result.appendCodePoint(point);
                separator = false;
            } else {
                separator = true;
            }
        }
        return result.toString();
    }

    private static Map<String, Integer> ngrams(String normalized) {
        Map<String, Integer> result = new LinkedHashMap<String, Integer>();
        if (normalized.isEmpty()) return result;
        for (String token : normalized.split(" ")) {
            int[] word = (" " + token + " ").codePoints().toArray();
            for (int n = 2; n <= 3; n++) {
                int offset = 0;
                increment(result, new String(word, offset, Math.min(n, word.length)));
                while (offset + n < word.length) {
                    offset++;
                    increment(result, new String(word, offset, n));
                }
                // Upstream emits one short-word gram instead of duplicating it.
                if (offset == 0) break;
            }
        }
        return result;
    }

    private static void increment(Map<String, Integer> values, String key) {
        Integer previous = values.get(key);
        values.put(key, previous == null ? 1 : previous + 1);
    }

    private static Map<String, Double> normalizedVector(
            Map<String, Integer> counts, Map<String, Double> idf) {
        Map<String, Double> vector = new LinkedHashMap<String, Double>();
        double squared = 0.0;
        for (Map.Entry<String, Integer> item : counts.entrySet()) {
            Double inverseFrequency = idf.get(item.getKey());
            if (inverseFrequency == null) continue;
            double weight = (1.0 + Math.log(item.getValue())) * inverseFrequency;
            vector.put(item.getKey(), weight);
            squared += weight * weight;
        }
        if (squared > 0.0) {
            double norm = Math.sqrt(squared);
            for (Map.Entry<String, Double> item : vector.entrySet())
                item.setValue(item.getValue() / norm);
        }
        return vector;
    }
}
