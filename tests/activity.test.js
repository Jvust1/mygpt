import test from "node:test";
import assert from "node:assert/strict";
import { buildActivitySignal } from "../src/activity/signal-builder.js";

test("screen distraction can raise Book focus drift", () => {
  const signal = buildActivitySignal({
    book: { taskActive: true, currentTask: "泛函分析", focusDrift: 0.2 },
    screen: { app: "Browser", distractionScore: 0.8 },
  });

  assert.equal(signal.task, "泛函分析");
  assert.equal(signal.app, "Browser");
  assert.equal(signal.focusDrift, 0.8);
});
