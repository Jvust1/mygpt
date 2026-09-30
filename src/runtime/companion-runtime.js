import { SupervisionEngine } from "../supervision/engine.js";
import { DotBrainBridge, normalizeDotResponse } from "../brain/dot-bridge.js";
import { InMemoryLiveSink, toLiveEvent } from "../live/protocol.js";

function fallbackDirective(state, signal) {
  if (signal.completed) {
    return {
      text: "完成了。先记下成果，接下来可以轻松一点。",
      intent: "companion",
      emotion: "happy",
      motion: "celebrate",
      nextCheckInMinutes: null,
    };
  }

  if (state.mode === "focus") {
    return {
      text: "现在偏离目标比较明显。先只做当前最重要的一步，完成后再切换。",
      intent: "supervise",
      emotion: "focused",
      motion: "attention",
      nextCheckInMinutes: 10,
    };
  }

  if (state.mode === "firm") {
    return {
      text: "该把注意力拉回来了。继续当前任务，不要再开新的支线。",
      intent: "supervise",
      emotion: "focused",
      motion: "nudge",
      nextCheckInMinutes: 15,
    };
  }

  if (state.mode === "light") {
    return {
      text: "提醒一下：当前任务还在进行，继续推进就好。",
      intent: "supervise",
      emotion: "neutral",
      motion: "notice",
      nextCheckInMinutes: 25,
    };
  }

  return {
    text: signal.userMessage || "我在。你继续做，我会在需要时提醒你。",
    intent: "companion",
    emotion: "neutral",
    motion: null,
    nextCheckInMinutes: 25,
  };
}

export class CompanionRuntime {
  constructor({
    supervision = new SupervisionEngine(),
    brain = new DotBrainBridge(),
    live = new InMemoryLiveSink(),
  } = {}) {
    this.supervision = supervision;
    this.brain = brain;
    this.live = live;
  }

  async handle(signal = {}) {
    const state = this.supervision.evaluate(signal);
    const request = await this.brain.submit({
      userMessage: signal.userMessage,
      supervision: state,
      context: {
        task: signal.task ?? null,
        app: signal.app ?? null,
        activity: signal.activity ?? null,
      },
      requestedTools: signal.requestedTools ?? [],
    });

    const fallback = fallbackDirective(state, signal);
    const response = await this.brain.readResponse(request.id);
    const directive = normalizeDotResponse(response, fallback);

    const event = toLiveEvent({
      ...directive,
      mode: state.mode,
      metadata: {
        dotRequestId: request.id,
        supervisionScore: state.score,
        reason: state.reason,
        brainSource: response ? "dot" : "local-fallback",
      },
    });

    await this.live.emit(event);
    return { state, request, directive, event };
  }
}
