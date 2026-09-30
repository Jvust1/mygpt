import http from "node:http";
import { fileURLToPath } from "node:url";
import { CompanionRuntime } from "./runtime/companion-runtime.js";
import { WebSocketLiveServer } from "./live/websocket-live-server.js";
import { buildActivitySignal } from "./activity/signal-builder.js";

function json(res, status, body) {
  const data = JSON.stringify(body);
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(data),
  });
  res.end(data);
}

async function readJson(req, maxBytes = 1024 * 1024) {
  let size = 0;
  const chunks = [];
  for await (const chunk of req) {
    size += chunk.length;
    if (size > maxBytes) throw Object.assign(new Error("request too large"), { statusCode: 413 });
    chunks.push(chunk);
  }
  if (!chunks.length) return {};
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

export async function startCompanionServer({
  httpPort = Number(process.env.MYGPT_HTTP_PORT || 8787),
  livePort = Number(process.env.MYGPT_LIVE_PORT || 8765),
  host = process.env.MYGPT_HOST || "127.0.0.1",
} = {}) {
  const live = new WebSocketLiveServer({ port: livePort, host });
  await live.start();
  const runtime = new CompanionRuntime({ live });

  const server = http.createServer(async (req, res) => {
    try {
      if (req.method === "GET" && req.url === "/health") {
        return json(res, 200, {
          ok: true,
          service: "mygpt",
          dotBridge: "indirect",
          liveWebSocket: `ws://${host}:${livePort}`,
          policy: { supervision: 0.7, companionship: 0.3 },
        });
      }

      if (req.method === "POST" && req.url === "/signal") {
        const body = await readJson(req);
        const signal = buildActivitySignal(body);
        const result = await runtime.handle(signal);
        return json(res, 202, {
          state: result.state,
          dotRequestId: result.request.id,
          directive: result.directive,
        });
      }

      if (req.method === "POST" && req.url === "/live/idle") {
        await live.setIdle();
        return json(res, 200, { ok: true });
      }

      return json(res, 404, { error: "not_found" });
    } catch (error) {
      return json(res, error.statusCode || 400, {
        error: error.name || "Error",
        message: error.message,
      });
    }
  });

  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(httpPort, host, resolve);
  });

  return {
    server,
    live,
    runtime,
    httpUrl: `http://${host}:${httpPort}`,
    liveUrl: `ws://${host}:${livePort}`,
    async stop() {
      await new Promise((resolve) => server.close(resolve));
      await live.stop();
    },
  };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const running = await startCompanionServer();
  console.log(`mygpt HTTP: ${running.httpUrl}`);
  console.log(`Live bridge: ${running.liveUrl}`);
}
