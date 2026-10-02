package dev.mygpt.voicespike;

import org.apache.commons.compress.archivers.tar.TarArchiveEntry;
import org.apache.commons.compress.archivers.tar.TarArchiveInputStream;
import org.apache.commons.compress.compressors.bzip2.BZip2CompressorInputStream;
import org.apache.commons.compress.compressors.gzip.GzipCompressorInputStream;

import java.io.IOException;
import java.io.InputStream;
import java.io.PushbackInputStream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * Streaming model-archive reader.
 *
 * Supported inputs:
 * - ZIP
 * - TAR.BZ2 (sherpa official model release format)
 * - TAR.GZ
 *
 * The reader never chooses output paths. Callers must enforce an allowlist.
 */
public final class ModelArchiveReader {
    @FunctionalInterface
    public interface EntryConsumer {
        void accept(String name, boolean directory, InputStream data) throws IOException;
    }

    private ModelArchiveReader() {}

    public static void forEachEntry(InputStream source, EntryConsumer consumer)
            throws IOException {
        if (source == null) throw new IllegalArgumentException("source is required");
        if (consumer == null) throw new IllegalArgumentException("consumer is required");

        PushbackInputStream input = new PushbackInputStream(source, 8);
        byte[] prefix = new byte[4];
        int count = 0;
        while (count < prefix.length) {
            int n = input.read(prefix, count, prefix.length - count);
            if (n < 0) break;
            count += n;
        }
        if (count > 0) input.unread(prefix, 0, count);

        if (isZip(prefix, count)) {
            readZip(input, consumer);
            return;
        }
        if (isBzip2(prefix, count)) {
            try (BZip2CompressorInputStream bz =
                         new BZip2CompressorInputStream(input, true);
                 TarArchiveInputStream tar = new TarArchiveInputStream(bz)) {
                readTar(tar, consumer);
            }
            return;
        }
        if (isGzip(prefix, count)) {
            try (GzipCompressorInputStream gz =
                         new GzipCompressorInputStream(input, true);
                 TarArchiveInputStream tar = new TarArchiveInputStream(gz)) {
                readTar(tar, consumer);
            }
            return;
        }
        throw new IOException("unsupported model archive format");
    }

    private static void readZip(InputStream input, EntryConsumer consumer)
            throws IOException {
        try (ZipInputStream zip = new ZipInputStream(input)) {
            ZipEntry entry;
            while ((entry = zip.getNextEntry()) != null) {
                consumer.accept(entry.getName(), entry.isDirectory(), zip);
                zip.closeEntry();
            }
        }
    }

    private static void readTar(TarArchiveInputStream tar, EntryConsumer consumer)
            throws IOException {
        TarArchiveEntry entry;
        while ((entry = tar.getNextTarEntry()) != null) {
            consumer.accept(entry.getName(), entry.isDirectory(), tar);
        }
    }

    private static boolean isZip(byte[] p, int n) {
        return n >= 4
                && p[0] == 'P'
                && p[1] == 'K'
                && (p[2] == 3 || p[2] == 5 || p[2] == 7)
                && (p[3] == 4 || p[3] == 6 || p[3] == 8);
    }

    private static boolean isBzip2(byte[] p, int n) {
        return n >= 3 && p[0] == 'B' && p[1] == 'Z' && p[2] == 'h';
    }

    private static boolean isGzip(byte[] p, int n) {
        return n >= 2 && (p[0] & 0xFF) == 0x1F && (p[1] & 0xFF) == 0x8B;
    }
}
