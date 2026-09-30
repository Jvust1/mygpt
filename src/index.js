export { DEFAULT_PROFILE, validateProfile } from "./config/profile.js";
export { SupervisionEngine } from "./supervision/engine.js";
export { DotBrainBridge, normalizeDotResponse } from "./brain/dot-bridge.js";
export { InMemoryLiveSink, toLiveEvent } from "./live/protocol.js";
export { WebSocketLiveServer } from "./live/websocket-live-server.js";
export { normalizeBookState } from "./adapters/book-state.js";
export { buildActivitySignal } from "./activity/signal-builder.js";
export { CompanionRuntime } from "./runtime/companion-runtime.js";
export { startCompanionServer } from "./server.js";
