package dev.mygpt.spike;

import com.badlogic.gdx.ApplicationAdapter;
import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.files.FileHandle;
import com.badlogic.gdx.graphics.GL20;
import com.badlogic.gdx.graphics.OrthographicCamera;
import com.badlogic.gdx.graphics.g2d.TextureAtlas;
import com.badlogic.gdx.math.Vector2;
import com.badlogic.gdx.utils.FloatArray;
import com.esotericsoftware.spine.AnimationState;
import com.esotericsoftware.spine.AnimationStateData;
import com.esotericsoftware.spine.Skeleton;
import com.esotericsoftware.spine.SkeletonBinary;
import com.esotericsoftware.spine.SkeletonData;
import com.esotericsoftware.spine.SkeletonRenderer;
import com.esotericsoftware.spine.utils.TwoColorPolygonBatch;

import java.io.File;

/** Private evaluation renderer for the decrypted Spine 4.1 skin package. */
public final class SpineSkinApplication extends ApplicationAdapter {
    public interface Listener { void onRendererState(String state); }

    private final Listener listener;
    private OrthographicCamera camera;
    private TwoColorPolygonBatch batch;
    private SkeletonRenderer renderer;
    private TextureAtlas atlas;
    private Skeleton skeleton;
    private SkeletonData data;
    private AnimationState animationState;
    private File pendingDirectory;
    private CompanionCoordinator.Cue pendingCue = CompanionCoordinator.Cue.QUIET;
    private int viewWidth = 1;
    private int viewHeight = 1;

    public SpineSkinApplication(Listener listener) {
        this.listener = listener;
    }

    @Override public void create() {
        camera = new OrthographicCamera();
        batch = new TwoColorPolygonBatch();
        renderer = new SkeletonRenderer();
        renderer.setPremultipliedAlpha(true);
        if (pendingDirectory != null) loadNow(pendingDirectory);
    }

    public void requestLoad(File directory) {
        pendingDirectory = directory;
        if (Gdx.app != null) Gdx.app.postRunnable(() -> loadNow(directory));
    }

    public void requestCue(CompanionCoordinator.Cue cue) {
        pendingCue = cue;
        if (Gdx.app != null) Gdx.app.postRunnable(() -> applyCue(cue));
    }

    @Override public void resize(int width, int height) {
        viewWidth = Math.max(1, width);
        viewHeight = Math.max(1, height);
        fitCamera();
    }

    @Override public void render() {
        Gdx.gl.glClearColor(239f / 255f, 243f / 255f, 238f / 255f, 1f);
        Gdx.gl.glClear(GL20.GL_COLOR_BUFFER_BIT);
        if (skeleton == null || animationState == null) return;

        animationState.update(Gdx.graphics.getDeltaTime());
        animationState.apply(skeleton);
        skeleton.updateWorldTransform();

        camera.update();
        batch.getProjectionMatrix().set(camera.combined);
        batch.begin();
        renderer.draw(batch, skeleton);
        batch.end();
    }

    private void loadNow(File directory) {
        try {
            disposeSkin();
            File atlasFile = new File(directory, "c610_00.atlas");
            File skeletonFile = new File(directory, "skeleton.bin");
            atlas = new TextureAtlas(new FileHandle(atlasFile));
            SkeletonBinary binary = new SkeletonBinary(atlas);
            binary.setScale(1f);
            data = binary.readSkeletonData(new FileHandle(skeletonFile));
            if (data.getVersion() == null || !data.getVersion().startsWith("4.1."))
                throw new IllegalStateException("Spine runtime/data mismatch: " + data.getVersion());

            skeleton = new Skeleton(data);
            skeleton.updateWorldTransform();
            animationState = new AnimationState(new AnimationStateData(data));
            applyCue(pendingCue);
            fitCamera();
            report("皮肤 3714430278 已加载 · Spine " + data.getVersion());
        } catch (Throwable error) {
            disposeSkin();
            report("皮肤加载失败：" + error.getClass().getSimpleName() + " · " + safeMessage(error));
        }
    }

    private void applyCue(CompanionCoordinator.Cue cue) {
        if (animationState == null || data == null) return;
        if (cue == CompanionCoordinator.Cue.PAUSED) {
            animationState.setTimeScale(0f);
            return;
        }
        animationState.setTimeScale(1f);
        String preferred;
        switch (cue) {
            case NEEDS_INPUT: preferred = "smile"; break;
            case GENTLE_CHECK_IN: preferred = "action"; break;
            default: preferred = "idle";
        }
        if (data.findAnimation(preferred) == null) preferred = "idle";
        if (data.findAnimation(preferred) != null) animationState.setAnimation(0, preferred, true);
    }

    private void fitCamera() {
        if (camera == null) return;
        camera.setToOrtho(false, viewWidth, viewHeight);
        if (skeleton == null) {
            camera.update();
            return;
        }
        Vector2 offset = new Vector2();
        Vector2 size = new Vector2();
        skeleton.updateWorldTransform();
        skeleton.getBounds(offset, size, new FloatArray());
        float width = size.x > 1f ? size.x : Math.max(1f, data.getWidth());
        float height = size.y > 1f ? size.y : Math.max(1f, data.getHeight());
        float centerX = size.x > 1f ? offset.x + size.x / 2f : data.getX() + width / 2f;
        float centerY = size.y > 1f ? offset.y + size.y / 2f : data.getY() + height / 2f;
        float zoom = Math.max(width / viewWidth, height / viewHeight) * 1.10f;
        camera.zoom = Math.max(0.01f, zoom);
        camera.position.set(centerX, centerY, 0f);
        camera.update();
    }

    private void disposeSkin() {
        if (atlas != null) {
            atlas.dispose();
            atlas = null;
        }
        skeleton = null;
        data = null;
        animationState = null;
    }

    @Override public void dispose() {
        disposeSkin();
        if (batch != null) batch.dispose();
    }

    private void report(String value) {
        if (listener != null) listener.onRendererState(value);
    }

    private static String safeMessage(Throwable error) {
        String message = error.getMessage();
        return message == null ? "无详细信息" : message;
    }
}
