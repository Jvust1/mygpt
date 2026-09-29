package dev.mygpt.spike;

/**
 * Dependency-neutral streaming ASR decode loop derived from the sherpa-onnx
 * Android Java demo at pinned commit
 * 040afe360a38e25daaa325ce8889abf93ea02609 (Apache-2.0).
 *
 * <p>This class deliberately does not depend on sherpa-onnx JNI/AAR classes or
 * model assets. A later Android adapter can bind one sherpa OnlineStream /
 * OnlineRecognizer pair to {@link Engine}. Keeping this layer pure Java makes
 * endpoint/reset semantics testable before adding a native runtime or model.
 */
final class SherpaStreamingDecoder {
    static final int SAMPLE_RATE_HZ = 16000;
    static final int ENDPOINT_TAIL_SAMPLES = (int) (0.8f * SAMPLE_RATE_HZ);
    private static final int MAX_DECODE_STEPS_PER_ACCEPT = 4096;

    interface Engine {
        void acceptWaveform(float[] samples, int sampleRateHz);
        boolean isReady();
        void decode();
        boolean isEndpoint();
        String resultText();
        void reset();
    }

    static final class Update {
        private final String partialText;
        private final String finalText;
        private final boolean endpoint;

        Update(String partialText, String finalText, boolean endpoint) {
            this.partialText = partialText;
            this.finalText = finalText;
            this.endpoint = endpoint;
        }

        String partialText() {
            return partialText;
        }

        String finalText() {
            return finalText;
        }

        boolean endpoint() {
            return endpoint;
        }
    }

    private final Engine engine;

    SherpaStreamingDecoder(Engine engine) {
        if (engine == null) {
            throw new IllegalArgumentException("engine is required");
        }
        this.engine = engine;
    }

    Update acceptFrame(float[] samples, int sampleRateHz) {
        if (samples == null || samples.length == 0) {
            throw new IllegalArgumentException("samples are required");
        }
        if (sampleRateHz != SAMPLE_RATE_HZ) {
            throw new IllegalArgumentException("only 16 kHz PCM is accepted");
        }

        engine.acceptWaveform(samples, sampleRateHz);
        decodeReady();
        String partial = normalized(engine.resultText());

        if (!engine.isEndpoint()) {
            return new Update(partial, "", false);
        }

        // The pinned sherpa-onnx Android demo pushes 0.8 s of zero tail at an
        // endpoint, drains all ready decoder work, reads the final text, then
        // resets the same online stream for the next utterance.
        engine.acceptWaveform(new float[ENDPOINT_TAIL_SAMPLES], sampleRateHz);
        decodeReady();
        String finalText = normalized(engine.resultText());
        engine.reset();
        return new Update(partial, finalText, true);
    }

    private void decodeReady() {
        int steps = 0;
        while (engine.isReady()) {
            if (++steps > MAX_DECODE_STEPS_PER_ACCEPT) {
                throw new IllegalStateException("decoder remained ready for too many steps");
            }
            engine.decode();
        }
    }

    private static String normalized(String value) {
        return value == null ? "" : value.trim();
    }
}
