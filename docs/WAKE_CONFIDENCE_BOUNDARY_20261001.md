# Quiet-first wake confidence boundary

Base: [PR #54](https://github.com/Jvust1/mygpt/pull/54),
`516ccebd4165dc77df0db6fd6dc71078e7cc91d3`.

## Existing path, not a new upstream adoption

The pre-existing optional wake adapter accepted positive infinity as confidence.
A production `VoiceActivationRuntime` repro with that backend result invoked ASR,
invoked the companion responder and created three history rows. Invalid model
data should not grant admission to that path.

This patch hardens existing application code only. No wake SDK/source/model is
imported, installed or downloaded. The existing openWakeWord source reference
remains `368c03716d1e92591906a84949bc477f3a834455`. Its repository had 2,803 stars
when checked on 2026-10-01, below the current new-adoption threshold; this work
is explicitly not counted as another qualifying upstream integration.

## Confidence contract

Predictions must be real numeric scalars with finite values in `[0, 1]`.
Booleans, numeric strings, bytes, arrays, other non-real values, NaN/infinity,
out-of-range numbers and unrepresentable numeric conversions do not compete
for the best label or start a wake. Values are not clamped into a trigger.
Original scalar bounds are checked before lossy float conversion; a Fraction or
extended-precision value above one must not be rounded into a valid confidence.

Python's standard `Real` interface admits NumPy numeric scalars without a new
runtime dependency. The [pinned upstream's `Model.predict`](https://github.com/dscripka/openWakeWord/blob/368c03716d1e92591906a84949bc477f3a834455/openwakeword/model.py#L314-L328) selects scalar array
elements (or scalar verifier probabilities) for its result mapping. An offline
test uses already-installed NumPy to verify float16/32/64 and integer confidence,
while rejecting NumPy booleans, arrays and invalid values. That test is required
by the existing optional gate; it does not execute a wake model.

Threshold equality, best-valid-candidate ordering, tie behavior, cooldown frame
countdown and reset behavior remain. Empty/invalid score maps stay quiet. A
wrong outer mapping type or backend `predict` exception still raises as before;
unexpected errors converting an otherwise-real scalar also propagate.

## Evidence and limits

Core tests cover invalid/high-precision values, exact/adjacent threshold values, mixed readonly
maps, cooldown/reset and backend exceptions. Two actual composition stories show
that invalid confidence never invokes injected ASR/responder, writes a receipt
or history, creates memory, or supersedes an existing valid in-flight turn.
A subsequent valid wake still completes normally through SQLite.

The audio/model inputs are synthetic and already buffered by the test caller.
No microphone permission, real wake model/recognition accuracy or device/audio
acceptance is established. Existing qualified AIRI/Pipecat/Ollama/sklearn/Gson
source pins/licenses and the production dependency lock are unchanged.
