package dev.mygpt.voicespike;

import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.HashSet;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * Imports the official bilingual streaming Zipformer model into app-private storage.
 */
public final class SherpaZhEnModelInstaller {
    private static final long MAX_TOTAL_BYTES = 1024L * 1024L * 1024L;
    private static final long MAX_ONE_FILE_BYTES = 768L * 1024L * 1024L;

    private static final String ENCODER = "encoder-epoch-99-avg-1.int8.onnx";
    private static final String DECODER = "decoder-epoch-99-avg-1.onnx";
    private static final String JOINER = "joiner-epoch-99-avg-1.int8.onnx";
    private static final String TOKENS = "tokens.txt";

    private static final Set<String> REQUIRED = new HashSet<>();
    static {
        REQUIRED.add(ENCODER);
        REQUIRED.add(DECODER);
        REQUIRED.add(JOINER);
        REQUIRED.add(TOKENS);
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

        long total = 0L;
        Set<String> seen = new HashSet<>();
        boolean committed = false;
        try (ZipInputStream zip = new ZipInputStream(source)) {
            ZipEntry entry;
            byte[] buffer = new byte[1024 * 1024];
            while ((entry = zip.getNextEntry()) != null) {
                if (entry.isDirectory()) continue;
                String name = basename(entry.getName());
                if (!REQUIRED.contains(name)) continue;
                if (!seen.add(name)) throw new IOException("duplicate ASR model entry: " + name);

                File out = new File(temp, name);
                long fileBytes = 0L;
                try (BufferedOutputStream stream = new BufferedOutputStream(new FileOutputStream(out))) {
                    while (true) {
                        int count = zip.read(buffer);
                        if (count < 0) break;
                        fileBytes += count;
                        total += count;
                        if (fileBytes > MAX_ONE_FILE_BYTES || total > MAX_TOTAL_BYTES) {
                            throw new IOException("ASR model package exceeds size limits");
                        }
                        stream.write(buffer, 0, count);
                    }
                }
            }

            if (!seen.equals(REQUIRED)) {
                throw new IOException("ASR model ZIP missing required files: " + missing(seen));
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
