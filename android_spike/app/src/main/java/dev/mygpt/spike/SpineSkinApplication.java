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
import com.esotericsoftware.spine.AnimationState.AnimationStateAdapter;
import com.esotericsoftware.spine.AnimationState.TrackEntry;
import com.esotericsoftware.spine.AnimationStateData;
import com.esotericsoftware.spine.Skeleton;
import com.esotericsoftware.spine.SkeletonBinary;
import com.esotericsoftware.spine.SkeletonData;
import com.esotericsoftware.spine.SkeletonRenderer;
import com.esotericsoftware.spine.utils.TwoColorPolygonBatch;

import java.io.File;

/** Multi-form Spine 4.1 renderer for Live skin 3714430278. Audio is intentionally unsupported. */
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
    private File skinDirectory;
    private File pendingDirectory;
    private volatile SkinCapabilityCatalog.Form currentForm = SkinCapabilityCatalog.Form.DEFAULT;
    private SkinCapabilityCatalog.Form pendingForm = SkinCapabilityCatalog.Form.DEFAULT;
    private CompanionCoordinator.Cue pendingCue = CompanionCoordinator.Cue.QUIET;
    private long actionGeneration;
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
        if (pendingDirectory != null) loadFormNow(pendingDirectory, pendingForm, true);
    }

    public void requestLoad(File directory) {
        pendingDirectory = directory;
        pendingForm = SkinCapabilityCatalog.Form.DEFAULT;
        if (Gdx.app != null) {
            Gdx.app.postRunnable(() -> loadFormNow(directory, SkinCapabilityCatalog.Form.DEFAULT, true));
        }
    }

    public void requestForm(SkinCapabilityCatalog.Form form) {
        if (form == null) return;
        pendingForm = form;
        if (Gdx.app != null) Gdx.app.postRunnable(() -> transitionToNow(form));
    }

    public void requestAnimation(String animation) {
        if (animation == null) return;
        if (Gdx.app != null) Gdx.app.postRunnable(() -> playRequestedAnimationNow(animation));
    }

    public SkinCapabilityCatalog.Form currentForm() {
        return currentForm;
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

    private void transitionToNow(SkinCapabilityCatalog.Form target) {
        if (skinDirectory == null) {
            pendingForm = target;
            return;
        }
        if (currentForm == target) {
            playLoop(SkinCapabilityCatalog.idle(target));
            report("已在 " + formLabel(target) + " 形态");
            return;
        }

        String authored = SkinCapabilityCatalog.authoredTransition(currentForm, target);
        if (authored != null && data != null && data.findAnimation(authored) != null) {
            final SkinCapabilityCatalog.Form from = currentForm;
            final long token = ++actionGeneration;
            animationState.setTimeScale(1f);
            TrackEntry entry = animationState.setAnimation(0, authored, false);
            entry.setListener(new AnimationStateAdapter() {
                @Override public void complete(TrackEntry completed) {
                    if (token != actionGeneration || Gdx.app == null) return;
                    Gdx.app.postRunnable(() -> {
                        if (token == actionGeneration && currentForm == from) {
                            loadFormNow(skinDirectory, target, true);
                        }
                    });
                }
            });
            report(formLabel(from) + " → " + formLabel(target) + " · " + authored);
            return;
        }

        ++actionGeneration;
        loadFormNow(skinDirectory, target, true);
    }

    private void loadFormNow(File directory, SkinCapabilityCatalog.Form form, boolean announce) {
        try {
            ++actionGeneration;
            disposeSkin();
            skinDirectory = directory;
            pendingDirectory = directory;
            pendingForm = form;

            File atlasFile = new File(directory, SkinCapabilityCatalog.atlas(form));
            File skeletonFile = new File(directory, SkinCapabilityCatalog.skeleton(form));
            atlas = new TextureAtlas(new FileHandle(atlasFile));

            SkeletonBinary binary = new SkeletonBinary(atlas);
            binary.setScale(1f);
            data = binary.readSkeletonData(new FileHandle(skeletonFile));
            if (data.getVersion() == null || !data.getVersion().startsWith("4.1.")) {
                throw new IllegalStateException("Spine runtime/data mismatch: " + data.getVersion());
            }

            skeleton = new Skeleton(data);
            skeleton.updateWorldTransform();
            animationState = new AnimationState(new AnimationStateData(data));
            currentForm = form;
            playLoop(SkinCapabilityCatalog.idle(form));
            applyCue(pendingCue);
            fitCamera();
            if (announce) {
                report("3714430278 · " + formLabel(form) + " · Spine " + data.getVersion());
            }
        } catch (Throwable error) {
            disposeSkin();
            report(formLabel(form) + " 加载失败：" + error.getClass().getSimpleName()
                    + " · " + safeMessage(error));
        }
    }

    private void playRequestedAnimationNow(String animation) {
        if ("to_cover".equals(animation) && currentForm == SkinCapabilityCatalog.Form.AIM) {
            transitionToNow(SkinCapabilityCatalog.Form.COVER);
            return;
        }
        if ("to_aim".equals(animation) && currentForm == SkinCapabilityCatalog.Form.COVER) {
            transitionToNow(SkinCapabilityCatalog.Form.AIM);
            return;
        }
        playOneShot(animation);
    }

    private void playOneShot(String animation) {
        if (animationState == null || data == null) return;
        if (data.findAnimation(animation) == null) {
            report(formLabel(currentForm) + " 不含动作 · " + animation);
            return;
        }

        final SkinCapabilityCatalog.Form formAtStart = currentForm;
        final long token = ++actionGeneration;
        animationState.setTimeScale(1f);
        TrackEntry entry = animationState.setAnimation(0, animation, false);
        entry.setListener(new AnimationStateAdapter() {
            @Override public void complete(TrackEntry completed) {
                if (token != actionGeneration || Gdx.app == null) return;
                Gdx.app.postRunnable(() -> {
                    if (token == actionGeneration && currentForm == formAtStart) {
                        playLoop(SkinCapabilityCatalog.idle(formAtStart));
                    }
                });
            }
        });
        report(formLabel(currentForm) + " · " + animation);
    }

    private void playLoop(String animation) {
        if (animationState == null || data == null) return;
        String selected = animation;
        if (data.findAnimation(selected) == null) {
            selected = SkinCapabilityCatalog.idle(currentForm);
        }
        if (data.findAnimation(selected) != null) {
            ++actionGeneration;
            animationState.setAnimation(0, selected, true);
        }
    }

    private void applyCue(CompanionCoordinator.Cue cue) {
        if (animationState == null || data == null) return;
        if (cue == CompanionCoordinator.Cue.PAUSED) {
            animationState.setTimeScale(0f);
            return;
        }

        animationState.setTimeScale(1f);
        switch (cue) {
            case NEEDS_INPUT:
                playOneShot(SkinCapabilityCatalog.reaction(currentForm));
                break;
            case GENTLE_CHECK_IN:
                playOneShot(SkinCapabilityCatalog.primaryAction(currentForm));
                break;
            default:
                playLoop(SkinCapabilityCatalog.idle(currentForm));
                break;
        }
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

    private static String formLabel(SkinCapabilityCatalog.Form form) {
        switch (form) {
            case AIM: return "AIM";
            case COVER: return "COVER";
            default: return "DEFAULT";
        }
    }

    private void report(String value) {
        if (listener != null) listener.onRendererState(value);
    }

    private static String safeMessage(Throwable error) {
        String message = error.getMessage();
        return message == null ? "无详细信息" : message;
    }
}
