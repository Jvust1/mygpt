import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import path from "node:path";

function safeId(value) {
  if (!/^[a-zA-Z0-9._-]+$/.test(value)) throw new Error("unsafe request id");
  return value;
}

/**
 * Indirect bridge for OpenAI Dot.
 *
 * This deliberately does not assume a private/public Dot HTTP API.
 * mygpt writes structured requests to an inbox. A Dot-side/local agent bridge
 * can consume them and write structured responses to the outbox.
 */
export class DotBrainBridge {
  constructor({ rootDir = "runtime-spool/dot", actor = "mygpt" } = {}) {
    this.rootDir = rootDir;
    this.inboxDir = path.join(rootDir, "inbox");
    this.outboxDir = path.join(rootDir, "outbox");
    this.actor = actor;
  }

  async init() {
    await Promise.all([
      mkdir(this.inboxDir, { recursive: true }),
      mkdir(this.outboxDir, { recursive: true }),
    ]);
  }

  async submit({ userMessage = "", supervision, context = {}, requestedTools = [] } = {}) {
    await this.init();
    const id = randomUUID();
    const request = {
      protocol: "mygpt.dot.bridge.v1",
      id,
      createdAt: new Date().toISOString(),
      actor: this.actor,
      role: "brain-request",
      policy: {
        supervisionWeight: 0.7,
        companionshipWeight: 0.3,
      },
      supervision,
      userMessage,
      context,
      requestedTools,
      expectedResponse: {
        text: "string",
        intent: "supervise|companion|tool|clarify",
        emotion: "string",
        motion: "string|null",
        nextCheckInMinutes: "number|null",
        toolCalls: "array",
      },
    };

    const finalPath = path.join(this.inboxDir, `${safeId(id)}.json`);
    const tempPath = `${finalPath}.tmp`;
    await writeFile(tempPath, JSON.stringify(request, null, 2), "utf8");
    await rename(tempPath, finalPath);
    return request;
  }

  async readResponse(id) {
    safeId(id);
    try {
      const content = await readFile(path.join(this.outboxDir, `${id}.json`), "utf8");
      const response = JSON.parse(content);
      if (response.requestId !== id) throw new Error("Dot response requestId mismatch");
      return response;
    } catch (error) {
      if (error?.code === "ENOENT") return null;
      throw error;
    }
  }
}

export function normalizeDotResponse(response, fallback) {
  if (!response) return fallback;
  return {
    text: typeof response.text === "string" && response.text.trim()
      ? response.text.trim()
      : fallback.text,
    intent: response.intent ?? fallback.intent,
    emotion: response.emotion ?? fallback.emotion,
    motion: response.motion ?? fallback.motion ?? null,
    nextCheckInMinutes: Number.isFinite(response.nextCheckInMinutes)
      ? response.nextCheckInMinutes
      : fallback.nextCheckInMinutes,
    toolCalls: Array.isArray(response.toolCalls) ? response.toolCalls : [],
  };
}
