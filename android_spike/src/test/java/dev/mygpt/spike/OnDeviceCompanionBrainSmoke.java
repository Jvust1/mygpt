package dev.mygpt.spike;

import java.io.File;
import java.io.FileOutputStream;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

public final class OnDeviceCompanionBrainSmoke {
    private static final class FakeBackend implements SerializedLocalLlmEngine.Backend {
        String systemPrompt;
        String userPrompt;
        boolean destroyed;

        @Override public void load(String modelPath) {}

        @Override public void setSystemPrompt(String prompt) {
            systemPrompt = prompt;
        }

        @Override public void generate(
                String prompt,
                int predictLength,
                LocalLlmEngine.TokenSink sink
        ) {
            userPrompt = prompt;
            sink.onToken("继续");
            sink.onToken("<|ACT:");
            sink.onToken("{\"emotion\":{\"name\":\"happy\",\"intensity\":0.75}}|>");
            sink.onToken("，我在。");
        }

        @Override public void cancelGeneration() {}
        @Override public void unload() {}
        @Override public void destroy() { destroyed = true; }
    }

    public static void main(String[] args) throws Exception {
        testActParser();
        testBrain();
        System.out.println("OnDeviceCompanionBrainSmoke PASS");
    }

    private static void testActParser() {
        AiriActEmotionParser.Result direct = AiriActEmotionParser.parse(
                "A<|ACT:{\"emotion\":\"sad\"}|>B"
        );
        require("AB".equals(direct.visibleText), "direct marker stripped");
        require(direct.emotion == PresentationEmotion.SAD, "direct emotion");
        require(direct.intensity == 1.0f, "direct intensity");

        AiriActEmotionParser.Result object = AiriActEmotionParser.parse(
                "x<|ACT : {\"emotion\":{\"name\":\"HAPPY\",\"intensity\":1.7}}|>y"
        );
        require("xy".equals(object.visibleText), "object marker stripped");
        require(object.emotion == PresentationEmotion.HAPPY, "object emotion");
        require(object.intensity == 1.0f, "intensity clamped");

        AiriActEmotionParser.Result unknown = AiriActEmotionParser.parse(
                "<|ACT:{\"emotion\":{\"name\":\"evil\",\"intensity\":0.2}}|>ok"
        );
        require("ok".equals(unknown.visibleText), "unknown marker still hidden");
        require(unknown.emotion == PresentationEmotion.NEUTRAL, "unknown fail-safe");
    }

    private static void testBrain() throws Exception {
        File model = File.createTempFile("mygpt-companion-", ".gguf");
        try (FileOutputStream out = new FileOutputStream(model)) {
            out.write(new byte[]{'G','G','U','F'});
        }

        FakeBackend backend = new FakeBackend();
        SerializedLocalLlmEngine engine = new SerializedLocalLlmEngine(backend);
        OnDeviceCompanionBrain brain = new OnDeviceCompanionBrain(
                engine,
                "你是 MyGPT，简洁、自然、尊重用户自主性。"
        );
        try {
            brain.initialize(model).get(2, TimeUnit.SECONDS);
            require(backend.systemPrompt.contains("Presentation control protocol"),
                    "control protocol in trusted system prompt");

            Future<OnDeviceCompanionBrain.Response> future =
                    brain.send("解释这一节", "泛函分析：教材上下文", 64);
            OnDeviceCompanionBrain.Response response = future.get(2, TimeUnit.SECONDS);
            require("继续，我在。".equals(response.text), "visible reply");
            require(response.emotion == PresentationEmotion.HAPPY, "emotion decoded");
            require(Math.abs(response.emotionIntensity - 0.75f) < 0.0001f,
                    "emotion intensity");
            require(backend.userPrompt.startsWith("[APPLICATION_CONTEXT_DATA"),
                    "book context is data boundary");
            require(backend.userPrompt.contains("[USER_MESSAGE]\n解释这一节"),
                    "user boundary");
        } finally {
            brain.close();
            require(backend.destroyed, "engine destroyed");
            model.delete();
        }
    }

    private static void require(boolean value, String label) {
        if (!value) throw new AssertionError(label);
    }
}
