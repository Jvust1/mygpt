package dev.mygpt.voicespike;

import java.io.BufferedInputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Locale;

/**
 * Fixed upstream identities for the sherpa ASR/TTS core files used by MyGPT.
 *
 * ASR source:
 *   csukuangfj/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20
 *   revision 98590b7ed6443e77b714204da2757d75e1a642f4
 *
 * TTS model source:
 *   csukuangfj/vits-melo-tts-zh_en
 *   revision a0d5c6a264c0ef92d70d8661d8cc502d79627cd6
 */
public final class SherpaModelIdentity {
    public static final String ASR_REVISION =
            "98590b7ed6443e77b714204da2757d75e1a642f4";
    public static final String TTS_REVISION =
            "a0d5c6a264c0ef92d70d8661d8cc502d79627cd6";

    private static final Spec[] ASR_CORE = new Spec[] {
            new Spec(
                    "encoder-epoch-99-avg-1.int8.onnx",
                    181895032L,
                    "8fa764187a261844f859d7143ebaa563af5d10adfece4c18a8f414c88cba2a9b"
            ),
            new Spec(
                    "decoder-epoch-99-avg-1.onnx",
                    13876452L,
                    "2e3b5ec371f8899ee6acd829fd753ba45772df57a91bdf37cde3136354e7db7d"
            ),
            new Spec(
                    "joiner-epoch-99-avg-1.int8.onnx",
                    3228404L,
                    "1ed689c5ed19dbaa725d9d191bb4822b5f4855a39e1ffd28cbc1f340d25b2ee0"
            ),
            new Spec(
                    "tokens.txt",
                    75756L,
                    "59aba8873a2ed1e122c25fee421e25f283b63290efbde85c1f01a853d83cb6e6"
            )
    };

    private static final Spec TTS_MODEL = new Spec(
            "model.onnx",
            170429550L,
            "bf30582eb1b012250a35b1a4a80e7dfbcf8485e7bb9de0d95efbbeef0e4ad86d"
    );

    private SherpaModelIdentity() {}

    public static void requireAsrCore(File directory) throws IOException {
        requireDirectory(directory);
        for (Spec spec : ASR_CORE) {
            requireExact(new File(directory, spec.fileName), spec);
        }
    }

    /**
     * Hard-locks the executable TTS ONNX model. Supporting lexicon/FST/token
     * files remain protected by MyGPT's deterministic per-file manifest until
     * authoritative upstream digests are pinned for them too.
     */
    public static void requireTtsExecutableModel(File directory) throws IOException {
        requireDirectory(directory);
        requireExact(new File(directory, TTS_MODEL.fileName), TTS_MODEL);
    }

    static boolean verifyExact(
            File file,
            long expectedBytes,
            String expectedSha256
    ) throws IOException {
        return verifyExact(file, new Spec(file.getName(), expectedBytes, expectedSha256));
    }

    private static void requireExact(File file, Spec spec) throws IOException {
        if (!verifyExact(file, spec)) {
            throw new IOException(
                    "sherpa model identity mismatch: " + spec.fileName
            );
        }
    }

    private static boolean verifyExact(File file, Spec spec) throws IOException {
        if (file == null || !file.isFile() || !file.canRead()) return false;
        if (file.length() != spec.bytes) return false;
        return spec.sha256.equals(sha256(file));
    }

    private static void requireDirectory(File directory) throws IOException {
        if (directory == null || !directory.isDirectory()) {
            throw new IOException("sherpa model directory missing");
        }
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

        StringBuilder out = new StringBuilder(64);
        for (byte value : digest.digest()) {
            out.append(String.format(Locale.ROOT, "%02x", value & 0xFF));
        }
        return out.toString();
    }

    private static final class Spec {
        final String fileName;
        final long bytes;
        final String sha256;

        Spec(String fileName, long bytes, String sha256) {
            if (fileName == null
                    || fileName.isEmpty()
                    || fileName.contains("/")
                    || fileName.contains("\\")) {
                throw new IllegalArgumentException("invalid sherpa identity file name");
            }
            if (bytes <= 0L) {
                throw new IllegalArgumentException("invalid sherpa identity byte length");
            }
            if (sha256 == null
                    || !sha256.matches("^[0-9a-f]{64}$")) {
                throw new IllegalArgumentException("invalid sherpa identity SHA-256");
            }
            this.fileName = fileName;
            this.bytes = bytes;
            this.sha256 = sha256;
        }
    }
}
