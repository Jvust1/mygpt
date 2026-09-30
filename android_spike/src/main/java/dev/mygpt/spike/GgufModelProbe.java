package dev.mygpt.spike;

import java.io.EOFException;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;

/**
 * Lightweight GGUF header validator adapted from llama.cpp Android metadata reader.
 *
 * Only the fixed header is read. Tensor data is never mapped or loaded.
 */
public final class GgufModelProbe {
    public static final class Header {
        public final int version;
        public final long tensorCount;
        public final long metadataCount;

        Header(int version, long tensorCount, long metadataCount) {
            this.version = version;
            this.tensorCount = tensorCount;
            this.metadataCount = metadataCount;
        }
    }

    private GgufModelProbe() {}

    public static Header probe(File file) throws IOException {
        if (file == null) throw new IllegalArgumentException("file is required");
        if (!file.exists() || !file.isFile() || !file.canRead()) {
            throw new IOException("GGUF file is not readable");
        }
        try (InputStream input = new FileInputStream(file)) {
            return probe(input);
        }
    }

    public static Header probe(InputStream input) throws IOException {
        if (input == null) throw new IllegalArgumentException("input is required");
        byte[] magic = readExact(input, 4);
        if (magic[0] != 'G' || magic[1] != 'G' || magic[2] != 'U' || magic[3] != 'F') {
            throw new IOException("invalid GGUF magic");
        }
        int version = readLittleInt(input);
        if (version < 1 || version > 3) {
            throw new IOException("unsupported GGUF version: " + version);
        }
        long tensorCount = readLittleLong(input);
        long metadataCount = readLittleLong(input);
        if (tensorCount < 0 || metadataCount < 0) {
            throw new IOException("GGUF count exceeds signed 64-bit range");
        }
        if (tensorCount > 10_000_000L || metadataCount > 10_000_000L) {
            throw new IOException("GGUF header count is implausibly large");
        }
        return new Header(version, tensorCount, metadataCount);
    }

    private static int readLittleInt(InputStream input) throws IOException {
        byte[] b = readExact(input, 4);
        return (b[0] & 0xFF)
                | ((b[1] & 0xFF) << 8)
                | ((b[2] & 0xFF) << 16)
                | ((b[3] & 0xFF) << 24);
    }

    private static long readLittleLong(InputStream input) throws IOException {
        byte[] b = readExact(input, 8);
        return ((long) b[0] & 0xFFL)
                | (((long) b[1] & 0xFFL) << 8)
                | (((long) b[2] & 0xFFL) << 16)
                | (((long) b[3] & 0xFFL) << 24)
                | (((long) b[4] & 0xFFL) << 32)
                | (((long) b[5] & 0xFFL) << 40)
                | (((long) b[6] & 0xFFL) << 48)
                | (((long) b[7] & 0xFFL) << 56);
    }

    private static byte[] readExact(InputStream input, int size) throws IOException {
        byte[] buffer = new byte[size];
        int offset = 0;
        while (offset < size) {
            int count = input.read(buffer, offset, size - offset);
            if (count < 0) throw new EOFException("truncated GGUF header");
            offset += count;
        }
        return buffer;
    }
}
