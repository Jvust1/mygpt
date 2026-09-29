# Xiaomi 14 真机验收清单：Spine skin 3714430278

本清单对应 Draft PR #10 的 exact-head renderer CI 证据。它只验证私有调试宿主和用户设备行为，不构成生产发布或真实 Book 集成验收。

## 固定证据

- GitHub 分支：`feat/android-companion-boundary-20260928`
- renderer exact head：`a076be06e2e4c3eeecdab3f1860143771bfef0d3`
- CI run：36449517394
- GitHub artifact：10983131261 / `mygpt-spine-3714430278-android-spike`
- artifact ZIP SHA-256：`1de222d0ef784a4fd5ab32970f5deb9772fcf12074a3fe2a2bc0108e7f896411`
- 已解密 Live 包：`3714430278.zip`
- Live 包 SHA-256：`eb6eddc96172c03fe4d0dd4dd8a68180ce832aeb82ae07f7f82175fed57bc23f`

## 安装前

1. 在 GitHub Actions run 36449517394 下载 artifact，先校验 ZIP SHA-256，再解压得到 `app-debug.apk`。
2. 在 Xiaomi 14 记录型号、Android 版本、MIUI/HyperOS 版本和剩余存储。
3. 开启开发者选项与 USB 调试，连接电脑后确认 `adb devices` 只列出目标手机。
4. 安装 exact-head APK：

```sh
adb install -r app-debug.apk
adb shell pm list packages | grep dev.mygpt.spike
```

安装失败、包名不匹配或设备不是目标手机时，停止验收并记录原因。

## 验收顺序

### 1. 冷启动和静默默认

- 冷启动应用，确认没有崩溃、没有网络/麦克风/悬浮窗权限请求。
- 预期：界面显示 Spine 渲染区域；未导入皮肤前，状态提示选择 `3714430278.zip`。
- 记录首次启动截图和启动耗时。

### 2. SAF 导入与首帧

- 点击“选择 / 更换 3714430278.zip”，通过系统文件选择器选中**已解密** ZIP。
- 预期：状态先显示校验/安装，随后显示 Spine 4.1.x 和 SHA 前缀；渲染区域出现首帧。
- 记录：首帧是否出现、耗时、是否变形/黑屏、是否有崩溃或 ANR。
- 如果导入失败，只记录错误文本和截图，不绕过校验或改包。

### 3. cue/动画转换

按以下顺序操作并记录渲染区域与状态文本：

| 操作 | 预期 cue / 动画 |
| --- | --- |
| 开始模拟 Book 会话 | `QUIET` / idle |
| 打开“允许轻量学习提醒”后模拟连续出错 | 需要本次会话授权；按 coordinator 冷却规则显示提醒 |
| 主动请求帮助 | `NEEDS_INPUT` / smile；没有 smile 时回退 idle |
| 暂停学习 | `PAUSED` / 当前动画冻结 |
| 恢复学习 | 回到 idle |
| 结束会话 | 回到 quiet，提醒授权清除 |

这里的 Book 事件仍是 synthetic test double；通过不等于真实 Book producer 已接入。

### 4. 后台、锁屏和重开

1. 已导入皮肤并开始模拟会话。
2. 按 Home、切换其他应用，再回到测试宿主；另测一次锁屏后解锁。
3. 预期：后台/锁屏触发 session 清除，重新打开后为 quiet，需重新开始会话并重新勾选提醒授权；已授予的 SAF URI 可用于重新加载皮肤。
4. 记录前后台切换是否崩溃、是否残留旧 cue、是否能重新显示首帧。

### 5. 失败恢复

- 选择错误文件或损坏 ZIP，确认应用拒绝并显示可读错误。
- 在导入过程中离开应用再回来，确认不会把半成品当作有效皮肤。
- 发现崩溃、黑屏、ANR、错误动画或后台残留时，保留截图/屏幕录制和 `adb logcat`，不要继续宣称通过。

## 记录模板

- 设备：
- Android / MIUI 或 HyperOS：
- APK SHA-256：
- Live ZIP SHA-256：
- 首帧：PASS / FAIL（耗时：）
- QUIET / idle：
- NEEDS_INPUT / smile：
- PAUSED / freeze：
- 恢复 / idle：
- 后台重开：
- 错误包拒绝：
- 崩溃、ANR、黑屏或权限弹窗：
- 截图/日志位置：
- 结论：CI verified / device verified / blocked

只有完成上述记录并保存证据后，才可以把 governance 状态从 `DEVICE_PENDING` 推进。Spine Runtime 的许可证门槛和真实 Book Android producer 门槛仍然独立存在。
