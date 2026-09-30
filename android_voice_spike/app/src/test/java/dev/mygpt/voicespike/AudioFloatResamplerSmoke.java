package dev.mygpt.voicespike;

public final class AudioFloatResamplerSmoke {
    public static void main(String[] args) {
        float[] input = new float[] {0.0f, 1.0f, 0.0f, -1.0f};

        float[] same = AudioFloatResampler.resample(input, 16000, 16000);
        check(same.length == input.length, "same-rate length");
        check(same != input, "same-rate clone");
        for (int i = 0; i < input.length; i++) {
            check(Math.abs(same[i] - input[i]) < 0.000001f, "same-rate sample " + i);
        }

        float[] doubled = AudioFloatResampler.resample(input, 16000, 32000);
        check(doubled.length == 8, "upsample length");
        check(Math.abs(doubled[0] - 0.0f) < 0.000001f, "upsample start");
        check(Math.abs(doubled[1] - 0.5f) < 0.000001f, "upsample interpolation");
        check(Math.abs(doubled[2] - 1.0f) < 0.000001f, "upsample original point");

        float[] halved = AudioFloatResampler.resample(input, 16000, 8000);
        check(halved.length == 2, "downsample length");
        check(Math.abs(halved[0] - 0.0f) < 0.000001f, "downsample first");
        check(Math.abs(halved[1] - 0.0f) < 0.000001f, "downsample second");

        expectFailure(() -> AudioFloatResampler.resample(input, 0, 16000));
        expectFailure(() -> AudioFloatResampler.resample(input, 16000, 0));

        System.out.println("AudioFloatResamplerSmoke PASS");
    }

    private static void expectFailure(Runnable action) {
        try {
            action.run();
            throw new AssertionError("expected IllegalArgumentException");
        } catch (IllegalArgumentException expected) {
            // pass
        }
    }

    private static void check(boolean value, String label) {
        if (!value) throw new AssertionError(label);
    }
}
