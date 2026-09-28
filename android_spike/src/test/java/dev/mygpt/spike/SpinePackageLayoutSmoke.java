package dev.mygpt.spike;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

public final class SpinePackageLayoutSmoke {
    public static void main(String[] args) throws Exception {
        File root = Files.createTempDirectory("mygpt-spine-layout").toFile();
        try {
            byte[] good = validZip();
            SpinePackageLayout.InstalledSkin skin = SpinePackageLayout.install(
                    new ByteArrayInputStream(good), new File(root, "skin"), sha256(good));
            require("4.1.20".equals(skin.spineVersion), "detects Spine 4.1.20");
            require(sha256(good).equals(skin.archiveSha256), "returns archive digest");
            require(new File(skin.directory, "c610_00.atlas").isFile(), "extracts atlas");
            require(new File(skin.directory, "c610_00.png").isFile(), "extracts texture");

            boolean wrongHashRejected = false;
            try {
                SpinePackageLayout.install(new ByteArrayInputStream(good), new File(root, "wrong-hash"),
                        "0000000000000000000000000000000000000000000000000000000000000000");
            } catch (IOException expected) {
                wrongHashRejected = true;
            }
            require(wrongHashRejected, "rejects wrong archive SHA-256");

            boolean missingRejected = false;
            byte[] bad = invalidZip();
            try {
                SpinePackageLayout.install(new ByteArrayInputStream(bad), new File(root, "bad"), sha256(bad));
            } catch (IOException expected) {
                missingRejected = true;
            }
            require(missingRejected, "rejects incomplete package");
            System.out.println("SpinePackageLayoutSmoke PASS");
        } finally {
            SpinePackageLayout.deleteRecursively(root);
        }
    }

    private static byte[] validZip() throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        try (ZipOutputStream zip = new ZipOutputStream(out)) {
            put(zip, "model.json", "{\"type\":9}");
            put(zip, "skeleton.bin", "hash-prefix\\u00074.1.20-data");
            put(zip, "c610_00.atlas", "c610_00.png\nsize:1,1\npma:true\n");
            putBytes(zip, "c610_00.png", new byte[]{1,2,3,4});
            put(zip, "lpk_files.json", "{\"fileId\": \"3714430278\"}");
            put(zip, "misc_ignored.bin", "ignored");
        }
        return out.toByteArray();
    }

    private static byte[] invalidZip() throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        try (ZipOutputStream zip = new ZipOutputStream(out)) {
            put(zip, "model.json", "{\"type\":9}");
            put(zip, "skeleton.bin", "4.1.20");
            put(zip, "lpk_files.json", "{\"fileId\": \"3714430278\"}");
        }
        return out.toByteArray();
    }

    private static String sha256(byte[] value) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        byte[] hash = digest.digest(value);
        StringBuilder out = new StringBuilder(hash.length * 2);
        for (byte b : hash) out.append(String.format("%02x", b & 0xff));
        return out.toString();
    }

    private static void put(ZipOutputStream zip, String name, String value) throws IOException {
        putBytes(zip, name, value.getBytes(StandardCharsets.UTF_8));
    }

    private static void putBytes(ZipOutputStream zip, String name, byte[] value) throws IOException {
        zip.putNextEntry(new ZipEntry(name));
        zip.write(value);
        zip.closeEntry();
    }

    private static void require(boolean value, String label) {
        if (!value) throw new AssertionError(label);
    }
}
