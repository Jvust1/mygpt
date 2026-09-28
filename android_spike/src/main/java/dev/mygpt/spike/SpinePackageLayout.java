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
        InstalledSkin(File directory, String spineVersion, String archiveSha256) {
            this.directory = directory;
            this.spineVersion = spineVersion;
            this.archiveSha256 = archiveSha256;
        }
    }

    /** Copies the selected package into app-private storage and verifies the exact Live asset identity. */
    public static File cacheVerifiedPackage(InputStream source, File destination) throws IOException {
        if (source == null) throw new IllegalArgumentException("source cannot be null");
        if (destination == null) throw new IllegalArgumentException("destination cannot be null");
        File parent = destination.getParentFile();
        if (parent == null) throw new IOException("package destination must have a parent");
        if (!parent.exists() && !parent.mkdirs()) throw new IOException("cannot create package parent");

        File partial = new File(parent, destination.getName() + ".partial");
        if (partial.exists() && !partial.delete()) throw new IOException("cannot replace partial package");
        MessageDigest digest;
        try {
            digest = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException impossible) {
            throw new IOException("SHA-256 unavailable", impossible);
        }

        long total = 0L;
        byte[] buffer = new byte[32 * 1024];
        try (BufferedInputStream in = new BufferedInputStream(source);
             BufferedOutputStream out = new BufferedOutputStream(new FileOutputStream(partial))) {
            int read;
            while ((read = in.read(buffer)) != -1) {
                total += read;
                if (total > MAX_PACKAGE_BYTES) throw new IOException("package exceeds size limit");
                digest.update(buffer, 0, read);
                out.write(buffer, 0, read);
            }
        } catch (IOException error) {
            partial.delete();
            throw error;
        }

        String actual = hex(digest.digest());
        if (!EXPECTED_ZIP_SHA256.equals(actual)) {
            partial.delete();
            throw new IOException("package SHA-256 mismatch: " + actual);
        }
        if (destination.exists() && !destination.delete()) {
            partial.delete();
            throw new IOException("cannot replace cached package");
        }
        if (!partial.renameTo(destination)) {
            partial.delete();
            throw new IOException("cannot promote cached package");
        }
        return destination;
    }

    public static InstalledSkin install(File packageFile, File targetDirectory) throws IOException {
        try (FileInputStream input = new FileInputStream(packageFile)) {
            return install(input, targetDirectory);
        }
    }

    public static InstalledSkin install(InputStream source, File targetDirectory) throws IOException {
        return install(source, targetDirectory, EXPECTED_ARCHIVE_SHA256);
    }

    static InstalledSkin install(InputStream source, File targetDirectory, String expectedSha256)
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
        if (expectedSha256 != null && !expectedSha256.equalsIgnoreCase(archiveSha)) {
            deleteRecursively(archive);
            throw new IOException("archive SHA-256 mismatch");
        }

        if (!staging.mkdirs()) {
            deleteRecursively(archive);
            throw new IOException("cannot create staging directory");
        }

        Set<String> found = new HashSet<String>();
        long total = 0L;
        try (ZipInputStream zip = new ZipInputStream(new BufferedInputStream(new FileInputStream(archive)))) {
            ZipEntry entry;
            byte[] buffer = new byte[32 * 1024];
            while ((entry = zip.getNextEntry()) != null) {
                if (entry.isDirectory()) continue;
                String name = normalizeFlatEntry(entry.getName());
                if (!REQUIRED.contains(name)) continue;
                if (!found.add(name)) throw new IOException("duplicate runtime entry: " + name);
                if (entry.getSize() > MAX_ENTRY_BYTES) throw new IOException("entry too large: " + name);

                File output = new File(staging, name);
                long written = 0L;
                try (BufferedOutputStream out = new BufferedOutputStream(new FileOutputStream(output))) {
                    int read;
                    while ((read = zip.read(buffer)) != -1) {
                        written += read;
                        total += read;
                        if (written > MAX_ENTRY_BYTES || total > MAX_TOTAL_EXTRACTED_BYTES)
                            throw new IOException("decompressed size limit exceeded");
                        out.write(buffer, 0, read);
                    }
                }
            }
        } catch (IOException error) {
            deleteRecursively(staging);
            deleteRecursively(archive);
            throw error;
        }

        deleteRecursively(archive);

        if (!found.containsAll(REQUIRED)) {
            Set<String> missing = new HashSet<String>(REQUIRED);
            missing.removeAll(found);
            deleteRecursively(staging);
            throw new IOException("missing required runtime files: " + missing);
        }

        String manifest = readUtf8(new File(staging, "lpk_files.json"));
        if (!manifest.contains("\"fileId\": \"" + SKIN_ID + "\"")
                && !manifest.contains("\"fileId\":\"" + SKIN_ID + "\"")) {
            deleteRecursively(staging);
            throw new IOException("package is not Live skin " + SKIN_ID);
        }

        String model = readUtf8(new File(staging, "model.json"));
        if (!model.contains("\"type\":9") && !model.contains("\"type\": 9")) {
            deleteRecursively(staging);
            throw new IOException("skin model is not the expected Spine type");
        }

        String version = detectSpineVersion(new File(staging, "skeleton.bin"));
        if (version == null || !version.startsWith("4.1.")) {
            deleteRecursively(staging);
            throw new IOException("unsupported Spine binary version: " + version);
        }

        deleteRecursively(targetDirectory);
        if (!staging.renameTo(targetDirectory)) {
            deleteRecursively(staging);
            throw new IOException("cannot promote installed skin");
        }
        return new InstalledSkin(targetDirectory, version, archiveSha);
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

    private static String hex(byte[] value) {
        StringBuilder out = new StringBuilder(value.length * 2);
        for (byte b : value) out.append(String.format("%02x", b & 0xff));
        return out.toString();
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
