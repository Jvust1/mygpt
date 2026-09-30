package dev.mygpt.voicespike;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

public final class SherpaModelIdentitySmoke {
    public static void main(String[] args) throws Exception {
        File root = Files.createTempDirectory("mygpt-sherpa-identity-").toFile();
        try {
            File abc = new File(root, "abc.bin");
            try (FileOutputStream output = new FileOutputStream(abc)) {
                output.write("abc".getBytes(StandardCharsets.UTF_8));
            }

            check(SherpaModelIdentity.verifyExact(
                    abc,
                    3L,
                    "ba7816bf8f01cfea414140de5dae2223"
                            + "b00361a396177a9cb410ff61f20015ad"
            ), "exact file passes");

            check(!SherpaModelIdentity.verifyExact(
                    abc,
                    4L,
                    "ba7816bf8f01cfea414140de5dae2223"
                            + "b00361a396177a9cb410ff61f20015ad"
            ), "wrong size rejected");

            check(!SherpaModelIdentity.verifyExact(
                    abc,
                    3L,
                    "0000000000000000000000000000000000000000000000000000000000000000"
            ), "wrong hash rejected");

            try (FileOutputStream output = new FileOutputStream(abc, true)) {
                output.write('x');
            }
            check(!SherpaModelIdentity.verifyExact(
                    abc,
                    3L,
                    "ba7816bf8f01cfea414140de5dae2223"
                            + "b00361a396177a9cb410ff61f20015ad"
            ), "tamper rejected");

            check(SherpaModelIdentity.ASR_REVISION.length() == 40,
                    "ASR revision pinned");
            check(SherpaModelIdentity.TTS_REVISION.length() == 40,
                    "TTS revision pinned");

            System.out.println("SherpaModelIdentitySmoke PASS");
        } finally {
            deleteRecursively(root);
        }
    }

    private static void deleteRecursively(File file) {
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children != null) {
                for (File child : children) deleteRecursively(child);
            }
        }
        file.delete();
    }

    private static void check(boolean value, String label) {
        if (!value) throw new AssertionError(label);
    }
}
