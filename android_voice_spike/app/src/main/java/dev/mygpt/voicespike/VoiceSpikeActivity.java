package dev.mygpt.voicespike;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import dev.mygpt.spike.VoicePcm;

import java.io.File;
import java.io.InputStream;

public final class VoiceSpikeActivity extends Activity {
    private static final int REQUEST_MODEL_ZIP = 9401;
    private static final int REQUEST_MIC = 9402;

    private final Handler main = new Handler(Looper.getMainLooper());

    private TextView status;
    private TextView transcript;
    private Button startButton;
    private Button stopButton;

    private SherpaZhEnModelInstaller.Installed model;
    private SherpaStreamingAsrEngine asr;
    private AudioRecord recorder;
    private Thread worker;
    private volatile boolean recording;
    private final StringBuilder committed = new StringBuilder();

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);

        ScrollView scroll = new ScrollView(this);
        LinearLayout page = new LinearLayout(this);
        page.setOrientation(LinearLayout.VERTICAL);
        page.setPadding(dp(18), dp(22), dp(18), dp(30));
        scroll.addView(page);
        setContentView(scroll);

        TextView title = text("MyGPT Voice Spike", 26);
        page.addView(title);
        page.addView(text("sherpa-onnx v1.13.8 · streaming zh/en · 全本地", 13));

        status = text("尚未导入中英 streaming Zipformer 模型包", 13);
        status.setPadding(0, dp(14), 0, dp(8));
        page.addView(status);

        page.addView(button("选择模型 ZIP", this::chooseModel));

        startButton = button("开始实时识别", this::startVoice);
        startButton.setEnabled(false);
        page.addView(startButton);

        stopButton = button("停止", this::stopVoice);
        stopButton.setEnabled(false);
        page.addView(stopButton);

        transcript = text("转写文本会显示在这里。", 16);
        transcript.setPadding(0, dp(18), 0, 0);
        page.addView(transcript);

        File root = new File(getFilesDir(), "asr-models");
        model = SherpaZhEnModelInstaller.existing(root);
        if (model != null) {
            status.setText("模型已恢复 · 可开始识别");
            startButton.setEnabled(true);
        }
    }

    private void chooseModel() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        intent.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{
                "application/zip", "application/x-zip", "application/octet-stream"
        });
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        startActivityForResult(intent, REQUEST_MODEL_ZIP);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQUEST_MODEL_ZIP || resultCode != RESULT_OK
                || data == null || data.getData() == null) return;
        importModel(data.getData());
    }

    private void importModel(Uri uri) {
        status.setText("正在导入 sherpa 模型…");
        startButton.setEnabled(false);
        new Thread(() -> {
            try (InputStream input = getContentResolver().openInputStream(uri)) {
                if (input == null) throw new IllegalStateException("cannot open model ZIP");
                SherpaZhEnModelInstaller.Installed installed =
                        SherpaZhEnModelInstaller.install(
                                input,
                                new File(getFilesDir(), "asr-models")
                        );
                model = installed;
                main.post(() -> {
                    status.setText("模型已导入 · encoder/decoder/joiner/tokens 完整");
                    startButton.setEnabled(true);
                });
            } catch (Throwable error) {
                main.post(() -> status.setText(
                        "模型导入失败 · " + error.getClass().getSimpleName()));
            }
        }, "mygpt-asr-model-import").start();
    }

    private void startVoice() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, REQUEST_MIC);
            return;
        }
        startRecording();
    }

    @Override
    public void onRequestPermissionsResult(
            int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != REQUEST_MIC) return;
        if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            startRecording();
        } else {
            status.setText("麦克风权限未授权；不会录音");
        }
    }

    private synchronized void startRecording() {
        if (recording) return;
        SherpaZhEnModelInstaller.Installed selected = model;
        if (selected == null) {
            status.setText("请先导入模型");
            return;
        }

        try {
            asr = new SherpaStreamingAsrEngine(selected, 2);
            int min = AudioRecord.getMinBufferSize(
                    SherpaStreamingAsrEngine.SAMPLE_RATE,
                    AudioFormat.CHANNEL_IN_MONO,
                    AudioFormat.ENCODING_PCM_16BIT
            );
            if (min <= 0) throw new IllegalStateException("invalid AudioRecord buffer");
            recorder = new AudioRecord(
                    MediaRecorder.AudioSource.MIC,
                    SherpaStreamingAsrEngine.SAMPLE_RATE,
                    AudioFormat.CHANNEL_IN_MONO,
                    AudioFormat.ENCODING_PCM_16BIT,
                    Math.max(min * 2, 3200)
            );
            if (recorder.getState() != AudioRecord.STATE_INITIALIZED) {
                throw new IllegalStateException("AudioRecord init failed");
            }
            committed.setLength(0);
            recording = true;
            recorder.startRecording();
            worker = new Thread(this::captureLoop, "mygpt-sherpa-mic");
            worker.start();
            status.setText("正在实时识别 · 16kHz mono · 音频不落盘");
            startButton.setEnabled(false);
            stopButton.setEnabled(true);
        } catch (Throwable error) {
            stopRecording();
            status.setText("启动失败 · " + error.getClass().getSimpleName());
        }
    }

    private void captureLoop() {
        short[] buffer = new short[1600];
        while (recording) {
            AudioRecord localRecorder = recorder;
            SherpaStreamingAsrEngine localAsr = asr;
            if (localRecorder == null || localAsr == null) break;

            int count = localRecorder.read(buffer, 0, buffer.length);
            if (count <= 0) continue;

            try {
                SherpaStreamingAsrEngine.Result result =
                        localAsr.accept(VoicePcm.normalizePcm16(buffer, count));
                if (result.text.isEmpty()) continue;

                if (result.endpoint) {
                    if (committed.length() > 0) committed.append('\n');
                    committed.append(result.text);
                }
                String view = committed.toString();
                if (!result.endpoint) {
                    view = view.isEmpty() ? result.text : view + "\n" + result.text;
                }
                final String display = view;
                main.post(() -> transcript.setText(display));
            } catch (Throwable error) {
                main.post(() -> status.setText(
                        "识别失败 · " + error.getClass().getSimpleName()));
                break;
            }
        }
    }

    private synchronized void stopVoice() {
        stopRecording();
        status.setText(model == null ? "尚未导入模型" : "已停止 · 可再次开始");
    }

    private synchronized void stopRecording() {
        recording = false;
        AudioRecord local = recorder;
        recorder = null;
        if (local != null) {
            try { local.stop(); } catch (Throwable ignored) {}
            local.release();
        }
        Thread thread = worker;
        worker = null;
        if (thread != null && thread != Thread.currentThread()) {
            try { thread.join(1000); } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
        SherpaStreamingAsrEngine localAsr = asr;
        asr = null;
        if (localAsr != null) localAsr.close();
        if (startButton != null) startButton.setEnabled(model != null);
        if (stopButton != null) stopButton.setEnabled(false);
    }

    @Override
    protected void onStop() {
        stopRecording();
        super.onStop();
    }

    private TextView text(String value, int sp) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(sp);
        return view;
    }

    private Button button(String value, Runnable action) {
        Button button = new Button(this);
        button.setText(value);
        button.setAllCaps(false);
        button.setOnClickListener(v -> action.run());
        button.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        ));
        return button;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
