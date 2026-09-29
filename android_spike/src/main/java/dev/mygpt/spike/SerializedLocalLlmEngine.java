package dev.mygpt.spike;

import java.io.File;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

/**
 * Serialized execution boundary for one local model instance.
 *
 * llama.cpp's Android binding runs all native model operations on one dedicated
 * single-thread dispatcher because the underlying native context is not a
 * general concurrent object. This Java-8 adaptation keeps the same invariant
 * while leaving the actual backend replaceable.
 */
public final class SerializedLocalLlmEngine implements LocalLlmEngine {
    public interface Backend {
        void load(String modelPath) throws Exception;
        void setSystemPrompt(String systemPrompt) throws Exception;
        void generate(String userPrompt, int predictLength, TokenSink sink) throws Exception;
        void cancelGeneration();
        void unload() throws Exception;
        void destroy() throws Exception;
    }

    private final Backend backend;
    private final ExecutorService executor;
    private volatile State state = State.INITIALIZED;
    private volatile boolean readyForSystemPrompt = false;
    private volatile boolean closed = false;

    public SerializedLocalLlmEngine(Backend backend) {
        if (backend == null) throw new IllegalArgumentException("backend is required");
        this.backend = backend;
        this.executor = Executors.newSingleThreadExecutor(runnable -> {
            Thread thread = new Thread(runnable, "mygpt-local-llm");
            thread.setDaemon(true);
            return thread;
        });
    }

    @Override
    public State state() {
        return state;
    }

    private void requireOpen() {
        if (closed || state == State.DESTROYED) {
            throw new IllegalStateException("local LLM engine is destroyed");
        }
    }

    private void requireState(State expected, String operation) {
        requireOpen();
        if (state != expected) {
            throw new IllegalStateException(
                    operation + " is not allowed while state=" + state);
        }
    }

    private Future<Void> submit(Callable<Void> action) {
        requireOpen();
        return executor.submit(action);
    }

    @Override
    public Future<Void> loadModel(File modelFile) {
        if (modelFile == null) throw new IllegalArgumentException("modelFile is required");
        return submit(() -> {
            requireState(State.INITIALIZED, "loadModel");
            if (!modelFile.exists()) throw fail("model file not found", null);
            if (!modelFile.isFile()) throw fail("model path is not a file", null);
            if (!modelFile.canRead()) throw fail("model file is not readable", null);
            state = State.LOADING_MODEL;
            try {
                backend.load(modelFile.getAbsolutePath());
                readyForSystemPrompt = true;
                state = State.MODEL_READY;
                return null;
            } catch (Exception error) {
                throw fail("model load failed", error);
            }
        });
    }

    @Override
    public Future<Void> setSystemPrompt(String systemPrompt) {
        if (systemPrompt == null || systemPrompt.trim().isEmpty()) {
            throw new IllegalArgumentException("systemPrompt must not be blank");
        }
        if (systemPrompt.length() > 8000) {
            throw new IllegalArgumentException("systemPrompt too long");
        }
        return submit(() -> {
            requireState(State.MODEL_READY, "setSystemPrompt");
            if (!readyForSystemPrompt) {
                throw new IllegalStateException(
                        "system prompt may only be set immediately after model load");
            }
            state = State.PROCESSING_SYSTEM_PROMPT;
            try {
                backend.setSystemPrompt(systemPrompt);
                readyForSystemPrompt = false;
                state = State.MODEL_READY;
                return null;
            } catch (Exception error) {
                throw fail("system prompt failed", error);
            }
        });
    }

    @Override
    public Future<Void> generate(String userPrompt, int predictLength, TokenSink sink) {
        if (userPrompt == null || userPrompt.trim().isEmpty()) {
            throw new IllegalArgumentException("userPrompt must not be blank");
        }
        if (userPrompt.length() > 12000) {
            throw new IllegalArgumentException("userPrompt too long");
        }
        if (predictLength < 1 || predictLength > 8192) {
            throw new IllegalArgumentException("predictLength must be in 1..8192");
        }
        if (sink == null) throw new IllegalArgumentException("sink is required");
        return submit(() -> {
            requireState(State.MODEL_READY, "generate");
            readyForSystemPrompt = false;
            state = State.GENERATING;
            try {
                backend.generate(userPrompt, predictLength, token -> {
                    if (token != null && !token.isEmpty()) sink.onToken(token);
                });
                state = State.MODEL_READY;
                return null;
            } catch (Exception error) {
                throw fail("generation failed", error);
            }
        });
    }

    @Override
    public void cancelGeneration() {
        requireOpen();
        backend.cancelGeneration();
    }

    @Override
    public Future<Void> unloadModel() {
        return submit(() -> {
            requireOpen();
            if (state != State.MODEL_READY && state != State.ERROR) {
                throw new IllegalStateException(
                        "unloadModel is not allowed while state=" + state);
            }
            state = State.UNLOADING_MODEL;
            try {
                backend.unload();
                readyForSystemPrompt = false;
                state = State.INITIALIZED;
                return null;
            } catch (Exception error) {
                throw fail("model unload failed", error);
            }
        });
    }

    private RuntimeException fail(String message, Exception cause) {
        readyForSystemPrompt = false;
        state = State.ERROR;
        return cause == null
                ? new IllegalStateException(message)
                : new RuntimeException(message, cause);
    }

    @Override
    public void close() {
        if (closed) return;
        closed = true;
        try {
            Future<?> future = executor.submit(() -> {
                try {
                    backend.destroy();
                } catch (Exception ignored) {
                    // Destruction is best-effort; state still becomes terminal.
                }
            });
            future.get(5, TimeUnit.SECONDS);
        } catch (Exception ignored) {
            // Do not keep native resources alive because shutdown reporting failed.
        } finally {
            state = State.DESTROYED;
            readyForSystemPrompt = false;
            executor.shutdownNow();
        }
    }
}
