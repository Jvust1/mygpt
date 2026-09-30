import { normalizeBookState } from "../adapters/book-state.js";

export function buildActivitySignal({ book = {}, screen = {}, userMessage = "", requestedTools = [] } = {}) {
  const b = normalizeBookState(book);
  const distraction = Number(screen.distractionScore);

  return {
    ...b,
    userMessage,
    requestedTools,
    app: screen.app ?? "Book",
    activity: {
      windowTitle: screen.windowTitle ?? null,
      category: screen.category ?? null,
    },
    focusDrift: Math.max(
      b.focusDrift,
      Number.isFinite(distraction) ? Math.max(0, Math.min(1, distraction)) : 0,
    ),
  };
}
