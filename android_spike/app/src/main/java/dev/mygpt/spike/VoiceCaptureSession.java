package dev.mygpt.spike;

import android.Manifest;
import android.content.Context;
import android.content.pm.PackageManager;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;

import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Explicit, non-persistent microphone capture layer for future local ASR.
 *
 * This is a bounded MyGPT adaptation of the AudioRecord loop used by the
 * sherpa-onnx Android Java demo. It does not request permissions, does not
 * write audio to disk, and does not select an ASR engine. The caller must
 * obtain RECORD_AUDIO permission through an explicit user action first.
 */
final class VoiceCaptureSession implements AutoCloseable {
    interface Listener {
        void onFrame(float[] samples, int sampleRateHz);
        void onError(String code);
    }

    static final int SAMPLE_RATE_HZ = 16000;
    private static final int FRAME_MILLIS = 100;
    private static final int FRAME_SAMPLES = SAMPLE_RATE_HZ * FRAME_MILLIS / 1000;

    private final Context appContext;
    private final Listener listener;
    private final AtomicBoolean running = new AtomicBoolean(false);

    private AudioRecord audioRecord;
    private Thread worker;

    VoiceCaptureSession(Context context, Listener listener) {
        if (context == null || listener == null) {
            throw new IllegalArgumentException("context and listener are required");
        }
        this.appContext = context.getApplicationContext();
        this.listener = listener;
    }

    synchronized boolean isRunning() {
        return running.get();
    }

    synchronized void start() {
        if (running.get()) {
            return;
        }
        if (appContext.checkSelfPermission(Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            throw new SecurityException("RECORD_AUDIO permission not granted");
        }

        int channel = AudioFormat.CHANNEL_IN_MONO;
        int format = AudioFormat.ENCODING_PCM_16BIT;
        int minBytes = AudioRecord.getMinBufferSize(SAMPLE_RATE_HZ, channel, format);
        if (minBytes <= 0) {
            throw new IllegalStateException("invalid AudioRecord minimum buffer size");
        }
        int bufferBytes = Math.max(minBytes * 2, FRAME_SAMPLES * 2);

        AudioRecord record = new AudioRecord(
                MediaRecorder.AudioSource.MIC,
                SAMPLE_RATE_HZ,
                channel,
                format,
                bufferBytes
        );
        if (record.getState() != AudioRecord.STATE_INITIALIZED) {
            record.release();
            throw new IllegalStateException("AudioRecord initialization failed");
        }

        audioRecord = record;
        running.set(true);
        try {
            record.startRecording();
        } catch (RuntimeException error) {
            running.set(false);
            audioRecord = null;
            record.release();
            throw error;
        }

        worker = new Thread(this::captureLoop, "mygpt-voice-capture");
        worker.start();
    }

    private void captureLoop() {
        short[] buffer = new short[FRAME_SAMPLES];
        try {
            while (running.get()) {
                AudioRecord record = audioRecord;
                if (record == null) {
                    break;
                }
                int count = record.read(buffer, 0, buffer.length);
                if (count > 0) {
                    listener.onFrame(VoicePcm.normalizePcm16(buffer, count), SAMPLE_RATE_HZ);
                } else if (count < 0) {
                    listener.onError("audio_read_error_" + count);
                    break;
                }
            }
        } catch (RuntimeException error) {
            listener.onError("audio_capture_failure");
        } finally {
            running.set(false);
        }
    }

    synchronized void stop() {
        if (!running.getAndSet(false) && audioRecord == null) {
            return;
        }
        AudioRecord record = audioRecord;
        audioRecord = null;
        if (record != null) {
            try {
                record.stop();
            } catch (RuntimeException ignored) {
                // A concurrent platform stop/revoke should still release the recorder.
            }
            record.release();
        }
        Thread thread = worker;
        worker = null;
        if (thread != null && thread != Thread.currentThread()) {
            try {
                thread.join(1000);
            } catch (InterruptedException error) {
                Thread.currentThread().interrupt();
            }
        }
    }

    @Override
    public void close() {
        stop();
    }
}
