package dev.mygpt.spike;

public final class VoicePcmSmoke {
    public static void main(String[] args) {
        short[] samples = new short[] {
                Short.MIN_VALUE, -16384, 0, 16384, Short.MAX_VALUE
        };
        float[] normalized = VoicePcm.normalizePcm16(samples, samples.length);
        require(normalized.length == 5, "length");
        require(normalized[0] == -1.0f, "min");
        require(Math.abs(normalized[1] + 0.5f) < 0.00001f, "negative half");
        require(normalized[2] == 0.0f, "zero");
        require(Math.abs(normalized[3] - 0.5f) < 0.00001f, "positive half");
        require(normalized[4] > 0.9999f && normalized[4] < 1.0f, "max");
        expectFailure(() -> VoicePcm.normalizePcm16(samples, -1));
        expectFailure(() -> VoicePcm.normalizePcm16(samples, samples.length + 1));
        System.out.println("VoicePcmSmoke PASS");
    }

    private static void require(boolean condition, String name) {
        if (!condition) {
            throw new AssertionError(name);
        }
    }

    private static void expectFailure(Runnable runnable) {
        try {
            runnable.run();
            throw new AssertionError("expected IllegalArgumentException");
        } catch (IllegalArgumentException expected) {
            // pass
        }
    }
}
