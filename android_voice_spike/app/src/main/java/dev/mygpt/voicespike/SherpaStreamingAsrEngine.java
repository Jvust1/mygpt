package dev.mygpt.voicespike;

import com.k2fsa.sherpa.onnx.OnlineModelConfig;
import com.k2fsa.sherpa.onnx.OnlineRecognizer;
import com.k2fsa.sherpa.onnx.OnlineRecognizerConfig;
import com.k2fsa.sherpa.onnx.OnlineStream;
import com.k2fsa.sherpa.onnx.OnlineTransducerModelConfig;

/**
 * Generic streaming ASR wrapper for sherpa-onnx transducer models.
 */
public final class SherpaStreamingAsrEngine implements AutoCloseable {
    public static final int SAMPLE_RATE = 16000;

    public static final class Result {
        public final String text;
        public final boolean endpoint;

        Result(String text, boolean endpoint) {
            this.text = text == null ? "" : text;
            this.endpoint = endpoint;
        }
    }

    private final OnlineRecognizer recognizer;
    private final OnlineStream stream;
    private boolean closed;

    public SherpaStreamingAsrEngine(
            SherpaZhEnModelInstaller.Installed model,
            int numThreads
    ) {
        if (model == null || !model.isComplete()) {
            throw new IllegalArgumentException("complete sherpa model is required");
        }
        if (numThreads < 1 || numThreads > 8) {
            throw new IllegalArgumentException("numThreads must be in 1..8");
        }

        OnlineTransducerModelConfig transducer =
                OnlineTransducerModelConfig.builder()
                        .setEncoder(model.encoder.getAbsolutePath())
                        .setDecoder(model.decoder.getAbsolutePath())
                        .setJoiner(model.joiner.getAbsolutePath())
                        .build();

        OnlineModelConfig onlineModel =
                OnlineModelConfig.builder()
                        .setTransducer(transducer)
                        .setTokens(model.tokens.getAbsolutePath())
                        .setNumThreads(numThreads)
                        .setDebug(false)
                        .setProvider("cpu")
                        .setModelType("zipformer")
                        .build();

        OnlineRecognizerConfig config =
                OnlineRecognizerConfig.builder()
                        .setOnlineModelConfig(onlineModel)
                        .setEnableEndpoint(true)
                        .setDecodingMethod("greedy_search")
                        .build();

        recognizer = new OnlineRecognizer(config);
        stream = recognizer.createStream();
    }

    public synchronized Result accept(float[] samples) {
        requireOpen();
        if (samples == null || samples.length == 0) return new Result("", false);

        stream.acceptWaveform(samples, SAMPLE_RATE);
        while (recognizer.isReady(stream)) recognizer.decode(stream);

        boolean endpoint = recognizer.isEndpoint(stream);
        String text = recognizer.getResult(stream).getText();

        if (endpoint) {
            float[] tail = new float[(int) (0.8f * SAMPLE_RATE)];
            stream.acceptWaveform(tail, SAMPLE_RATE);
            while (recognizer.isReady(stream)) recognizer.decode(stream);
            text = recognizer.getResult(stream).getText();
            recognizer.reset(stream);
        }
        return new Result(text, endpoint);
    }

    public synchronized void reset() {
        requireOpen();
        recognizer.reset(stream);
    }

    private void requireOpen() {
        if (closed) throw new IllegalStateException("ASR engine is closed");
    }

    @Override
    public synchronized void close() {
        if (closed) return;
        closed = true;
        stream.release();
        recognizer.release();
    }
}
