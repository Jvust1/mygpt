package dev.mygpt.spike;

import java.io.ByteArrayInputStream;
import java.io.IOException;

public final class GgufModelProbeSmoke {
    public static void main(String[] args) throws Exception {
        byte[] valid = header(3, 321L, 77L);
        GgufModelProbe.Header parsed = GgufModelProbe.probe(new ByteArrayInputStream(valid));
        require(parsed.version == 3, "version");
        require(parsed.tensorCount == 321L, "tensor count");
        require(parsed.metadataCount == 77L, "metadata count");

        byte[] badMagic = valid.clone();
        badMagic[0] = 'B';
        expectIo(badMagic, "magic");

        byte[] badVersion = header(9, 1L, 1L);
        expectIo(badVersion, "version");

        byte[] truncated = new byte[] {'G','G','U','F',3,0,0,0};
        expectIo(truncated, "truncated");

        System.out.println("GgufModelProbeSmoke PASS");
    }

    private static byte[] header(int version, long tensors, long metadata) {
        byte[] out = new byte[24];
        out[0]='G'; out[1]='G'; out[2]='U'; out[3]='F';
        putInt(out,4,version);
        putLong(out,8,tensors);
        putLong(out,16,metadata);
        return out;
    }

    private static void putInt(byte[] out, int offset, int value) {
        for (int i=0;i<4;i++) out[offset+i]=(byte)((value >>> (8*i)) & 0xFF);
    }

    private static void putLong(byte[] out, int offset, long value) {
        for (int i=0;i<8;i++) out[offset+i]=(byte)((value >>> (8*i)) & 0xFF);
    }

    private static void expectIo(byte[] bytes, String label) {
        try {
            GgufModelProbe.probe(new ByteArrayInputStream(bytes));
            throw new AssertionError("expected IOException: " + label);
        } catch (IOException expected) {
            // pass
        }
    }

    private static void require(boolean value, String label) {
        if (!value) throw new AssertionError(label);
    }
}
