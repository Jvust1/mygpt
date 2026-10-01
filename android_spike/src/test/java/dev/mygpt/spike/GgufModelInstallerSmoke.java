package dev.mygpt.spike;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.IOException;
import java.nio.file.Files;

public final class GgufModelInstallerSmoke {
    public static void main(String[] args) throws Exception {
        File root = Files.createTempDirectory("mygpt-gguf-install-").toFile();
        try {
            byte[] payload = modelBytes(3, 12, 5, 1024);
            GgufModelInstaller.InstalledModel first = GgufModelInstaller.install(
                    new ByteArrayInputStream(payload), root, 4096);
            require(first.file.isFile(), "installed file");
            require(first.sizeBytes == payload.length, "size");
            require(first.sha256.length() == 64, "sha256");
            require(first.header.version == 3, "version");
            require(first.header.tensorCount == 12, "tensor count");
            require(first.header.metadataCount == 5, "metadata count");

            GgufModelInstaller.InstalledModel second = GgufModelInstaller.install(
                    new ByteArrayInputStream(payload), root, 4096);
            require(first.file.equals(second.file), "dedupe target");

            expectIo(() -> GgufModelInstaller.install(
                    new ByteArrayInputStream(new byte[64]), root, 4096));
            expectIo(() -> GgufModelInstaller.install(
                    new ByteArrayInputStream(payload), root, 100));

            File[] leftovers = root.listFiles((dir, name) -> name.endsWith(".partial"));
            require(leftovers != null && leftovers.length == 0, "no partial leftovers");
        } finally {
            deleteRecursively(root);
        }
        System.out.println("GgufModelInstallerSmoke PASS");
    }

    private static byte[] modelBytes(int version, long tensors, long metadata, int totalSize) {
        if (totalSize < 24) throw new IllegalArgumentException();
        byte[] out = new byte[totalSize];
        out[0]='G'; out[1]='G'; out[2]='U'; out[3]='F';
        putInt(out,4,version);
        putLong(out,8,tensors);
        putLong(out,16,metadata);
        for (int i=24;i<out.length;i++) out[i]=(byte)(i * 31);
        return out;
    }

    private static void putInt(byte[] out, int offset, int value) {
        for (int i=0;i<4;i++) out[offset+i]=(byte)((value >>> (8*i)) & 0xFF);
    }

    private static void putLong(byte[] out, int offset, long value) {
        for (int i=0;i<8;i++) out[offset+i]=(byte)((value >>> (8*i)) & 0xFF);
    }

    private interface IoRunnable { void run() throws Exception; }

    private static void expectIo(IoRunnable runnable) {
        try {
            runnable.run();
            throw new AssertionError("expected IOException");
        } catch (IOException expected) {
            // pass
        } catch (Exception other) {
            throw new AssertionError(other);
        }
    }

    private static void deleteRecursively(File file) {
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children != null) for (File child : children) deleteRecursively(child);
        }
        file.delete();
    }

    private static void require(boolean value, String label) {
        if (!value) throw new AssertionError(label);
    }
}
