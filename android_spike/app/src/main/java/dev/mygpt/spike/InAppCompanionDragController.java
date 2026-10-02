package dev.mygpt.spike;

import android.view.MotionEvent;
import android.view.View;
import android.view.ViewConfiguration;

/**
 * Current-Activity-only draggable companion surface.
 *
 * This controller never creates a system WindowManager overlay and therefore
 * does not request SYSTEM_ALERT_WINDOW. It is intended for a future mini
 * companion view inside MyGPT's own activity.
 */
final class InAppCompanionDragController implements View.OnTouchListener {
    private final View floatingView;
    private final View parentView;
    private final FloatDragPolicy.SnapMode snapMode;
    private final int touchSlopSquared;

    private float lastRawX;
    private float lastRawY;
    private float downRawX;
    private float downRawY;
    private boolean dragging;

    InAppCompanionDragController(
            View floatingView,
            View parentView,
            FloatDragPolicy.SnapMode snapMode
    ) {
        if (floatingView == null || parentView == null || snapMode == null) {
            throw new IllegalArgumentException("view, parent and snapMode are required");
        }
        this.floatingView = floatingView;
        this.parentView = parentView;
        this.snapMode = snapMode;
        int slop = ViewConfiguration.get(floatingView.getContext()).getScaledTouchSlop();
        this.touchSlopSquared = slop * slop;
    }

    static InAppCompanionDragController attach(
            View floatingView,
            View parentView,
            FloatDragPolicy.SnapMode snapMode
    ) {
        InAppCompanionDragController controller =
                new InAppCompanionDragController(floatingView, parentView, snapMode);
        floatingView.setOnTouchListener(controller);
        return controller;
    }

    @Override
    public boolean onTouch(View view, MotionEvent event) {
        switch (event.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
                dragging = false;
                downRawX = lastRawX = event.getRawX();
                downRawY = lastRawY = event.getRawY();
                return true;

            case MotionEvent.ACTION_MOVE:
                float totalDx = event.getRawX() - downRawX;
                float totalDy = event.getRawY() - downRawY;
                if (!dragging
                        && totalDx * totalDx + totalDy * totalDy < touchSlopSquared) {
                    return true;
                }
                dragging = true;
                moveBy(
                        Math.round(event.getRawX() - lastRawX),
                        Math.round(event.getRawY() - lastRawY)
                );
                lastRawX = event.getRawX();
                lastRawY = event.getRawY();
                return true;

            case MotionEvent.ACTION_UP:
                if (!dragging) {
                    view.performClick();
                } else {
                    snapToEdge();
                }
                dragging = false;
                return true;

            case MotionEvent.ACTION_CANCEL:
                if (dragging) snapToEdge();
                dragging = false;
                return true;

            default:
                return false;
        }
    }

    private FloatDragPolicy.Bounds currentBounds() {
        int maxX = Math.max(0, parentView.getWidth() - floatingView.getWidth());
        int maxY = Math.max(0, parentView.getHeight() - floatingView.getHeight());
        return new FloatDragPolicy.Bounds(0, 0, maxX, maxY);
    }

    private void moveBy(int dx, int dy) {
        FloatDragPolicy.Position next = FloatDragPolicy.move(
                new FloatDragPolicy.Position(
                        Math.round(floatingView.getX()),
                        Math.round(floatingView.getY())
                ),
                dx,
                dy,
                currentBounds()
        );
        floatingView.setX(next.x);
        floatingView.setY(next.y);
    }

    private void snapToEdge() {
        FloatDragPolicy.Position target = FloatDragPolicy.snap(
                new FloatDragPolicy.Position(
                        Math.round(floatingView.getX()),
                        Math.round(floatingView.getY())
                ),
                currentBounds(),
                snapMode
        );
        floatingView.animate()
                .x(target.x)
                .y(target.y)
                .setDuration(180L)
                .start();
    }
}
