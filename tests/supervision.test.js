import test from "node:test";
import assert from "node:assert/strict";
import { SupervisionEngine } from "../src/supervision/engine.js";

test("defaults to companion when no task is active", () => {
  const result = new SupervisionEngine().evaluate({ taskActive: false });
  assert.equal(result.mode, "companion");
  assert.equal(result.score, 0);
});

test("escalates supervision when user is overdue, idle and drifting", () => {
  const result = new SupervisionEngine().evaluate({
    taskActive: true,
    overdueMinutes: 45,
    idleMinutes: 30,
    focusDrift: 1,
    missedCheckIns: 3,
  });
  assert.equal(result.mode, "focus");
  assert.ok(result.score >= 0.7);
});

test("completion returns to companionship", () => {
  const result = new SupervisionEngine().evaluate({
    taskActive: true,
    completed: true,
    overdueMinutes: 60,
  });
  assert.equal(result.mode, "companion");
  assert.equal(result.reason, "completed");
});
