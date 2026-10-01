package dev.mygpt.spike;

import java.io.File;
import java.util.concurrent.Future;

/**
 * Renderer/provider-neutral local LLM contract for the Android companion.
 *
 * The lifecycle/state shape is adapted from llama.cpp's MIT-licensed Android
 * InferenceEngine. Native/JNI implementation is intentionally separate.
 */
public interface LocalLlmEngine extends AutoCloseable {
    int DEFAULT_PREDICT_LENGTH = 1024;

    enum State {
        INITIALIZED,
        LOADING_MODEL,
        MODEL_READY,
        PROCESSING_SYSTEM_PROMPT,
        GENERATING,
        UNLOADING_MODEL,
        ERROR,
        DESTROYED
    }

    interface TokenSink {
        void onToken(String token);
    }

    State state();

    Future<Void> loadModel(File modelFile);

    Future<Void> setSystemPrompt(String systemPrompt);

    Future<Void> generate(String userPrompt, int predictLength, TokenSink sink);

    void cancelGeneration();

    Future<Void> unloadModel();

    @Override
    void close();
}
