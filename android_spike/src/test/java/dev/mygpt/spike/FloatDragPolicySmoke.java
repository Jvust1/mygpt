package dev.mygpt.spike;

public final class FloatDragPolicySmoke {
    public static void main(String[] args) {
        FloatDragPolicy.Bounds bounds = new FloatDragPolicy.Bounds(0, 10, 200, 300);

        FloatDragPolicy.Position moved = FloatDragPolicy.move(
                new FloatDragPolicy.Position(100, 100), 500, -500, bounds);
        require(moved.x == 200 && moved.y == 10, "clamp");

        FloatDragPolicy.Position left = FloatDragPolicy.snap(
                new FloatDragPolicy.Position(40, 150),
                bounds,
                FloatDragPolicy.SnapMode.HORIZONTAL);
        require(left.x == 0 && left.y == 150, "horizontal left");

        FloatDragPolicy.Position right = FloatDragPolicy.snap(
                new FloatDragPolicy.Position(180, 150),
                bounds,
                FloatDragPolicy.SnapMode.HORIZONTAL);
        require(right.x == 200 && right.y == 150, "horizontal right");

        FloatDragPolicy.Position nearestTop = FloatDragPolicy.snap(
                new FloatDragPolicy.Position(100, 20),
                bounds,
                FloatDragPolicy.SnapMode.NEAREST_SIDE);
        require(nearestTop.x == 100 && nearestTop.y == 10, "nearest top");

        FloatDragPolicy.Position tiePrefersVertical = FloatDragPolicy.snap(
                new FloatDragPolicy.Position(100, 155),
                new FloatDragPolicy.Bounds(0, 0, 200, 310),
                FloatDragPolicy.SnapMode.NEAREST_SIDE);
        require(tiePrefersVertical.x == 100 && tiePrefersVertical.y == 0,
                "tie determinism");

        System.out.println("FloatDragPolicySmoke PASS");
    }

    private static void require(boolean value, String label) {
        if (!value) throw new AssertionError(label);
    }
}
