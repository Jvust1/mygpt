package dev.mygpt.companionv2;

import android.app.Activity;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;

import dev.mygpt.spike.GgufModelInstaller;
import dev.mygpt.spike.LlmBenchmarkCandidateCatalog;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;

public final class DebugModelImportReceiver extends BroadcastReceiver {
    public static final String ACTION =
            "dev.mygpt.companionv2.debug.IMPORT_ACCEPTANCE_MODEL_V1";

    private static final String PREFS = "mygpt_companion_v2";
    private static final String PREF_MODEL_PATH = "gguf_path";
    private static final String PREF_MODEL_SHA256 = "gguf_sha256";
    private static final String INBOX = "acceptance-inbox/model.gguf";
    private static final String RESULT = "adb-model-import-result.txt";
    private static final long MAX_MODEL_BYTES = 16L * 1024L * 1024L * 1024L;

    @Override
    public void onReceive(Context context, Intent intent) {
        boolean accepted = false;
        String detail;

        try {
            if (intent == null || !ACTION.equals(intent.getAction())) {
                throw new IllegalArgumentException("invalid debug import action");
            }

            File inbox = new File(context.getFilesDir(), INBOX);
            GgufModelInstaller.InstalledModel inspected =
                    GgufModelInstaller.inspectFile(inbox, MAX_MODEL_BYTES);

            LlmBenchmarkCandidateCatalog.Candidate candidate =
                    LlmBenchmarkCandidateCatalog.bySha256(inspected.sha256);
            if (candidate == null) {
                throw new IOException("GGUF is not a fixed benchmark candidate");
            }
            if (candidate.expectedBytes != inspected.sizeBytes) {
                throw new IOException("candidate byte length mismatch");
            }

            File modelsDir = new File(context.getFilesDir(), "models");
            SharedPreferences prefs =
                    context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
            String oldPath = prefs.getString(PREF_MODEL_PATH, null);
            String oldHash = prefs.getString(PREF_MODEL_SHA256, null);

            GgufModelInstaller.InstalledModel installed =
                    GgufModelInstaller.adoptFile(
                            inbox,
                            modelsDir,
                            MAX_MODEL_BYTES
                    );

            if (!prefs.edit()
                    .putString(PREF_MODEL_PATH, installed.file.getAbsolutePath())
                    .putString(PREF_MODEL_SHA256, installed.sha256)
                    .commit()) {
                throw new IOException("failed to persist model identity");
            }

            String oldCleanup = cleanupOldKnownCandidate(
                    modelsDir,
                    oldPath,
                    oldHash,
                    installed.file
            );

            detail = "candidate=" + candidate.id
                    + "\nlabel=" + candidate.label
                    + "\nsha256=" + installed.sha256
                    + "\nbytes=" + installed.sizeBytes
                    + "\nupstream_commit=" + candidate.upstreamCommit
                    + "\ngguf_version=" + installed.header.version
                    + "\ntensor_count=" + installed.header.tensorCount
                    + "\nold_candidate_cleanup=" + oldCleanup;
            accepted = true;
        } catch (Throwable error) {
            detail = "error=" + error.getClass().getSimpleName();
        }

        writeResult(
                context,
                "schema=mygpt.debug-model-import.v1\n"
                        + "accepted=" + accepted + "\n"
                        + detail + "\n"
        );

        if (isOrderedBroadcast()) {
            setResultCode(accepted ? Activity.RESULT_OK : Activity.RESULT_CANCELED);
        }
    }

    private static String cleanupOldKnownCandidate(
            File modelsDir,
            String oldPath,
            String oldHash,
            File keep
    ) {
        if (oldPath == null || oldHash == null) return "NOT_APPLICABLE";
        if (LlmBenchmarkCandidateCatalog.bySha256(oldHash) == null) {
            return "CUSTOM_PRESERVED";
        }

        try {
            File oldFile = new File(oldPath).getCanonicalFile();
            File keepFile = keep.getCanonicalFile();
            File canonicalModels = modelsDir.getCanonicalFile();

            if (oldFile.equals(keepFile)) return "SAME_MODEL";
            if (!canonicalModels.equals(oldFile.getParentFile())) {
                return "OUTSIDE_MODEL_DIR_PRESERVED";
            }
            if (!oldFile.exists()) return "OLD_FILE_ALREADY_ABSENT";
            return oldFile.delete() ? "PASS" : "FAILED";
        } catch (IOException error) {
            return "FAILED";
        }
    }

    private static void writeResult(Context context, String value) {
        File target = new File(context.getFilesDir(), RESULT);
        File temp = new File(context.getFilesDir(), RESULT + ".tmp");
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
}
