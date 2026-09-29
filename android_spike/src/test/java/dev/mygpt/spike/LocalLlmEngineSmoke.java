package dev.mygpt.spike;

import java.io.File;
import java.io.FileOutputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;

public final class LocalLlmEngineSmoke {
    private static final class FakeBackend implements SerializedLocalLlmEngine.Backend {
        final List<String> threads = new ArrayList<>();
        boolean cancelled;
        boolean destroyed;

        private void record() {
            threads.add(Thread.currentThread().getName());
        }

        @Override public void load(String modelPath) {
            record();
            if (modelPath == null || modelPath.isEmpty()) throw new AssertionError("model path");
        }

        @Override public void setSystemPrompt(String systemPrompt) {
            record();
            if (!systemPrompt.contains("MyGPT")) throw new AssertionError("system prompt");
        }

        @Override public void generate(
                String userPrompt, int predictLength, LocalLlmEngine.TokenSink sink) {
            record();
            sink.onToken("你");
            sink.onToken("");
            sink.onToken("好");
        }

        @Override public void cancelGeneration() {
            cancelled = true;
        }

        @Override public void unload() {
            record();
        }

        @Override public void destroy() {
            record();
            destroyed = true;
        }
    }

    public static void main(String[] args) throws Exception {
        File model = File.createTempFile("mygpt-llm-", ".gguf");
        try (FileOutputStream out = new FileOutputStream(model)) {
            out.write(new byte[] { 'G', 'G', 'U', 'F' });
        }

        FakeBackend backend = new FakeBackend();
        SerializedLocalLlmEngine engine = new SerializedLocalLlmEngine(backend);
        try {
            // Queueing is allowed; state checks execute in the serialized worker.
            engine.loadModel(model).get(2, TimeUnit.SECONDS);
            require(engine.state() == LocalLlmEngine.State.MODEL_READY, "model ready");

            engine.setSystemPrompt("You are MyGPT.").get(2, TimeUnit.SECONDS);
            StringBuilder output = new StringBuilder();
            engine.generate("你好", 64, output::append).get(2, TimeUnit.SECONDS);
            require("你好".contentEquals(output), "token stream");
            require(engine.state() == LocalLlmEngine.State.MODEL_READY, "ready after generation");

            engine.cancelGeneration();
            require(backend.cancelled, "cancel boundary");

            engine.unloadModel().get(2, TimeUnit.SECONDS);
            require(engine.state() == LocalLlmEngine.State.INITIALIZED, "unloaded");

            require(!backend.threads.isEmpty(), "backend threads captured");
            String worker = backend.threads.get(0);
            for (String name : backend.threads) {
                require(worker.equals(name), "all backend calls serialized on one worker");
            }
        } finally {
            engine.close();
            require(backend.destroyed, "backend destroy");
            require(engine.state() == LocalLlmEngine.State.DESTROYED, "destroyed state");
            model.delete();
        }

        FakeBackend failureBackend = new FakeBackend();
        SerializedLocalLlmEngine failing = new SerializedLocalLlmEngine(failureBackend);
        try {
            try {
                failing.loadModel(new File(model.getParentFile(), "does-not-exist.gguf"))
                        .get(2, TimeUnit.SECONDS);
                throw new AssertionError("missing model should fail");
            } catch (ExecutionException expected) {
                require(
                        failing.state() == LocalLlmEngine.State.ERROR,
                        "missing model enters error state");
            }
        } finally {
            failing.close();
        }

        System.out.println("LocalLlmEngineSmoke PASS");
    }

    private static void require(boolean value, String label) {
        if (!value) throw new AssertionError(label);
    }
}
