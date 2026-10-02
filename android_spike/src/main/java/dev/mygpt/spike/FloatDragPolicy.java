package dev.mygpt.spike;

/**
 * Permission-free in-app floating-position policy.
 *
 * The snap vocabulary and boundary-clamp behavior are adapted from EasyFloat's
 * Apache-2.0 TouchUtils/SidePattern implementation. Android touch plumbing is
 * kept separate so this class is host-JVM testable.
 */
public final class FloatDragPolicy {
    public enum SnapMode {
        NONE,
        LEFT,
        RIGHT,
        TOP,
        BOTTOM,
        HORIZONTAL,
        VERTICAL,
        NEAREST_SIDE
    }

    public static final class Bounds {
        public final int left;
        public final int top;
        public final int right;
        public final int bottom;

        public Bounds(int left, int top, int right, int bottom) {
            if (right < left || bottom < top) {
                throw new IllegalArgumentException("invalid drag bounds");
            }
            this.left = left;
            this.top = top;
            this.right = right;
            this.bottom = bottom;
        }
    }

    public static final class Position {
        public final int x;
        public final int y;

        public Position(int x, int y) {
            this.x = x;
            this.y = y;
        }
    }

    private FloatDragPolicy() {}

    public static Position clamp(int x, int y, Bounds bounds) {
        if (bounds == null) throw new IllegalArgumentException("bounds are required");
        return new Position(
                Math.max(bounds.left, Math.min(bounds.right, x)),
                Math.max(bounds.top, Math.min(bounds.bottom, y))
        );
    }

    public static Position move(Position current, int dx, int dy, Bounds bounds) {
        if (current == null) throw new IllegalArgumentException("current is required");
        return clamp(current.x + dx, current.y + dy, bounds);
    }

    public static Position snap(Position current, Bounds bounds, SnapMode mode) {
        if (current == null) throw new IllegalArgumentException("current is required");
        if (bounds == null) throw new IllegalArgumentException("bounds are required");
        if (mode == null) throw new IllegalArgumentException("mode is required");

        Position safe = clamp(current.x, current.y, bounds);
        int left = safe.x - bounds.left;
        int right = bounds.right - safe.x;
        int top = safe.y - bounds.top;
        int bottom = bounds.bottom - safe.y;

        switch (mode) {
            case LEFT:
                return new Position(bounds.left, safe.y);
            case RIGHT:
                return new Position(bounds.right, safe.y);
            case TOP:
                return new Position(safe.x, bounds.top);
            case BOTTOM:
                return new Position(safe.x, bounds.bottom);
            case HORIZONTAL:
                return new Position(left <= right ? bounds.left : bounds.right, safe.y);
            case VERTICAL:
                return new Position(safe.x, top <= bottom ? bounds.top : bounds.bottom);
            case NEAREST_SIDE:
                int minHorizontal = Math.min(left, right);
                int minVertical = Math.min(top, bottom);
                if (minHorizontal < minVertical) {
                    return new Position(left <= right ? bounds.left : bounds.right, safe.y);
                }
                return new Position(safe.x, top <= bottom ? bounds.top : bounds.bottom);
            case NONE:
            default:
                return safe;
        }
    }
}
