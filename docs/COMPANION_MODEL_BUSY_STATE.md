# Model busy-state unification

Companion V2 now uses `modelLoading` as the single busy flag for both:
- GGUF import/validation/copy; and
- llama unload/load/system-prompt transitions.

This closes a race where multiple document-picker results could start concurrent
large GGUF imports while the process-wide llama engine was being unloaded.

While the flag is true, Companion V2 refuses:
- another GGUF import;
- model reload;
- chat reset that reloads the model;
- benchmark start.

The flag is cleared on both import success/failure and load success/failure.
