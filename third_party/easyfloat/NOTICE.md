# EasyFloat attribution

Upstream: https://github.com/princekin-f/EasyFloat  
Pinned upstream commit: `1a65226084a46cafc7ebcb27f0a077aebefa9b0e`  
License: Apache-2.0 (Copyright 2019 Liu Zhenfeng)

MyGPT directly adapts the in-app drag/snap concepts from:

- `easyfloat/src/main/java/com/lzf/easyfloat/core/TouchUtils.kt`
- `easyfloat/src/main/java/com/lzf/easyfloat/enums/SidePattern.kt`

Local derived/modified files:

- `android_spike/src/main/java/dev/mygpt/spike/FloatDragPolicy.java`
- `android_spike/app/src/main/java/dev/mygpt/spike/InAppCompanionDragController.java`

Material changes in MyGPT:

- only the permission-free current-activity drag/snap behavior is adopted;
- the system overlay manager and automatic overlay permission request are not copied;
- the policy is split into pure Java math plus Android touch plumbing;
- Android's touch slop replaces the upstream fixed small-motion threshold;
- movement is clamped to the current parent view and may snap horizontally,
  vertically, or to the nearest side after release;
- no `SYSTEM_ALERT_WINDOW` manifest permission is added by this change.

The upstream Apache-2.0 license is reproduced in
`third_party/easyfloat/LICENSE`.
