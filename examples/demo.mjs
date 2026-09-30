import { CompanionRuntime, InMemoryLiveSink } from "../src/index.js";

const live = new InMemoryLiveSink();
const runtime = new CompanionRuntime({ live });

const result = await runtime.handle({
  taskActive: true,
  task: "复习泛函分析",
  overdueMinutes: 18,
  idleMinutes: 12,
  focusDrift: 0.55,
  missedCheckIns: 1,
  userMessage: "我有点想刷别的东西。",
  app: "Book",
});

console.log(JSON.stringify(result.event, null, 2));
