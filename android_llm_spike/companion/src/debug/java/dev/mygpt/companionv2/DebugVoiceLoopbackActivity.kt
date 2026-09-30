package dev.mygpt.companionv2

import android.app.Activity
import android.os.Bundle
import android.os.SystemClock
import android.widget.TextView
import com.k2fsa.sherpa.onnx.GeneratedAudio
import com.k2fsa.sherpa.onnx.OfflineTts
import dev.mygpt.voicespike.SherpaMeloTtsFactory
import dev.mygpt.voicespike.SherpaMeloTtsModelInstaller
import dev.mygpt.voicespike.SherpaStreamingAsrEngine
import dev.mygpt.voicespike.SherpaZhEnModelInstaller
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.nio.charset.StandardCharsets

/**
 * Debug-only native voice loopback:
 * Melo TTS -> in-memory float PCM -> 16 kHz resample -> streaming ASR.
 *
 * It never uses the microphone or speaker and never persists audio.
 */
class DebugVoiceLoopbackActivity : Activity() {
    private lateinit var status: TextView

    override fun onCreate(state: Bundle?) {
        super.onCreate(state)

        status = TextView(this).apply {
            text = "MyGPT sherpa native loopback running…"
            textSize = 16f
            setPadding(24, 32, 24, 32)
        }
        setContentView(status)

        Thread({
            val report = runLoopback()
            runOnUiThread {
                status.text = if (report.optBoolean("completed", false)) {
                    "Sherpa native loopback complete"
                } else {
                    "Sherpa native loopback failed"
                }
                finish()
            }
        }, "mygpt-voice-loopback").start()
    }

    private fun runLoopback(): JSONObject {
        val report = JSONObject()
        report.put("schema", "mygpt.voice-loopback.v1")
        report.put("phrase", PHRASE)
        report.put("audio_persisted", false)

        var tts: OfflineTts? = null
        var asr: SherpaStreamingAsrEngine? = null

        return try {
            val asrModel = SherpaZhEnModelInstaller.existing(
                File(filesDir, "asr-models")
            ) ?: error("ASR_MODEL_UNAVAILABLE")

            val ttsModel = SherpaMeloTtsModelInstaller.existing(
                File(filesDir, "tts-models")
            ) ?: error("TTS_MODEL_UNAVAILABLE")

            val ttsStart = SystemClock.elapsedRealtime()
            tts = SherpaMeloTtsFactory.create(ttsModel, 2)
            val generated: GeneratedAudio = tts.generate(PHRASE, 0, 1.0f)
            val ttsMs = SystemClock.elapsedRealtime() - ttsStart

            val samples = generated.samples
            val sourceRate = generated.sampleRate
            require(sourceRate > 0) { "invalid TTS sample rate" }
            require(samples.isNotEmpty()) { "TTS produced no samples" }

            val asrStart = SystemClock.elapsedRealtime()
            asr = SherpaStreamingAsrEngine(asrModel, 2)

            var transcript = ""
            var endpoint = false
            val chunkSamples = maxOf(1, sourceRate / 10)

            var offset = 0
            while (offset < samples.size) {
                val size = minOf(chunkSamples, samples.size - offset)
                val chunk = samples.copyOfRange(offset, offset + size)
                val result = asr.accept(chunk, sourceRate)
                if (result.text.isNotBlank()) {
                    transcript = result.text.trim()
                }
                if (result.endpoint) {
                    endpoint = true
                    if (result.text.isNotBlank()) {
                        transcript = result.text.trim()
                    }
                    break
                }
                offset += size
            }

            if (!endpoint) {
                val silence = FloatArray(chunkSamples)
                for (index in 0 until MAX_SILENCE_CHUNKS) {
                    val result = asr.accept(silence, sourceRate)
                    if (result.text.isNotBlank()) {
                        transcript = result.text.trim()
                    }
                    if (result.endpoint) {
                        endpoint = true
                        if (result.text.isNotBlank()) {
                            transcript = result.text.trim()
                        }
                        break
                    }
                }
            }

            val asrMs = SystemClock.elapsedRealtime() - asrStart
            require(transcript.isNotBlank()) { "ASR produced empty transcript" }

            report.put("tts_sample_rate", sourceRate)
            report.put("tts_samples", samples.size)
            report.put("tts_wall_ms", ttsMs)
            report.put("asr_input_sample_rate", sourceRate)
            report.put("asr_model_sample_rate", SherpaStreamingAsrEngine.SAMPLE_RATE)
            report.put("asr_internal_resample", sourceRate != SherpaStreamingAsrEngine.SAMPLE_RATE)
            report.put("asr_input_samples", samples.size)
            report.put("asr_wall_ms", asrMs)
            report.put("asr_endpoint", endpoint)
            report.put("transcript", transcript)
            report.put("completed", true)
            report.put("error", JSONObject.NULL)
            report
        } catch (error: Throwable) {
            report.put("completed", false)
            report.put("error", error.javaClass.simpleName)
            report.put("message", error.message ?: "")
            report
        } finally {
            runCatching { asr?.close() }
            runCatching { tts?.release() }
            persist(report)
        }
    }

    private fun persist(report: JSONObject) {
        val target = File(filesDir, RESULT_FILE)
        val temp = File(filesDir, RESULT_FILE + ".tmp")
        val bytes = (report.toString(2) + "\n").toByteArray(StandardCharsets.UTF_8)

        FileOutputStream(temp, false).use { output ->
            output.write(bytes)
            output.flush()
            output.fd.sync()
        }

        if (target.exists() && !target.delete()) {
            temp.delete()
            error("cannot replace voice loopback result")
        }
        if (!temp.renameTo(target)) {
            temp.delete()
            error("cannot commit voice loopback result")
        }
    }

    companion object {
        private const val PHRASE = "你好，今天一起学习。"
        private const val RESULT_FILE = "voice-loopback-result.json"
        private const val MAX_SILENCE_CHUNKS = 30
    }
}
