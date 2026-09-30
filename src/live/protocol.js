const ALLOWED_MODES = new Set(["companion", "light", "firm", "focus"]);

export function toLiveEvent({ text, emotion, motion = null, mode = "companion", priority, metadata = {} }) {
  if (!ALLOWED_MODES.has(mode)) throw new Error(`unsupported companion mode: ${mode}`);
  if (!text || typeof text !== "string") throw new TypeError("Live event text is required");

  return {
    protocol: "mygpt.live.v1",
    type: "companion.message",
    timestamp: new Date().toISOString(),
    payload: {
      text,
      emotion: emotion || "neutral",
      motion,
      mode,
      priority: priority ?? (mode === "focus" ? 90 : mode === "firm" ? 70 : mode === "light" ? 45 : 20),
      metadata,
    },
  };
}

export class InMemoryLiveSink {
  events = [];
  async emit(event) {
    this.events.push(event);
    return event;
  }
}
