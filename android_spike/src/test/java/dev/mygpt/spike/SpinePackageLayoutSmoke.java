package dev.mygpt.spike;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

public final class SpinePackageLayoutSmoke {
    public static void main(String[] args) throws Exception {
        File root = Files.createTempDirectory("mygpt-spine-layout").toFile();
        try {
            SpinePackageLayout.InstalledSkin skin = SpinePackageLayout.install(
                    new ByteArrayInputStream(validZip()), new File(root, "skin"));
            require("4.1.20".equals(skin.spineVersion), "detects Spine 4.1.20");
            require(new File(skin.directory, "c610_00.atlas").isFile(), "extracts atlas");
            require(new File(skin.directory, "c610_00.png").isFile(), "extracts texture");

            boolean missingRejected = false;
            try {
                SpinePackageLayout.install(new ByteArrayInputStream(invalidZip()), new File(root, "bad"));
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
            put(zip, "model.json", "{}");
            put(zip, "skeleton.bin", "hash-prefix\\u00074.1.20-data");
            put(zip, "c610_00.atlas", "c610_00.png\\nsize:1,1\\npma:true\\n");
            putBytes(zip, "c610_00.png", new byte[]{1,2,3,4});
            put(zip, "lpk_files.json", "{\"fileId\": \"3714430278\"}");
            put(zip, "misc_ignored.bin", "ignored");
        }
        return out.toByteArray();
    }

    private static byte[] invalidZip() throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        try (ZipOutputStream zip = new ZipOutputStream(out)) {
            put(zip, "model.json", "{}");
            put(zip, "skeleton.bin", "4.1.20");
            put(zip, "lpk_files.json", "{\"fileId\": \"3714430278\"}");
        }
        return out.toByteArray();
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
