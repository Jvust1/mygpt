package dev.mygpt.voicespike;

import com.k2fsa.sherpa.onnx.OfflineTts;
import com.k2fsa.sherpa.onnx.OfflineTtsConfig;
import com.k2fsa.sherpa.onnx.OfflineTtsModelConfig;
import com.k2fsa.sherpa.onnx.OfflineTtsVitsModelConfig;

/**
 * One production/debug factory for the pinned sherpa Melo zh/en TTS config.
 */
public final class SherpaMeloTtsFactory {
    private SherpaMeloTtsFactory() {}

    public static OfflineTts create(
            SherpaMeloTtsModelInstaller.Installed model,
            int numThreads
    ) {
        if (model == null || !model.isComplete()) {
            throw new IllegalArgumentException("complete Melo TTS model is required");
        }
        if (numThreads < 1 || numThreads > 8) {
            throw new IllegalArgumentException("numThreads must be in 1..8");
        }

        OfflineTtsVitsModelConfig vits =
                OfflineTtsVitsModelConfig.builder()
                        .setModel(model.model.getAbsolutePath())
                        .setTokens(model.tokens.getAbsolutePath())
                        .setLexicon(model.lexicon.getAbsolutePath())
                        .build();

        OfflineTtsModelConfig modelConfig =
                OfflineTtsModelConfig.builder()
                        .setVits(vits)
                        .setNumThreads(numThreads)
                        .setDebug(false)
                        .setProvider("cpu")
                        .build();

        OfflineTtsConfig config =
                OfflineTtsConfig.builder()
                        .setModel(modelConfig)
                        .setRuleFsts(model.ruleFsts())
                        .setMaxNumSentences(1)
                        .build();

        return new OfflineTts(config);
    }
}
