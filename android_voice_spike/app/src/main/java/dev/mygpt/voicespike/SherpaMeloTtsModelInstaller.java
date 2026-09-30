package dev.mygpt.voicespike;

import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.HashSet;
import java.util.Set;

/**
 * Imports sherpa-onnx vits-melo-tts-zh_en into app-private storage.
 * Accepts ZIP, TAR.BZ2, or TAR.GZ archives.
 *
 * Runtime-required model files are copied with strict basename allowlisting.
 * README/LICENSE are preserved when present so model provenance is not discarded.
 */
public final class SherpaMeloTtsModelInstaller {
    private static final long MAX_TOTAL_BYTES = 1024L * 1024L * 1024L;
    private static final long MAX_ONE_FILE_BYTES = 768L * 1024L * 1024L;

    private static final Set<String> REQUIRED = new HashSet<>();
    private static final Set<String> OPTIONAL_NOTICE = new HashSet<>();
    static {
        REQUIRED.add("model.onnx");
        REQUIRED.add("tokens.txt");
        REQUIRED.add("lexicon.txt");
        REQUIRED.add("date.fst");
        REQUIRED.add("phone.fst");
        REQUIRED.add("number.fst");
        OPTIONAL_NOTICE.add("LICENSE");
        OPTIONAL_NOTICE.add("LICENSE.txt");
        OPTIONAL_NOTICE.add("README.md");
    }

    public static final class Installed {
        public final File directory;
        public final File model;
        public final File tokens;
        public final File lexicon;
        public final File dateFst;
        public final File phoneFst;
        public final File numberFst;
        public final File fingerprintManifest;

        Installed(File directory) {
            this.directory = directory;
            this.model = new File(directory, "model.onnx");
            this.tokens = new File(directory, "tokens.txt");
            this.lexicon = new File(directory, "lexicon.txt");
            this.dateFst = new File(directory, "date.fst");
            this.phoneFst = new File(directory, "phone.fst");
            this.numberFst = new File(directory, "number.fst");
            this.fingerprintManifest =
                    new File(directory, ModelFingerprintManifest.FILE_NAME);
        }

        public boolean isComplete() {
            return model.isFile()
                    && tokens.isFile()
                    && lexicon.isFile()
                    && dateFst.isFile()
                    && phoneFst.isFile()
                    && numberFst.isFile()
                    && fingerprintManifest.isFile();
        }

        public String ruleFsts() {
            return dateFst.getAbsolutePath()
                    + "," + phoneFst.getAbsolutePath()
                    + "," + numberFst.getAbsolutePath();
        }
    }

    private SherpaMeloTtsModelInstaller() {}

    public static Installed install(InputStream source, File modelsRoot) throws IOException {
        if (source == null) throw new IllegalArgumentException("source is required");
        if (modelsRoot == null) throw new IllegalArgumentException("modelsRoot is required");
        if (!modelsRoot.exists() && !modelsRoot.mkdirs()) {
            throw new IOException("failed to create TTS model directory");
        }

        File temp = new File(modelsRoot, "sherpa-melo-zh-en-tts.tmp");
        File target = new File(modelsRoot, "sherpa-melo-zh-en-tts");
        deleteRecursively(temp);
        if (!temp.mkdirs()) throw new IOException("failed to create temporary TTS directory");

        final long[] total = {0L};
        Set<String> seenRequired = new HashSet<>();
        Set<String> seenAll = new HashSet<>();
        boolean committed = false;

        try {
            ModelArchiveReader.forEachEntry(source, (entryName, directory, input) -> {
                if (directory) return;

                String name = basename(entryName);
                boolean required = REQUIRED.contains(name);
                boolean notice = OPTIONAL_NOTICE.contains(name);
                if (!required && !notice) return;
                if (!seenAll.add(name)) {
                    throw new IOException("duplicate TTS model entry: " + name);
                }

                File out = new File(temp, name);
                long fileBytes = copyBounded(input, out, total);
                if (required) {
                    if (fileBytes == 0L) {
                        throw new IOException("empty TTS model file: " + name);
                    }
                    seenRequired.add(name);
                }
            });

            if (!seenRequired.equals(REQUIRED)) {
                Set<String> missing = new HashSet<>(REQUIRED);
                missing.removeAll(seenRequired);
                throw new IOException("TTS model archive missing required files: " + missing);
            }

            Installed stagedBeforeManifest = new Installed(temp);
            if (!stagedBeforeManifest.model.isFile()
                    || !stagedBeforeManifest.tokens.isFile()
                    || !stagedBeforeManifest.lexicon.isFile()
                    || !stagedBeforeManifest.dateFst.isFile()
                    || !stagedBeforeManifest.phoneFst.isFile()
                    || !stagedBeforeManifest.numberFst.isFile()) {
                throw new IOException("TTS model install incomplete");
            }

            ModelFingerprintManifest.write(
                    temp,
                    "sherpa-vits-melo-tts-zh-en",
                    "sherpa-onnx-v1.13.8",
                    "model.onnx",
                    "tokens.txt",
                    "lexicon.txt",
                    "date.fst",
                    "phone.fst",
                    "number.fst"
            );

            Installed staged = new Installed(temp);
            if (!staged.isComplete()
                    || !ModelFingerprintManifest.verify(
                            temp,
                            "sherpa-vits-melo-tts-zh-en",
                            "sherpa-onnx-v1.13.8",
                            "model.onnx",
                            "tokens.txt",
                            "lexicon.txt",
                            "date.fst",
                            "phone.fst",
                            "number.fst"
                    )) {
                throw new IOException("TTS model manifest verification failed");
            }

            deleteRecursively(target);
            if (!temp.renameTo(target)) {
                throw new IOException("failed to commit TTS model directory");
            }
            committed = true;
            return new Installed(target);
        } finally {
            if (!committed) deleteRecursively(temp);
        }
    }

    public static Installed existing(File modelsRoot) {
        File directory = new File(modelsRoot, "sherpa-melo-zh-en-tts");
        Installed installed = new Installed(directory);

        if (!installed.model.isFile()
                || !installed.tokens.isFile()
                || !installed.lexicon.isFile()
                || !installed.dateFst.isFile()
                || !installed.phoneFst.isFile()
                || !installed.numberFst.isFile()) {
            return null;
        }

        try {
            if (!installed.fingerprintManifest.isFile()) {
                // One-time migration for models installed before fingerprint v1.
                ModelFingerprintManifest.write(
                        directory,
                        "sherpa-vits-melo-tts-zh-en",
                        "sherpa-onnx-v1.13.8",
                        "model.onnx",
                        "tokens.txt",
                        "lexicon.txt",
                        "date.fst",
                        "phone.fst",
                        "number.fst"
                );
            }
            return ModelFingerprintManifest.verify(
                    directory,
                    "sherpa-vits-melo-tts-zh-en",
                    "sherpa-onnx-v1.13.8",
                    "model.onnx",
                    "tokens.txt",
                    "lexicon.txt",
                    "date.fst",
                    "phone.fst",
                    "number.fst"
            ) ? new Installed(directory) : null;
        } catch (IOException error) {
            return null;
        }
    }

    private static long copyBounded(InputStream input, File out, long[] total)
            throws IOException {
        byte[] buffer = new byte[1024 * 1024];
        long fileBytes = 0L;
        try (BufferedOutputStream stream =
                     new BufferedOutputStream(new FileOutputStream(out))) {
            while (true) {
                int count = input.read(buffer);
                if (count < 0) break;
                fileBytes += count;
                total[0] += count;
                if (fileBytes > MAX_ONE_FILE_BYTES || total[0] > MAX_TOTAL_BYTES) {
                    throw new IOException("TTS model archive exceeds size limits");
                }
                stream.write(buffer, 0, count);
            }
        }
        return fileBytes;
    }

    private static String basename(String value) {
        String normalized = value.replace('\\', '/');
        int index = normalized.lastIndexOf('/');
        return index >= 0 ? normalized.substring(index + 1) : normalized;
    }

    private static void deleteRecursively(File file) {
        if (!file.exists()) return;
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children != null) {
                for (File child : children) deleteRecursively(child);
            }
        }
        if (!file.delete()) file.deleteOnExit();
    }
}
