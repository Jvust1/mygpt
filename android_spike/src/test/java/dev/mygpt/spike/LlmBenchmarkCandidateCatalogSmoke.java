package dev.mygpt.spike;

public final class LlmBenchmarkCandidateCatalogSmoke {
    public static void main(String[] args) {
        check("speed".equals(LlmBenchmarkCandidateCatalog.idOrCustom(
                "57D1997790D1744FBA5B40A7317DF71EA5E2ACEE28C47E78F0CCE39C0703F8CF"
        )), "case-insensitive speed lookup");
        check("balanced".equals(LlmBenchmarkCandidateCatalog.idOrCustom(
                "d2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5"
        )), "balanced lookup");
        check("quality".equals(LlmBenchmarkCandidateCatalog.idOrCustom(
                "ab27b9bfa375a178d6cba48f3ad892b94b7739659dcc7aae8058ce0ffed6b328"
        )), "quality lookup");
        check("custom".equals(LlmBenchmarkCandidateCatalog.idOrCustom(
                "0000000000000000000000000000000000000000000000000000000000000000"
        )), "custom fallback");
        System.out.println("LlmBenchmarkCandidateCatalogSmoke PASS");
    }

    private static void check(boolean value, String label) {
        if (!value) throw new AssertionError(label);
    }
}
