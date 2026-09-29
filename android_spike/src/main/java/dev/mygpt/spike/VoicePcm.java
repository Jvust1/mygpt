package dev.mygpt.spike;

/**
 * Pure Java PCM helpers shared by Android voice capture and host-side smoke tests.
 *
 * The 16-bit PCM normalization rule is adapted from sherpa-onnx's Apache-2.0
 * Android Java demo. See third_party/sherpa-onnx/NOTICE.md.
 */
final class VoicePcm {
    private VoicePcm() {}

    static float[] normalizePcm16(short[] input, int count) {
        if (input == null) {
            throw new IllegalArgumentException("input is required");
        }
        if (count < 0 || count > input.length) {
            throw new IllegalArgumentException("count out of range");
        }
        float[] output = new float[count];
        for (int i = 0; i < count; i++) {
            output[i] = input[i] / 32768.0f;
        }
        return output;
    }
}
