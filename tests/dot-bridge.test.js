import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { DotBrainBridge } from "../src/brain/dot-bridge.js";

test("writes a Dot request and reads the matching response", async () => {
  const rootDir = await mkdtemp(path.join(os.tmpdir(), "mygpt-dot-"));
  const bridge = new DotBrainBridge({ rootDir });

  try {
    const request = await bridge.submit({
      userMessage: "继续学习",
      supervision: { mode: "light", score: 0.3 },
    });

    const stored = JSON.parse(
      await readFile(path.join(rootDir, "inbox", `${request.id}.json`), "utf8"),
    );
    assert.equal(stored.protocol, "mygpt.dot.bridge.v1");

    await writeFile(
      path.join(rootDir, "outbox", `${request.id}.json`),
      JSON.stringify({ requestId: request.id, text: "继续当前任务。", intent: "supervise" }),
      "utf8",
    );

    const response = await bridge.readResponse(request.id);
    assert.equal(response.text, "继续当前任务。");
  } finally {
    await rm(rootDir, { recursive: true, force: true });
  }
});
