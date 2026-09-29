package dev.mygpt.spike;

public final class SherpaStreamingDecoderSmoke {
    public static void main(String[] args) {
        FakeEngine engine = new FakeEngine();
        SherpaStreamingDecoder decoder = new SherpaStreamingDecoder(engine);

        engine.readySteps = 2;
        engine.text = " 正在识别 ";
        SherpaStreamingDecoder.Update partial =
                decoder.acceptFrame(new float[] {0.1f, -0.1f}, 16000);
        require(!partial.endpoint(), "partial endpoint");
        require("正在识别".equals(partial.partialText()), "partial text");
        require("".equals(partial.finalText()), "partial final text");
        require(engine.decodeCalls == 2, "partial decode count");
        require(engine.lastAcceptedLength == 2, "partial frame length");
        require(engine.resetCalls == 0, "partial reset");

        engine.endpoint = true;
        engine.readySteps = 1;
        engine.text = " 初步结果 ";
        engine.finalTextAfterTail = " 最终结果 ";
        SherpaStreamingDecoder.Update complete =
                decoder.acceptFrame(new float[] {0.2f}, 16000);
        require(complete.endpoint(), "final endpoint");
        require("初步结果".equals(complete.partialText()), "pre-tail text");
        require("最终结果".equals(complete.finalText()), "final text");
        require(engine.tailAccepted, "endpoint tail");
        require(engine.lastTailLength == SherpaStreamingDecoder.ENDPOINT_TAIL_SAMPLES,
                "tail length");
        require(engine.resetCalls == 1, "endpoint reset");

        expectFailure(() -> decoder.acceptFrame(new float[] {0.1f}, 8000));
        expectFailure(() -> decoder.acceptFrame(new float[0], 16000));
        expectFailure(() -> new SherpaStreamingDecoder(null));

        System.out.println("SherpaStreamingDecoderSmoke PASS");
    }

    private static final class FakeEngine implements SherpaStreamingDecoder.Engine {
        int readySteps;
        int decodeCalls;
        int resetCalls;
        int lastAcceptedLength;
        int lastTailLength;
        boolean endpoint;
        boolean tailAccepted;
        String text = "";
        String finalTextAfterTail = "";

        @Override
        public void acceptWaveform(float[] samples, int sampleRateHz) {
            require(sampleRateHz == 16000, "engine sample rate");
            lastAcceptedLength = samples.length;
            if (samples.length == SherpaStreamingDecoder.ENDPOINT_TAIL_SAMPLES) {
                tailAccepted = true;
                lastTailLength = samples.length;
                text = finalTextAfterTail;
                readySteps = 1;
            }
        }

        @Override
        public boolean isReady() {
            return readySteps > 0;
        }

        @Override
        public void decode() {
            decodeCalls += 1;
            readySteps -= 1;
        }

        @Override
        public boolean isEndpoint() {
            return endpoint;
        }

        @Override
        public String resultText() {
            return text;
        }

        @Override
        public void reset() {
            resetCalls += 1;
            endpoint = false;
        }
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
