package dev.mygpt.llama

import android.content.Context
import com.arm.aichat.AiChat
import com.arm.aichat.InferenceEngine
import kotlinx.coroutines.flow.Flow
import java.io.File

/**
 * Thin MyGPT-owned adapter over the pinned llama.cpp Android binding.
 *
 * This module is intentionally isolated from the Java-8 Spine host. It uses the
 * upstream Android requirements (API 33+, Java/Kotlin 17, NDK 29) and exposes
 * only the local-model lifecycle MyGPT needs.
 */
class LlamaCppCompanionEngine internal constructor(
    private val engine: InferenceEngine,
) : AutoCloseable {

    constructor(context: Context) : this(
        AiChat.getInferenceEngine(context.applicationContext)
    )

    val state: Flow<InferenceEngine.State>
        get() = engine.state

    suspend fun load(
        modelFile: File,
        approvedSystemPrompt: String,
    ) {
        require(modelFile.isFile) { "model file not found" }
        require(modelFile.canRead()) { "model file is not readable" }
        require(approvedSystemPrompt.isNotBlank()) { "system prompt is blank" }
        require(approvedSystemPrompt.length <= 8000) { "system prompt too long" }

        engine.loadModel(modelFile.absolutePath)
        try {
            engine.setSystemPrompt(approvedSystemPrompt)
        }
        catch (error: Throwable) {
            runCatching { engine.cleanUp() }
            throw error
        }
    }

    fun generate(
        userPrompt: String,
        predictLength: Int = InferenceEngine.DEFAULT_PREDICT_LENGTH,
    ): Flow<String> {
        require(userPrompt.isNotBlank()) { "user prompt is blank" }
        require(userPrompt.length <= 12000) { "user prompt too long" }
        require(predictLength in 1..8192) { "predictLength must be in 1..8192" }
        return engine.sendUserPrompt(userPrompt, predictLength)
    }

    suspend fun benchmark(
        promptProcessingTokens: Int = 128,
        generatedTokens: Int = 64,
        parallelSequences: Int = 1,
        repetitions: Int = 1,
    ): String {
        require(promptProcessingTokens in 1..8192)
        require(generatedTokens in 1..8192)
        require(parallelSequences in 1..16)
        require(repetitions in 1..20)
        return engine.bench(
            promptProcessingTokens,
            generatedTokens,
            parallelSequences,
            repetitions,
        )
    }

    fun unload() {
        engine.cleanUp()
    }

    /**
     * Release the currently loaded model without destroying llama.cpp's
     * process-wide singleton. Upstream AiChat keeps a static singleton reference;
     * destroying it inside an Activity lifecycle would make later Activity
     * recreation reuse an already-destroyed engine.
     *
     * Process termination is left to Android/OS cleanup.
     */
    override fun close() {
        runCatching { engine.cleanUp() }
    }
}
