package dev.mygpt.spike;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/**
 * App-private GGUF installer with bounded streaming copy and post-copy validation.
 */
public final class GgufModelInstaller {
    public static final class InstalledModel {
        public final File file;
        public final String sha256;
        public final long sizeBytes;
        public final GgufModelProbe.Header header;

        InstalledModel(
                File file,
                String sha256,
                long sizeBytes,
                GgufModelProbe.Header header
        ) {
            this.file = file;
            this.sha256 = sha256;
            this.sizeBytes = sizeBytes;
            this.header = header;
        }
    }

    private static final int BUFFER_SIZE = 1024 * 1024;

    private GgufModelInstaller() {}

    public static InstalledModel install(
            InputStream source,
            File modelsDir,
            long maxBytes
    ) throws IOException {
        if (source == null) throw new IllegalArgumentException("source is required");
        if (modelsDir == null) throw new IllegalArgumentException("modelsDir is required");
        if (maxBytes < 24 || maxBytes > 64L * 1024L * 1024L * 1024L) {
            throw new IllegalArgumentException("maxBytes must be in 24..64GiB");
        }
        if (!modelsDir.exists() && !modelsDir.mkdirs()) {
            throw new IOException("failed to create model directory");
        }
        if (!modelsDir.isDirectory()) {
            throw new IOException("model destination is not a directory");
        }

        File temp = File.createTempFile("mygpt-model-", ".partial", modelsDir);
        long size = 0L;
        MessageDigest digest = sha256();
        boolean committed = false;
        try {
            try (
                    BufferedInputStream input = new BufferedInputStream(source, BUFFER_SIZE);
                    BufferedOutputStream output = new BufferedOutputStream(
                            new FileOutputStream(temp), BUFFER_SIZE)
            ) {
                byte[] buffer = new byte[BUFFER_SIZE];
                while (true) {
                    int count = input.read(buffer);
                    if (count < 0) break;
                    size += count;
                    if (size > maxBytes) {
                        throw new IOException("GGUF source exceeds configured size limit");
                    }
                    digest.update(buffer, 0, count);
                    output.write(buffer, 0, count);
                }
                output.flush();
            }

            if (size < 24) throw new IOException("GGUF source is too small");
            GgufModelProbe.Header header = GgufModelProbe.probe(temp);
            String hash = hex(digest.digest());
            File target = new File(modelsDir, "model-" + hash.substring(0, 16) + ".gguf");

            if (target.exists()) {
                if (!target.isFile() || target.length() != size) {
                    throw new IOException("existing GGUF target conflicts with import");
                }
                String existingHash = sha256File(target);
                if (!hash.equals(existingHash)) {
                    throw new IOException("existing GGUF target hash conflict");
                }
                if (!temp.delete()) temp.deleteOnExit();
                committed = true;
                return new InstalledModel(target, hash, size, header);
            }

            if (!temp.renameTo(target)) {
                copyAndSync(temp, target);
                if (!temp.delete()) temp.deleteOnExit();
            }
            committed = true;
            return new InstalledModel(target, hash, size, header);
        } finally {
            if (!committed && temp.exists() && !temp.delete()) {
                temp.deleteOnExit();
            }
        }
    }

    private static void copyAndSync(File source, File target) throws IOException {
        try (
                FileInputStream input = new FileInputStream(source);
                FileOutputStream output = new FileOutputStream(target)
        ) {
            byte[] buffer = new byte[BUFFER_SIZE];
            while (true) {
                int count = input.read(buffer);
                if (count < 0) break;
                output.write(buffer, 0, count);
            }
            output.flush();
            output.getFD().sync();
        } catch (IOException error) {
            if (target.exists() && !target.delete()) target.deleteOnExit();
            throw error;
        }
    }

    private static String sha256File(File file) throws IOException {
        MessageDigest digest = sha256();
        try (InputStream input = new BufferedInputStream(new FileInputStream(file))) {
            byte[] buffer = new byte[BUFFER_SIZE];
            while (true) {
                int count = input.read(buffer);
                if (count < 0) break;
                digest.update(buffer, 0, count);
            }
        }
        return hex(digest.digest());
    }

    private static MessageDigest sha256() {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException("SHA-256 unavailable", impossible);
        }
    }

    private static String hex(byte[] bytes) {
        StringBuilder builder = new StringBuilder(bytes.length * 2);
        for (byte value : bytes) {
            builder.append(String.format("%02x", value & 0xFF));
        }
        return builder.toString();
    }
}
