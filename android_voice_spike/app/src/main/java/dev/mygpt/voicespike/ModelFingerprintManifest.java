package dev.mygpt.voicespike;

import java.io.BufferedInputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/** Deterministic SHA-256 manifest for app-private imported model files. */
final class ModelFingerprintManifest {
    static final String FILE_NAME = "mygpt-model-manifest.txt";

    private ModelFingerprintManifest() {}

    static File write(
            File directory,
            String kind,
            String runtime,
            String... requiredNames
    ) throws IOException {
        if (directory == null || !directory.isDirectory()) {
            throw new IOException("model directory missing");
        }
        if (kind == null || kind.trim().isEmpty()) {
            throw new IllegalArgumentException("kind is required");
        }
        if (runtime == null || runtime.trim().isEmpty()) {
            throw new IllegalArgumentException("runtime is required");
        }

        List<String> names = new ArrayList<>();
        Collections.addAll(names, requiredNames);
        Collections.sort(names);

        StringBuilder content = new StringBuilder();
        content.append("schema=mygpt.model-fingerprint.v1\n");
        content.append("kind=").append(kind).append('\n');
        content.append("runtime=").append(runtime).append('\n');

        for (String name : names) {
            File file = new File(directory, name);
            if (!file.isFile() || !file.canRead()) {
                throw new IOException("required model file missing: " + name);
            }
            content.append("file=")
                    .append(name)
                    .append("\tbytes=")
                    .append(file.length())
                    .append("\tsha256=")
                    .append(sha256(file))
                    .append('\n');
        }

        File target = new File(directory, FILE_NAME);
        File temp = new File(directory, FILE_NAME + ".tmp");
        byte[] bytes = content.toString().getBytes(StandardCharsets.UTF_8);

        try (FileOutputStream output = new FileOutputStream(temp, false)) {
            output.write(bytes);
            output.flush();
            output.getFD().sync();
        }

        if (target.exists() && !target.delete()) {
            if (!temp.delete()) temp.deleteOnExit();
            throw new IOException("cannot replace model fingerprint manifest");
        }
        if (!temp.renameTo(target)) {
            if (!temp.delete()) temp.deleteOnExit();
            throw new IOException("cannot commit model fingerprint manifest");
        }
        return target;
    }

    private static String sha256(File file) throws IOException {
        final MessageDigest digest;
        try {
            digest = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException impossible) {
            throw new IOException("SHA-256 unavailable", impossible);
        }

        byte[] buffer = new byte[1024 * 1024];
        try (BufferedInputStream input =
                     new BufferedInputStream(new FileInputStream(file), buffer.length)) {
            while (true) {
                int count = input.read(buffer);
                if (count < 0) break;
                digest.update(buffer, 0, count);
            }
        }
        return hex(digest.digest());
    }

    private static String hex(byte[] bytes) {
        final char[] digits = "0123456789abcdef".toCharArray();
        char[] output = new char[bytes.length * 2];
        for (int i = 0; i < bytes.length; i++) {
            int value = bytes[i] & 0xFF;
            output[i * 2] = digits[value >>> 4];
            output[i * 2 + 1] = digits[value & 0x0F];
        }
        return new String(output);
    }
}
