package dev.mygpt.spike;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

/** Fixed upstream identities for Xiaomi 14 benchmark candidates. */
public final class LlmBenchmarkCandidateCatalog {
    public static final class Candidate {
        public final String id;
        public final String label;
        public final String sha256;
        public final long expectedBytes;
        public final String upstreamCommit;

        Candidate(
                String id,
                String label,
                String sha256,
                long expectedBytes,
                String upstreamCommit
        ) {
            this.id = id;
            this.label = label;
            this.sha256 = sha256;
            this.expectedBytes = expectedBytes;
            this.upstreamCommit = upstreamCommit;
        }
    }

    private static final Map<String, Candidate> BY_SHA;

    static {
        Map<String, Candidate> values = new LinkedHashMap<>();
        add(values, new Candidate(
                "speed",
                "Qwen3.5-0.8B-Q4_0",
                "57d1997790d1744fba5b40a7317df71ea5e2acee28c47e78f0cce39c0703f8cf",
                563036064L,
                "9447f74101aeb4e93621884dfa36ee8effb8831b"
        ));
        add(values, new Candidate(
                "balanced",
                "Qwen3-1.7B-Q4_K_M",
                "d2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5",
                1282439264L,
                "daeb8e2d528a760970442092f6bf1e55c3b659eb"
        ));
        add(values, new Candidate(
                "quality",
                "Qwen3-4B-Q4_K_M",
                "ab27b9bfa375a178d6cba48f3ad892b94b7739659dcc7aae8058ce0ffed6b328",
                2497280640L,
                "2f3b082b1356a6123f7ed71e65aea340da25d53c"
        ));
        BY_SHA = Collections.unmodifiableMap(values);
    }

    private LlmBenchmarkCandidateCatalog() {}

    public static Candidate bySha256(String sha256) {
        if (sha256 == null) return null;
        return BY_SHA.get(sha256.toLowerCase());
    }

    public static String idOrCustom(String sha256) {
        Candidate candidate = bySha256(sha256);
        return candidate == null ? "custom" : candidate.id;
    }

    public static String labelOrCustom(String sha256) {
        Candidate candidate = bySha256(sha256);
        return candidate == null ? "Custom GGUF" : candidate.label;
    }

    private static void add(Map<String, Candidate> values, Candidate candidate) {
        if (candidate.sha256.length() != 64
                || candidate.expectedBytes <= 0L
                || candidate.upstreamCommit.length() != 40
                || values.put(candidate.sha256, candidate) != null) {
            throw new IllegalStateException(
                    "duplicate/invalid benchmark candidate identity");
        }
    }
}
