import { WebSocketServer, WebSocket } from "ws";

function bridgeFrames(event) {
  const payload = event.payload ?? {};
  const frames = [
    { type: "status", value: "speaking" },
    { type: "emotion", value: payload.emotion || "neutral" },
    { type: "text", content: payload.text || "", streaming: false },
  ];

  if (payload.expression) {
    frames.splice(2, 0, { type: "expression", name: payload.expression });
  }
  return frames;
}

export class WebSocketLiveServer {
  constructor({ port = 8765, host = "127.0.0.1" } = {}) {
    this.port = port;
    this.host = host;
    this.wss = null;
  }

  async start() {
    if (this.wss) return this;
    this.wss = new WebSocketServer({ port: this.port, host: this.host });
    await new Promise((resolve, reject) => {
      this.wss.once("listening", resolve);
      this.wss.once("error", reject);
    });
    return this;
  }

  async stop() {
    if (!this.wss) return;
    const server = this.wss;
    this.wss = null;
    await new Promise((resolve) => server.close(resolve));
  }

  async emit(event) {
    if (!this.wss) throw new Error("Live WebSocket server is not started");
    const frames = bridgeFrames(event);
    for (const client of this.wss.clients) {
      if (client.readyState !== WebSocket.OPEN) continue;
      for (const frame of frames) {
        client.send(JSON.stringify(frame));
      }
    }
    return event;
  }

  async setIdle() {
    if (!this.wss) return;
    const frame = JSON.stringify({ type: "status", value: "idle" });
    for (const client of this.wss.clients) {
      if (client.readyState === WebSocket.OPEN) client.send(frame);
    }
  }
}
