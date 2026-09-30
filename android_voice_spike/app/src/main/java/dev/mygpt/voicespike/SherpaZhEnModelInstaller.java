package dev.mygpt.voicespike;

import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.HashSet;
import java.util.Set;

/**
 * Imports the official bilingual streaming Zipformer model into app-private storage.
 * Accepts ZIP, TAR.BZ2, or TAR.GZ archives.
 */
public final class SherpaZhEnModelInstaller {
    private static final long MAX_TOTAL_BYTES = 1024L * 1024L * 1024L;
    private static final long MAX_ONE_FILE_BYTES = 768L * 1024L * 1024L;

    private static final String ENCODER = "encoder-epoch-99-avg-1.int8.onnx";
    private static final String DECODER = "decoder-epoch-99-avg-1.onnx";
    private static final String JOINER = "joiner-epoch-99-avg-1.int8.onnx";
    private static final String TOKENS = "tokens.txt";

    private static final Set<String> REQUIRED = new HashSet<>();
    private static final Set<String> OPTIONAL_NOTICE = new HashSet<>();
    static {
        REQUIRED.add(ENCODER);
        REQUIRED.add(DECODER);
        REQUIRED.add(JOINER);
        REQUIRED.add(TOKENS);
        OPTIONAL_NOTICE.add("LICENSE");
        OPTIONAL_NOTICE.add("LICENSE.txt");
        OPTIONAL_NOTICE.add("README.md");
    }

    public static final class Installed {
        public final File directory;
        public final File encoder;
        public final File decoder;
        public final File joiner;
        public final File tokens;

        Installed(File directory) {
            this.directory = directory;
            this.encoder = new File(directory, ENCODER);
            this.decoder = new File(directory, DECODER);
            this.joiner = new File(directory, JOINER);
            this.tokens = new File(directory, TOKENS);
        }

        public boolean isComplete() {
            return encoder.isFile() && decoder.isFile() && joiner.isFile() && tokens.isFile();
        }
    }

    private SherpaZhEnModelInstaller() {}

    public static Installed install(InputStream source, File modelsRoot) throws IOException {
        if (source == null) throw new IllegalArgumentException("source is required");
        if (modelsRoot == null) throw new IllegalArgumentException("modelsRoot is required");
        if (!modelsRoot.exists() && !modelsRoot.mkdirs()) {
            throw new IOException("failed to create ASR model directory");
        }

        File temp = new File(modelsRoot, "sherpa-zh-en.tmp");
        File target = new File(modelsRoot, "sherpa-zh-en-streaming");
        deleteRecursively(temp);
        if (!temp.mkdirs()) throw new IOException("failed to create temporary ASR directory");

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
                    throw new IOException("duplicate ASR model entry: " + name);
                }

                File out = new File(temp, name);
                long fileBytes = copyBounded(input, out, total);
                if (required) {
                    if (fileBytes == 0L) {
                        throw new IOException("empty ASR model file: " + name);
                    }
                    seenRequired.add(name);
                }
            });

            if (!seenRequired.equals(REQUIRED)) {
                throw new IOException("ASR model archive missing required files: " + missing(seenRequired));
            }

            Installed staged = new Installed(temp);
            if (!staged.isComplete()) throw new IOException("ASR model install incomplete");

            deleteRecursively(target);
            if (!temp.renameTo(target)) {
                throw new IOException("failed to commit ASR model directory");
            }
            committed = true;
            return new Installed(target);
        } finally {
            if (!committed) deleteRecursively(temp);
        }
    }

    public static Installed existing(File modelsRoot) {
        Installed installed = new Installed(new File(modelsRoot, "sherpa-zh-en-streaming"));
        return installed.isComplete() ? installed : null;
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
                    throw new IOException("ASR model archive exceeds size limits");
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

    private static String missing(Set<String> seen) {
        Set<String> missing = new HashSet<>(REQUIRED);
        missing.removeAll(seen);
        return missing.toString();
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
