package dev.mygpt.spike;

public final class LlmBenchmarkCandidateCatalogSmoke {
    public static void main(String[] args) {
        LlmBenchmarkCandidateCatalog.Candidate speed =
                LlmBenchmarkCandidateCatalog.bySha256(
                        "57D1997790D1744FBA5B40A7317DF71EA5E2ACEE28C47E78F0CCE39C0703F8CF"
                );
        check(speed != null, "speed lookup");
        check("speed".equals(speed.id), "speed id");
        check(speed.expectedBytes == 563036064L, "speed bytes");
        check("9447f74101aeb4e93621884dfa36ee8effb8831b".equals(speed.upstreamCommit),
                "speed upstream commit");

        LlmBenchmarkCandidateCatalog.Candidate balanced =
                LlmBenchmarkCandidateCatalog.bySha256(
                        "d2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5"
                );
        check(balanced != null && balanced.expectedBytes == 1282439264L,
                "balanced bytes");
        check("daeb8e2d528a760970442092f6bf1e55c3b659eb".equals(
                balanced.upstreamCommit), "balanced upstream commit");

        LlmBenchmarkCandidateCatalog.Candidate quality =
                LlmBenchmarkCandidateCatalog.bySha256(
                        "ab27b9bfa375a178d6cba48f3ad892b94b7739659dcc7aae8058ce0ffed6b328"
                );
        check(quality != null && quality.expectedBytes == 2497280640L,
                "quality bytes");
        check("2f3b082b1356a6123f7ed71e65aea340da25d53c".equals(
                quality.upstreamCommit), "quality upstream commit");

        check("custom".equals(LlmBenchmarkCandidateCatalog.idOrCustom(
                "0000000000000000000000000000000000000000000000000000000000000000"
        )), "custom fallback");

        System.out.println("LlmBenchmarkCandidateCatalogSmoke PASS");
    }

    private static void check(boolean value, String label) {
        if (!value) throw new AssertionError(label);
    }
}
