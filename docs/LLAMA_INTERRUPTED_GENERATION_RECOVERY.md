# llama.cpp interrupted-generation recovery

The pinned llama.cpp Android Flow sets ModelReady when coroutine collection is
cancelled, but a cancellation may occur after the current user prompt and some
partial generated tokens have already entered native KV state. The assistant
message is not committed to upstream chat history until generation completes.

Companion V2 therefore treats an interrupted/native-failed generation as a
potentially inconsistent native session:

- the interrupted exchange is not written to LocalConversationStore;
- modelLoaded becomes false;
- conversationPrimed becomes false;
- modelNeedsRecovery becomes true;
- returning to foreground triggers the existing unload -> load -> system-prompt
  path;
- the next successful turn can prime only completed visible conversation from
  LocalConversationStore.

Pre-JNI validation failures (for example prompt budget/user-length rejection) do
not mark the native model dirty.

This keeps persistent visible conversation separate from transient native KV and
avoids carrying a half-generated answer into later turns.
