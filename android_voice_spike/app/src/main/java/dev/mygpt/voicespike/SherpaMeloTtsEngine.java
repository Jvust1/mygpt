package dev.mygpt.voicespike;

import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioTrack;

import com.k2fsa.sherpa.onnx.OfflineTts;
import com.k2fsa.sherpa.onnx.OfflineTtsConfig;
import com.k2fsa.sherpa.onnx.OfflineTtsModelConfig;
import com.k2fsa.sherpa.onnx.OfflineTtsVitsModelConfig;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Streaming local TTS for the sherpa vits-melo-tts-zh_en model.
 *
 * Audio is sent directly to AudioTrack and is never written to a file.
 */
public final class SherpaMeloTtsEngine implements AutoCloseable {
    private final OfflineTts tts;
    private final AudioTrack track;
    private final ExecutorService executor;
    private final AtomicLong generation = new AtomicLong();
    private volatile boolean closed;

    public SherpaMeloTtsEngine(
            SherpaMeloTtsModelInstaller.Installed model,
            int numThreads
    ) {
        if (model == null || !model.isComplete()) {
            throw new IllegalArgumentException("complete Melo TTS model is required");
        }
        if (numThreads < 1 || numThreads > 8) {
            throw new IllegalArgumentException("numThreads must be in 1..8");
        }

        OfflineTtsVitsModelConfig vits =
                OfflineTtsVitsModelConfig.builder()
                        .setModel(model.model.getAbsolutePath())
                        .setTokens(model.tokens.getAbsolutePath())
                        .setLexicon(model.lexicon.getAbsolutePath())
                        .build();

        OfflineTtsModelConfig modelConfig =
                OfflineTtsModelConfig.builder()
                        .setVits(vits)
                        .setNumThreads(numThreads)
                        .setDebug(false)
                        .setProvider("cpu")
                        .build();

        OfflineTtsConfig config =
                OfflineTtsConfig.builder()
                        .setModel(modelConfig)
                        .setRuleFsts(model.ruleFsts())
                        .setMaxNumSentences(1)
                        .build();

        tts = new OfflineTts(config);

        int sampleRate = tts.getSampleRate();
        int minBytes = AudioTrack.getMinBufferSize(
                sampleRate,
                AudioFormat.CHANNEL_OUT_MONO,
                AudioFormat.ENCODING_PCM_FLOAT
        );
        if (minBytes <= 0) {
            tts.release();
            throw new IllegalStateException("invalid TTS AudioTrack buffer");
        }

        AudioAttributes attributes =
                new AudioAttributes.Builder()
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .setUsage(AudioAttributes.USAGE_ASSISTANT)
                        .build();

        AudioFormat format =
                new AudioFormat.Builder()
                        .setEncoding(AudioFormat.ENCODING_PCM_FLOAT)
                        .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                        .setSampleRate(sampleRate)
                        .build();

        track = new AudioTrack(
                attributes,
                format,
                minBytes,
                AudioTrack.MODE_STREAM,
                AudioManager.AUDIO_SESSION_ID_GENERATE
        );
        if (track.getState() != AudioTrack.STATE_INITIALIZED) {
            track.release();
            tts.release();
            throw new IllegalStateException("TTS AudioTrack initialization failed");
        }

        executor = Executors.newSingleThreadExecutor(runnable -> {
            Thread thread = new Thread(runnable, "mygpt-local-tts");
            thread.setDaemon(true);
            return thread;
        });
    }

    public synchronized Future<?> speak(String text) {
        requireOpen();
        if (text == null || text.trim().isEmpty()) {
            throw new IllegalArgumentException("TTS text must not be blank");
        }
        if (text.length() > 1600) {
            throw new IllegalArgumentException("TTS text too long");
        }

        final String value = text.trim();
        final long id = generation.incrementAndGet();

        return executor.submit(() -> {
            if (closed || generation.get() != id) return;
            try {
                track.pause();
                track.flush();
                track.play();

                tts.generateWithCallback(value, 0, 1.0f, samples -> {
                    if (closed || generation.get() != id) return 0;
                    if (samples == null || samples.length == 0) return 1;

                    int written = track.write(
                            samples,
                            0,
                            samples.length,
                            AudioTrack.WRITE_BLOCKING
                    );
                    return written >= 0 && generation.get() == id ? 1 : 0;
                });
            } finally {
                if (!closed && generation.get() == id) {
                    try {
                        track.pause();
                    } catch (Throwable ignored) {
                    }
                }
            }
        });
    }

    public synchronized void stop() {
        generation.incrementAndGet();
        if (!closed) {
            try {
                track.pause();
                track.flush();
            } catch (Throwable ignored) {
            }
        }
    }

    private void requireOpen() {
        if (closed) throw new IllegalStateException("TTS engine is closed");
    }

    @Override
    public synchronized void close() {
        if (closed) return;
        closed = true;
        generation.incrementAndGet();

        try {
            track.pause();
            track.flush();
        } catch (Throwable ignored) {
        }

        executor.shutdown();
        try {
            executor.awaitTermination(3, TimeUnit.SECONDS);
        } catch (InterruptedException error) {
            Thread.currentThread().interrupt();
        }
        executor.shutdownNow();

        track.release();
        tts.release();
    }
}
