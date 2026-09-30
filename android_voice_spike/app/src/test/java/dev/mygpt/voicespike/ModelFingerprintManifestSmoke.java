package dev.mygpt.voicespike;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

public final class ModelFingerprintManifestSmoke {
    public static void main(String[] args) throws Exception {
        File root = Files.createTempDirectory("mygpt-model-fingerprint-").toFile();
        try {
            write(new File(root, "a.bin"), "abc");
            write(new File(root, "b.txt"), "12345");

            File manifest = ModelFingerprintManifest.write(
                    root,
                    "test-model",
                    "runtime-v1",
                    "b.txt",
                    "a.bin"
            );

            String first = new String(
                    Files.readAllBytes(manifest.toPath()),
                    StandardCharsets.UTF_8
            );

            require(first.startsWith("schema=mygpt.model-fingerprint.v1\n"),
                    "schema");
            require(first.contains("kind=test-model\n"), "kind");
            require(first.contains("runtime=runtime-v1\n"), "runtime");
            require(first.contains(
                    "file=a.bin\tbytes=3\tsha256=ba7816bf8f01cfea414140de5dae2223"
                            + "b00361a396177a9cb410ff61f20015ad"),
                    "a fingerprint");
            require(first.contains(
                    "file=b.txt\tbytes=5\tsha256=5994471abb01112afcc18159f6cc74b4"
                            + "f511b99806da59b3caf5a9c173cacfc5"),
                    "b fingerprint");
            require(first.indexOf("file=a.bin") < first.indexOf("file=b.txt"),
                    "sorted deterministic order");

            // Rewriting identical inputs must produce byte-identical evidence.
            ModelFingerprintManifest.write(
                    root,
                    "test-model",
                    "runtime-v1",
                    "a.bin",
                    "b.txt"
            );
            String second = new String(
                    Files.readAllBytes(manifest.toPath()),
                    StandardCharsets.UTF_8
            );
            require(first.equals(second), "deterministic rewrite");

            expectFailure(() -> ModelFingerprintManifest.write(
                    root,
                    "test-model",
                    "runtime-v1",
                    "missing.bin"
            ));

            System.out.println("ModelFingerprintManifestSmoke PASS");
        } finally {
            deleteRecursively(root);
        }
    }

    private static void write(File file, String value) throws Exception {
        try (FileOutputStream out = new FileOutputStream(file)) {
            out.write(value.getBytes(StandardCharsets.UTF_8));
        }
    }

    private interface ThrowingRunnable {
        void run() throws Exception;
    }

    private static void expectFailure(ThrowingRunnable action) {
        try {
            action.run();
            throw new AssertionError("expected failure");
        } catch (java.io.IOException expected) {
            // pass
        } catch (Exception other) {
            throw new AssertionError(other);
        }
    }

    private static void deleteRecursively(File file) {
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children != null) {
                for (File child : children) deleteRecursively(child);
            }
        }
        file.delete();
    }

    private static void require(boolean value, String label) {
        if (!value) throw new AssertionError(label);
    }
}
