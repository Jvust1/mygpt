# Companion V2 model lifecycle epochs

Companion V2 now separates two independent concurrency guards:

- `modelLoading` — only one llama unload/load/system-prompt transition may run.
- `generationEpoch` — every user generation owns an epoch; any lifecycle
  action that invalidates that generation increments the epoch.

Why:

The upstream llama Android engine is process-wide and serialized. Coroutine
cancellation can finish asynchronously. Without an epoch, an old cancelled
generation callback could run after a newer model reload and incorrectly flip
`modelLoaded/modelNeedsRecovery` or re-enable controls.

Rules:

1. starting a generation increments and captures `generationEpoch`;
2. onSuccess/onFailure mutate UI/model state only if their captured epoch is
   still current;
3. leaving the Activity during a generation increments the epoch before
   cancelling the Job and marks the native session for recovery;
4. model import/load and Activity destruction also invalidate older generation
   epochs;
5. model import, reload, chat reset, and benchmark refuse to start while
   `modelLoading` is true.

This does not add parallel llama execution; it prevents stale coroutine
callbacks from corrupting the serialized singleton lifecycle.
