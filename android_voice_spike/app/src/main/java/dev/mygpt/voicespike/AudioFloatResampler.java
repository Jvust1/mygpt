package dev.mygpt.voicespike;

/**
 * Dependency-free mono float resampler for acceptance/test plumbing.
 *
 * Linear interpolation is sufficient for the fixed local TTS->ASR loopback
 * gate; production microphone ASR remains native 16 kHz capture.
 */
public final class AudioFloatResampler {
    private AudioFloatResampler() {}

    public static float[] resample(
            float[] input,
            int sourceRate,
            int targetRate
    ) {
        if (input == null) throw new IllegalArgumentException("input is required");
        if (sourceRate < 1 || targetRate < 1) {
            throw new IllegalArgumentException("sample rates must be positive");
        }
        if (input.length == 0) return new float[0];
        if (sourceRate == targetRate) return input.clone();

        long scaled = Math.round(
                (double) input.length * (double) targetRate / (double) sourceRate
        );
        if (scaled < 1L || scaled > Integer.MAX_VALUE) {
            throw new IllegalArgumentException("resampled length out of range");
        }

        int outputLength = (int) scaled;
        float[] output = new float[outputLength];
        double step = (double) sourceRate / (double) targetRate;

        for (int i = 0; i < outputLength; i++) {
            double position = i * step;
            int left = (int) Math.floor(position);
            if (left >= input.length - 1) {
                output[i] = input[input.length - 1];
                continue;
            }

            int right = left + 1;
            double fraction = position - left;
            output[i] = (float) (
                    input[left] * (1.0 - fraction)
                            + input[right] * fraction
            );
        }
        return output;
    }
}
