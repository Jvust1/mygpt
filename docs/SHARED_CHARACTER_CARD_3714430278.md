# Shared 3714430278 Character Card

The authoritative MyGPT persona card remains:

`brain/personas/3714430278.json`

Both Python Brain and Android Companion V2 consume this same file.

Android build configuration adds `brain/personas` as an asset source directory,
so the APK packages `assets/3714430278.json` without maintaining a second copy.

Android validates:
- schema `mygpt.character-card.v1`;
- card id `mygpt-3714430278`;
- visual skin id `3714430278`;
- known field set and bounded text/list/example values.

The Android system prompt is built as:
1. the Character Card's identity/system/personality/scenario/consistency/examples;
2. Android-specific authority/freshness and AIRI ACT protocol rules.

This keeps personality content shared while allowing platform-specific security
rules to remain local to each runtime.
