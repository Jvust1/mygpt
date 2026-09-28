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
import java.nio.file.Files;
import java.util.HashSet;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/** Validates and installs the decrypted Live 3714430278 package without any LPK decryption step. */
public final class SpinePackageLayout {
    public static final String SKIN_ID = "3714430278";
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
        InstalledSkin(File directory, String spineVersion) {
            this.directory = directory;
            this.spineVersion = spineVersion;
        }
    }

    public static InstalledSkin install(InputStream source, File targetDirectory) throws IOException {
        if (source == null) throw new IllegalArgumentException("source cannot be null");
        if (targetDirectory == null) throw new IllegalArgumentException("targetDirectory cannot be null");
        File parent = targetDirectory.getParentFile();
        if (parent == null) throw new IOException("target directory must have a parent");
        if (!parent.exists() && !parent.mkdirs()) throw new IOException("cannot create skin parent");

        File staging = new File(parent, targetDirectory.getName() + ".staging");
        deleteRecursively(staging);
        if (!staging.mkdirs()) throw new IOException("cannot create staging directory");

        Set<String> found = new HashSet<String>();
        long total = 0L;
        try (ZipInputStream zip = new ZipInputStream(new BufferedInputStream(source))) {
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
            throw error;
        }

        if (!found.containsAll(REQUIRED)) {
            Set<String> missing = new HashSet<String>(REQUIRED);
            missing.removeAll(found);
            deleteRecursively(staging);
            throw new IOException("missing required runtime files: " + missing);
        }

        String manifest = new String(Files.readAllBytes(new File(staging, "lpk_files.json").toPath()),
                StandardCharsets.UTF_8);
        if (!manifest.contains("\"fileId\": \"" + SKIN_ID + "\"")
                && !manifest.contains("\"fileId\":\"" + SKIN_ID + "\"")) {
            deleteRecursively(staging);
            throw new IOException("package is not Live skin " + SKIN_ID);
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
        return new InstalledSkin(targetDirectory, version);
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
}
