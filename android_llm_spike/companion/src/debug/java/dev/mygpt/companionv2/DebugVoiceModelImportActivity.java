package dev.mygpt.companionv2;

import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;

import dev.mygpt.voicespike.SherpaMeloTtsModelInstaller;
import dev.mygpt.voicespike.SherpaZhEnModelInstaller;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;

/**
 * Debug-build-only acceptance activity for large sherpa archives.
 *
 * It exists as an Activity rather than a BroadcastReceiver because extracting
 * and hashing hundreds of MB may exceed broadcast execution time.
 */
public final class DebugVoiceModelImportActivity extends Activity {
    private static final String RESULT = "adb-voice-model-import-result.txt";

    private TextView status;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);

        status = new TextView(this);
        status.setText("MyGPT debug voice model import");
        status.setPadding(32, 32, 32, 32);
        setContentView(status);

        final String kind = getIntent() == null
                ? null
                : getIntent().getStringExtra("kind");

        new Thread(
                () -> importModel(kind),
                "mygpt-debug-voice-model-import"
        ).start();
    }

    private void importModel(String kind) {
        boolean accepted = false;
        String detail;

        try {
            if ("asr".equals(kind)) {
                File source = new File(
                        getFilesDir(),
                        "acceptance-inbox/asr-model.tar.bz2"
                );
                requireArchiveBytes(source, 511274346L);

                SherpaZhEnModelInstaller.Installed installed;
                try (FileInputStream input = new FileInputStream(source)) {
                    installed = SherpaZhEnModelInstaller.install(
                            input,
                            new File(getFilesDir(), "asr-models")
                    );
                }
                if (!source.delete()) source.deleteOnExit();

                detail = "kind=asr"
                        + "\narchive_bytes=511274346"
                        + "\nmodel_revision=98590b7ed6443e77b714204da2757d75e1a642f4"
                        + "\nfingerprint_manifest="
                        + installed.fingerprintManifest.getAbsolutePath()
                        + "\nhard_identity=PASS";
                accepted = true;
            } else if ("tts".equals(kind)) {
                File source = new File(
                        getFilesDir(),
                        "acceptance-inbox/tts-model.tar.bz2"
                );
                requireArchiveBytes(source, 167006755L);

                SherpaMeloTtsModelInstaller.Installed installed;
                try (FileInputStream input = new FileInputStream(source)) {
                    installed = SherpaMeloTtsModelInstaller.install(
                            input,
                            new File(getFilesDir(), "tts-models")
                    );
                }
                if (!source.delete()) source.deleteOnExit();

                detail = "kind=tts"
                        + "\narchive_bytes=167006755"
                        + "\nmodel_revision=a0d5c6a264c0ef92d70d8661d8cc502d79627cd6"
                        + "\nfingerprint_manifest="
                        + installed.fingerprintManifest.getAbsolutePath()
                        + "\nhard_identity=PASS";
                accepted = true;
            } else {
                throw new IllegalArgumentException("kind must be asr or tts");
            }
        } catch (Throwable error) {
            detail = "kind=" + safe(kind)
                    + "\nerror=" + error.getClass().getSimpleName();
        }

        writeResult(
                "schema=mygpt.debug-voice-model-import.v1\n"
                        + "accepted=" + accepted + "\n"
                        + detail + "\n"
        );

        final boolean ok = accepted;
        final String ui = accepted
                ? "Voice model import PASS: " + kind
                : "Voice model import FAILED: " + kind;

        runOnUiThread(() -> {
            status.setText(ui);
            setResult(ok ? RESULT_OK : RESULT_CANCELED);
            finish();
        });
    }

    private static void requireArchiveBytes(
            File source,
            long expectedBytes
    ) throws IOException {
        if (!source.isFile() || !source.canRead()) {
            throw new IOException("acceptance archive missing");
        }
        if (source.length() != expectedBytes) {
            throw new IOException("acceptance archive byte length mismatch");
        }
    }

    private void writeResult(String value) {
        File target = new File(getFilesDir(), RESULT);
        File temp = new File(getFilesDir(), RESULT + ".tmp");

        try (FileOutputStream output = new FileOutputStream(temp, false)) {
            output.write(value.getBytes(StandardCharsets.UTF_8));
            output.flush();
            output.getFD().sync();
        } catch (IOException ignored) {
            return;
        }

        if (target.exists() && !target.delete()) {
            temp.delete();
            return;
        }
        if (!temp.renameTo(target)) temp.delete();
    }

    private static String safe(String value) {
        return value == null ? "null" : value.replace("\n", "").replace("\r", "");
    }
}
