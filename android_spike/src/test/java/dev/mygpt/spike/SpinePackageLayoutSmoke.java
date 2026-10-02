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
            require("4.1.20".equals(skin.spineVersion), "detects default Spine 4.1.20");
            require(sha256(good).equals(skin.archiveSha256), "returns archive digest");

            require(new File(skin.directory, "c610_00.atlas").isFile(), "extracts default atlas");
            require(new File(skin.directory, "misc_01.bin").isFile(), "extracts aim skeleton");
            require(new File(skin.directory, "misc_02.atlas").isFile(), "extracts aim atlas");
            require(new File(skin.directory, "misc_04.png").isFile(), "extracts aim texture");
            require(new File(skin.directory, "misc_08.bin").isFile(), "extracts cover skeleton");
            require(new File(skin.directory, "misc_03.atlas").isFile(), "extracts cover atlas");
            require(new File(skin.directory, "misc_05.png").isFile(), "extracts cover texture");
            require(new File(skin.directory, "misc_06.json").isFile(), "extracts aim config");
            require(new File(skin.directory, "misc_07.json").isFile(), "extracts cover config");
            require(new File(skin.directory, "c610_aim_00.png").isFile(), "creates aim texture alias");
            require(new File(skin.directory, "c610_cover_00.png").isFile(), "creates cover texture alias");

            boolean wrongHashRejected = false;
            try {
                SpinePackageLayout.install(new ByteArrayInputStream(good),
                        new File(root, "wrong-hash"),
                        "0000000000000000000000000000000000000000000000000000000000000000");
            } catch (IOException expected) {
                wrongHashRejected = true;
            }
            require(wrongHashRejected, "rejects wrong archive SHA-256");

            boolean missingRejected = false;
            byte[] bad = invalidZip();
            try {
                SpinePackageLayout.install(new ByteArrayInputStream(bad),
                        new File(root, "bad"), sha256(bad));
            } catch (IOException expected) {
                missingRejected = true;
            }
            require(missingRejected, "rejects incomplete multi-form package");
            System.out.println("SpinePackageLayoutSmoke PASS");
        } finally {
            SpinePackageLayout.deleteRecursively(root);
        }
    }

    private static byte[] validZip() throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        try (ZipOutputStream zip = new ZipOutputStream(out)) {
            put(zip, "model.json",
                    "{\"type\":9,\"motions\":{\"idle\":[{\"file\":\"idle\"}],"
                    + "\"tap\":[{\"file\":\"smile\"},{\"file\":\"special\"}]}}");
            put(zip, "skeleton.bin", "hash-prefix\u00074.1.20-default");
            put(zip, "c610_00.atlas", "c610_00.png\nsize:1,1\npma:true\n");
            putBytes(zip, "c610_00.png", new byte[]{1,2,3,4});

            put(zip, "misc_01.bin", "hash-prefix\u00074.1.20-aim");
            put(zip, "misc_02.atlas", "c610_aim_00.png\nsize:1,1\npma:true\n");
            putBytes(zip, "misc_04.png", new byte[]{5,6,7,8});
            put(zip, "misc_06.json",
                    "{\"type\":9,\"motions\":{\"idle\":[{\"file\":\"aim_idle\"}],"
                    + "\"tap\":[{\"file\":\"aim_fire\"},{\"file\":\"to_cover\","
                    + "\"post_command\":\"change_cos a577a19ec0666bd04bd8d0a61cfcab2c.bin\"}]}}");

            put(zip, "misc_08.bin", "hash-prefix\u00074.1.20-cover");
            put(zip, "misc_03.atlas", "c610_cover_00.png\nsize:1,1\npma:true\n");
            putBytes(zip, "misc_05.png", new byte[]{9,10,11,12});
            put(zip, "misc_07.json",
                    "{\"type\":9,\"motions\":{\"idle\":[{\"file\":\"cover_idle\"}],"
                    + "\"tap\":[{\"file\":\"cover_reload\"},{\"file\":\"to_aim\","
                    + "\"post_command\":\"change_cos 6e9d962cc9ff8af8063a1354ff9b9540.bin\"}]}}");

            put(zip, "lpk_files.json", "{\"fileId\": \"3714430278\"}");
        }
        return out.toByteArray();
    }

    private static byte[] invalidZip() throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        try (ZipOutputStream zip = new ZipOutputStream(out)) {
            put(zip, "model.json", "{\"type\":9,\"motions\":{\"idle\":[]}}");
            put(zip, "skeleton.bin", "4.1.20");
            put(zip, "c610_00.atlas", "c610_00.png\npma:true\n");
            putBytes(zip, "c610_00.png", new byte[]{1});
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
