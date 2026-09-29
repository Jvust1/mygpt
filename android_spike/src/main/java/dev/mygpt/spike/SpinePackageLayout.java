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
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/** Full-package installer/validator for decrypted Live skin 3714430278. */
public final class SpinePackageLayout {
    public static final String SKIN_ID = "3714430278";
    public static final String EXPECTED_ARCHIVE_SHA256 =
            "eb6eddc96172c03fe4d0dd4dd8a68180ce832aeb82ae07f7f82175fed57bc23f";

    private static final long MAX_ARCHIVE_BYTES = 16L * 1024L * 1024L;
    private static final long MAX_ENTRY_BYTES = 8L * 1024L * 1024L;
    private static final long MAX_TOTAL_EXTRACTED_BYTES = 20L * 1024L * 1024L;
    private static final Pattern SPINE_VERSION = Pattern.compile("4\\.1\\.[0-9]+");

    private static final Set<String> REQUIRED = new HashSet<String>();
    private static final Map<String, String> EXPECTED_SHA256 = new HashMap<String, String>();

    static {
        require("model.json", "da9950af3cb0df0a234421a488ad4e2049660f16f5c1077c618b0b6ba88ea219");
        require("skeleton.bin", "990dbb1e9eafddfbc4972dd8431cee4c9ca1532f6448548ee0eaddf1c9e3d66e");
        require("c610_00.atlas", "de4677f5dc475f0399fa18b4a652f46a6ddea9762aafd5d0a591cd5ce67de8b0");
        require("c610_00.png", "01dab8b08ad1b848e0788c0df7ae05357c1476704ad5d15f62fb31ec6bc98434");
        require("misc_01.bin", "1805d1469f7b697f1fb573cdc9689e839e79a68955aa73250dd974766695068a");
        require("misc_02.atlas", "b90c459331813f5b82137a81e9aa770c2724d5d8ba769f13c83abc40b2265057");
        require("misc_03.atlas", "5114e6f8ba8d327a9fdf884d551a90922c1d4cd35a90f929200a3374a2afbcd7");
        require("misc_04.png", "f48a88763db8622cd361ddb14973d352adeff66145012f6e276429cdecf99657");
        require("misc_05.png", "2c87577ebbf430f70b2dd4300f61ab0f8f78a8bde5bc44b8f9ad63d346e4ed52");
        require("misc_06.json", "a10230a0a6eecd0f2d633a9557d7751c4eeb2ac4622d69cdbd30ac35d86b3834");
        require("misc_07.json", "41a912a970d33cb81831209a1a4cd5956e6a041b8718bbda05040aa01b4a3606");
        require("misc_08.bin", "bc7166c98f924e87d3ea51f23f761752b5dd8560ad0b80b37f67af0675bb783a");
        require("lpk_files.json", "68d674d76f4875289b6b0ff971a2510ca92fe1db61740e6072d67b938d2e8ba2");
    }

    private static void require(String file, String sha256) {
        REQUIRED.add(file);
        EXPECTED_SHA256.put(file, sha256);
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

    public static InstalledSkin install(InputStream source, File targetDirectory) throws IOException {
        return installInternal(source, targetDirectory, EXPECTED_ARCHIVE_SHA256, false, true);
    }

    static InstalledSkin install(InputStream source, File targetDirectory, String expectedSha256)
            throws IOException {
        return installInternal(source, targetDirectory, expectedSha256,
                expectedSha256 != null, false);
    }

    public static String validateInstalled(File directory) throws IOException {
        return validateExtracted(directory, true);
    }

    private static InstalledSkin installInternal(InputStream source, File targetDirectory,
            String expectedSha256, boolean requireExactArchive, boolean verifyProductionContent)
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
        boolean exactArchive = expectedSha256 != null && expectedSha256.equalsIgnoreCase(archiveSha);
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
            throw new IOException("missing required skin files: " + missing);
        }

        final String version;
        try {
            version = validateExtracted(staging, verifyProductionContent);
            prepareTextureAliases(staging);
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
                (verifyProductionContent ? "VERIFIED_FULL_CONTENT" : "STRUCTURE_ONLY_TEST");
        return new InstalledSkin(targetDirectory, version, archiveSha, identityMode);
    }

    private static String validateExtracted(File directory, boolean verifyProductionContent)
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
        String aim = readUtf8(new File(directory, "misc_06.json"));
        String cover = readUtf8(new File(directory, "misc_07.json"));

        if (!containsType9(model) || !model.contains("\"idle\"")
                || !model.contains("\"smile\"") || !model.contains("\"special\"")) {
            throw new IOException("unexpected default Spine metadata");
        }
        if (!containsType9(aim) || !aim.contains("aim_idle") || !aim.contains("aim_fire")
                || !aim.contains("to_cover")
                || !aim.contains("change_cos a577a19ec0666bd04bd8d0a61cfcab2c.bin")) {
            throw new IOException("unexpected aim Spine metadata");
        }
        if (!containsType9(cover) || !cover.contains("cover_idle")
                || !cover.contains("cover_reload") || !cover.contains("to_aim")
                || !cover.contains("change_cos 6e9d962cc9ff8af8063a1354ff9b9540.bin")) {
            throw new IOException("unexpected cover Spine metadata");
        }

        verifyAtlas(directory, "c610_00.atlas", "c610_00.png");
        verifyAtlas(directory, "misc_02.atlas", "c610_aim_00.png");
        verifyAtlas(directory, "misc_03.atlas", "c610_cover_00.png");

        String defaultVersion = detectSpineVersion(new File(directory, "skeleton.bin"));
        String aimVersion = detectSpineVersion(new File(directory, "misc_01.bin"));
        String coverVersion = detectSpineVersion(new File(directory, "misc_08.bin"));
        if (!isSpine41(defaultVersion) || !isSpine41(aimVersion) || !isSpine41(coverVersion)) {
            throw new IOException("unsupported Spine versions: default=" + defaultVersion
                    + ", aim=" + aimVersion + ", cover=" + coverVersion);
        }

        if (verifyProductionContent) {
            for (Map.Entry<String, String> entry : EXPECTED_SHA256.entrySet()) {
                verifyFileSha(new File(directory, entry.getKey()), entry.getValue(), entry.getKey());
            }
        }

        return defaultVersion;
    }

    private static boolean containsType9(String json) {
        return json.contains("\"type\":9") || json.contains("\"type\": 9");
    }

    private static boolean isSpine41(String value) {
        return value != null && value.startsWith("4.1.");
    }

    private static void verifyAtlas(File directory, String atlasName, String expectedTexture)
            throws IOException {
        String atlas = readUtf8(new File(directory, atlasName));
        if (!atlas.startsWith(expectedTexture)
                || (!atlas.contains("pma:true") && !atlas.contains("pma: true"))) {
            throw new IOException("unexpected atlas metadata: " + atlasName);
        }
    }

    private static void prepareTextureAliases(File directory) throws IOException {
        copyFileIfNeeded(new File(directory, "misc_04.png"),
                new File(directory, "c610_aim_00.png"));
        copyFileIfNeeded(new File(directory, "misc_05.png"),
                new File(directory, "c610_cover_00.png"));
    }

    private static void copyFileIfNeeded(File source, File target) throws IOException {
        if (target.isFile() && target.length() == source.length()) return;
        byte[] buffer = new byte[32 * 1024];
        try (FileInputStream in = new FileInputStream(source);
             BufferedOutputStream out = new BufferedOutputStream(new FileOutputStream(target))) {
            int read;
            while ((read = in.read(buffer)) != -1) out.write(buffer, 0, read);
        }
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
        byte[] head = new byte[160];
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
