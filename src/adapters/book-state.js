export function normalizeBookState(input = {}) {
  const progress = Number(input.progress);
  const focusDrift = Number(input.focusDrift);
  const overdueMinutes = Number(input.overdueMinutes);
  const idleMinutes = Number(input.idleMinutes);

  return {
    source: "book",
    taskActive: Boolean(input.taskActive ?? input.currentTask),
    task: input.currentTask ?? input.task ?? null,
    chapter: input.chapter ?? null,
    section: input.section ?? null,
    progress: Number.isFinite(progress) ? Math.max(0, Math.min(1, progress)) : null,
    completed: Boolean(input.completed),
    overdueMinutes: Number.isFinite(overdueMinutes) ? Math.max(0, overdueMinutes) : 0,
    idleMinutes: Number.isFinite(idleMinutes) ? Math.max(0, idleMinutes) : 0,
    focusDrift: Number.isFinite(focusDrift) ? Math.max(0, Math.min(1, focusDrift)) : 0,
    missedCheckIns: Math.max(0, Number(input.missedCheckIns) || 0),
    onApprovedBreak: Boolean(input.onApprovedBreak),
  };
}
