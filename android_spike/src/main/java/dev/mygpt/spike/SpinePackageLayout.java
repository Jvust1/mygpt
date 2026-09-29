package dev.mygpt.spike;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HashSet;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/** Validates and installs the decrypted Live 3714430278 package without any LPK decryption step. */
public final class SpinePackageLayout {
    public static final String SKIN_ID = "3714430278";
    public static final String EXPECTED_ARCHIVE_SHA256 =
            "eb6eddc96172c03fe4d0dd4dd8a68180ce832aeb82ae07f7f82175fed57bc23f";

    // A ZIP may be repacked without changing the actual skin. These three hashes pin the
    // executable/rendered content rather than ZIP container metadata.
    private static final String EXPECTED_SKELETON_SHA256 =
            "990dbb1e9eafddfbc4972dd8431cee4c9ca1532f6448548ee0eaddf1c9e3d66e";
    private static final String EXPECTED_ATLAS_SHA256 =
            "de4677f5dc475f0399fa18b4a652f46a6ddea9762aafd5d0a591cd5ce67de8b0";
    private static final String EXPECTED_TEXTURE_SHA256 =
            "01dab8b08ad1b848e0788c0df7ae05357c1476704ad5d15f62fb31ec6bc98434";

    private static final long MAX_ARCHIVE_BYTES = 16L * 1024L * 1024L;
    private static final long MAX_ENTRY_BYTES = 8L * 1024L * 1024L;
    private static final long MAX_TOTAL_EXTRACTED_BYTES = 20L * 1024L * 1024L;
    private static final Pattern SPINE_VERSION = Pattern.compile("4\\.1\\.[0-9]+");

    private static final Set<String> REQUIRED = new HashSet<String>();
    static {
        REQUIRED.add("model.json");
        REQUIRED.add("skeleton.bin");
        REQUIRED.add("c610_00.atlas");
        REQUIRED.add("c610_00.png");
        REQUIRED.add("lpk_files.json");
    }

    private SpinePackageLayout() {}

    public static final class InstalledSkin {
        public final File directory;
        public final String spineVersion;
        public final String archiveSha256;
        public final String identityMode;

        InstalledSkin(File directory, String spineVersion, String archiveSha256, String identityMode) {
            this.directory = directory;
            this.spineVersion = spineVersion;
            this.archiveSha256 = archiveSha256;
            this.identityMode = identityMode;
        }
    }

    /**
     * User import path. Prefer the canonical ZIP SHA, but permit a repacked ZIP when its actual
     * Spine skeleton, atlas and texture bytes exactly match Live skin 3714430278.
     */
    public static InstalledSkin install(InputStream source, File targetDirectory) throws IOException {
        return installInternal(source, targetDirectory, EXPECTED_ARCHIVE_SHA256,
                false, true);
    }

    /** Package-private exact-container overload for deterministic tests. */
    static InstalledSkin install(InputStream source, File targetDirectory, String expectedSha256)
            throws IOException {
        return installInternal(source, targetDirectory, expectedSha256,
                expectedSha256 != null, false);
    }

    /** Validate an already-installed app-private copy so normal launches need no file picker. */
    public static String validateInstalled(File directory) throws IOException {
        return validateExtracted(directory, true);
    }

    private static InstalledSkin installInternal(InputStream source, File targetDirectory,
            String expectedSha256, boolean requireExactArchive, boolean verifyProductionCore)
            throws IOException {
        if (source == null) throw new IllegalArgumentException("source cannot be null");
        if (targetDirectory == null) throw new IllegalArgumentException("targetDirectory cannot be null");

        File parent = targetDirectory.getParentFile();
        if (parent == null) throw new IOException("target directory must have a parent");
        if (!parent.exists() && !parent.mkdirs()) throw new IOException("cannot create skin parent");

        File archive = new File(parent, targetDirectory.getName() + ".incoming.zip");
        File staging = new File(parent, targetDirectory.getName() + ".staging");
        deleteRecursively(archive);
        deleteRecursively(staging);

        String archiveSha = copyAndDigest(source, archive);
        boolean exactArchive = expectedSha256 != null
                && expectedSha256.equalsIgnoreCase(archiveSha);
        if (requireExactArchive && !exactArchive) {
            deleteRecursively(archive);
            throw new IOException("archive SHA-256 mismatch: " + archiveSha);
        }

        if (!staging.mkdirs()) {
            deleteRecursively(archive);
            throw new IOException("cannot create staging directory");
        }

        Set<String> found = new HashSet<String>();
        long extractedTotal = 0L;
        try (ZipInputStream zip = new ZipInputStream(
                new BufferedInputStream(new FileInputStream(archive)))) {
            ZipEntry entry;
            byte[] buffer = new byte[32 * 1024];
            while ((entry = zip.getNextEntry()) != null) {
                if (entry.isDirectory()) continue;

                String name = normalizeFlatEntry(entry.getName());
                if (!REQUIRED.contains(name)) continue;
                if (!found.add(name)) throw new IOException("duplicate runtime entry: " + name);
                if (entry.getSize() > MAX_ENTRY_BYTES) throw new IOException("entry too large: " + name);

                File output = new File(staging, name);
                long entryBytes = 0L;
                try (BufferedOutputStream out =
                             new BufferedOutputStream(new FileOutputStream(output))) {
                    int read;
                    while ((read = zip.read(buffer)) != -1) {
                        entryBytes += read;
                        extractedTotal += read;
                        if (entryBytes > MAX_ENTRY_BYTES
                                || extractedTotal > MAX_TOTAL_EXTRACTED_BYTES) {
                            throw new IOException("decompressed size limit exceeded");
                        }
                        out.write(buffer, 0, read);
                    }
                }
            }
        } catch (IOException error) {
            deleteRecursively(staging);
            deleteRecursively(archive);
            throw error;
        } finally {
            deleteRecursively(archive);
        }

        if (!found.containsAll(REQUIRED)) {
            Set<String> missing = new HashSet<String>(REQUIRED);
            missing.removeAll(found);
            deleteRecursively(staging);
            throw new IOException("missing required runtime files: " + missing);
        }

        final String version;
        try {
            version = validateExtracted(staging, verifyProductionCore);
        } catch (IOException error) {
            deleteRecursively(staging);
            throw error;
        }

        deleteRecursively(targetDirectory);
        if (!staging.renameTo(targetDirectory)) {
            deleteRecursively(staging);
            throw new IOException("cannot promote installed skin");
        }

        String identityMode = exactArchive ? "EXACT_ARCHIVE" :
                (verifyProductionCore ? "VERIFIED_CORE_CONTENT" : "STRUCTURE_ONLY_TEST");
        return new InstalledSkin(targetDirectory, version, archiveSha, identityMode);
    }

    private static String validateExtracted(File directory, boolean verifyProductionCore)
            throws IOException {
        if (directory == null || !directory.isDirectory())
            throw new IOException("installed skin directory missing");

        for (String name : REQUIRED) {
            if (!new File(directory, name).isFile())
                throw new IOException("installed skin missing: " + name);
        }

        String manifest = readUtf8(new File(directory, "lpk_files.json"));
        if (!manifest.contains("\"fileId\": \"" + SKIN_ID + "\"")
                && !manifest.contains("\"fileId\":\"" + SKIN_ID + "\"")) {
            throw new IOException("package is not Live skin " + SKIN_ID);
        }

        String model = readUtf8(new File(directory, "model.json"));
        if ((!model.contains("\"type\":9") && !model.contains("\"type\": 9"))
                || !model.contains("\"idle\"")) {
            throw new IOException("unexpected Spine model metadata");
        }

        String atlas = readUtf8(new File(directory, "c610_00.atlas"));
        if (!atlas.startsWith("c610_00.png")
                || (!atlas.contains("pma:true") && !atlas.contains("pma: true"))) {
            throw new IOException("unexpected atlas identity or PMA setting");
        }

        String version = detectSpineVersion(new File(directory, "skeleton.bin"));
        if (version == null || !version.startsWith("4.1.")) {
            throw new IOException("unsupported Spine binary version: " + version);
        }

        if (verifyProductionCore) {
            verifyFileSha(new File(directory, "skeleton.bin"),
                    EXPECTED_SKELETON_SHA256, "skeleton.bin");
            verifyFileSha(new File(directory, "c610_00.atlas"),
                    EXPECTED_ATLAS_SHA256, "c610_00.atlas");
            verifyFileSha(new File(directory, "c610_00.png"),
                    EXPECTED_TEXTURE_SHA256, "c610_00.png");
        }

        return version;
    }

    private static void verifyFileSha(File file, String expected, String label) throws IOException {
        String actual = sha256(file);
        if (!expected.equalsIgnoreCase(actual))
            throw new IOException(label + " content mismatch: " + actual);
    }

    private static String sha256(File file) throws IOException {
        final MessageDigest digest;
        try {
            digest = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException impossible) {
            throw new IOException("SHA-256 unavailable", impossible);
        }
        byte[] buffer = new byte[32 * 1024];
        try (FileInputStream in = new FileInputStream(file)) {
            int read;
            while ((read = in.read(buffer)) != -1) digest.update(buffer, 0, read);
        }
        return hex(digest.digest());
    }

    private static String copyAndDigest(InputStream source, File archive) throws IOException {
        final MessageDigest digest;
        try {
            digest = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException impossible) {
            throw new IOException("SHA-256 unavailable", impossible);
        }

        byte[] buffer = new byte[32 * 1024];
        long total = 0L;
        try (BufferedInputStream in = new BufferedInputStream(source);
             BufferedOutputStream out = new BufferedOutputStream(new FileOutputStream(archive))) {
            int read;
            while ((read = in.read(buffer)) != -1) {
                total += read;
                if (total > MAX_ARCHIVE_BYTES) throw new IOException("archive size limit exceeded");
                digest.update(buffer, 0, read);
                out.write(buffer, 0, read);
            }
        } catch (IOException error) {
            deleteRecursively(archive);
            throw error;
        }
        return hex(digest.digest());
    }

    private static String readUtf8(File file) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buffer = new byte[4096];
        try (FileInputStream input = new FileInputStream(file)) {
            int read;
            while ((read = input.read(buffer)) != -1) {
                if (out.size() + read > MAX_ENTRY_BYTES) throw new IOException("text file too large");
                out.write(buffer, 0, read);
            }
        }
        return new String(out.toByteArray(), StandardCharsets.UTF_8);
    }

    private static String normalizeFlatEntry(String raw) throws IOException {
        if (raw == null) throw new IOException("null zip entry");
        String name = raw.replace('\\', '/');
        if (name.startsWith("/") || name.contains("../") || name.contains("/"))
            throw new IOException("nested or unsafe zip entry: " + raw);
        return name;
    }

    static String detectSpineVersion(File skeleton) throws IOException {
        byte[] head = new byte[128];
        int count;
        try (FileInputStream input = new FileInputStream(skeleton)) {
            count = input.read(head);
        }
        if (count <= 0) return null;
        String probe = new String(head, 0, count, StandardCharsets.ISO_8859_1);
        Matcher matcher = SPINE_VERSION.matcher(probe);
        return matcher.find() ? matcher.group() : null;
    }

    static void deleteRecursively(File file) throws IOException {
        if (file == null || !file.exists()) return;
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children != null) {
                for (File child : children) deleteRecursively(child);
            }
        }
        if (!file.delete()) throw new IOException("cannot delete " + file);
    }

    private static String hex(byte[] bytes) {
        char[] out = new char[bytes.length * 2];
        final char[] digits = "0123456789abcdef".toCharArray();
        for (int i = 0; i < bytes.length; i++) {
            int value = bytes[i] & 0xff;
            out[i * 2] = digits[value >>> 4];
            out[i * 2 + 1] = digits[value & 0x0f];
        }
        return new String(out);
    }
}
