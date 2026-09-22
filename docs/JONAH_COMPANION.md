# 约拿宠物组件 v0.1

## 交付范围与现状

用户希望把已有的「约拿」动态宠物放进 mygpt，并在手机界面右下角显示。恢复 GitHub 后确认：截至基础分支 `79257dc1c0c3b1b78cf8ae58e7ad5d3fd4c251c3`，mygpt 只有治理和产品架构文档，没有运行中的前端或原生 Android 项目。

本阶段加入一个无框架依赖的 Web Component 和可运行的交互演示，用作未来 mygpt 网页或 WebView 内的陪伴界面。它是实际可渲染、可交互的组件，但不是已经上线的 mygpt 产品，也不是 Android APK。

| 能力 | 当前实现 |
| --- | --- |
| 应用内右下角显示 | 默认 112px，距离底部 76px 加安全区；可由宿主覆盖 |
| 手机触摸 | 点击打开操作面板；拖动改变位置；拖动结束不会误触聊天 |
| 键盘操作 | Tab 聚焦；方向键微调；Escape 收起面板 |
| 可控性 | 隐藏、显示、回到右下角、尺寸调整、暂停动画 |
| 本地记忆 | 仅位置和隐藏偏好；localStorage 不可用时降级为会话内使用 |
| 动画 | 9 组完整动作、16 个明确视线方向；复用已验证的原始 PNG |
| 状态接口 | 安静、处理、等待回应、新进展、需要处理 |
| 省资源 | 定时器按原始帧时长更新；后台、隐藏、断开连接、减少动态效果时停止 |
| 聊天入口 | 发出事件，交给宿主打开真正的聊天模块；演示不伪装模型回答 |
| 跨应用安卓悬浮窗 | 未实现，需要另建 Android Studio 工程和系统悬浮窗授权流程 |
| 真机与生产接入 | 尚未验证；Book 语义事件桥和模型服务仍待实现 |

## 启动演示

需要 Node.js 20 或更新版本，运行时无 npm 第三方依赖：

```sh
npm start
```

浏览器打开终端打印的 `http://127.0.0.1:4173`。开发服务器默认只监听本机，不自动暴露到局域网或公网。

页面明确标为交互演示。按钮只用于演示状态与回调，不表示 Book 或真实任务已有连接。

## 集成到 mygpt 前端

保持 `companion/` 目录结构和图片路径，通过静态文件服务发布。将元素直接挂在 `document.body` 下，避免祖先的 transform/overflow 改变 fixed 定位或裁切宠物。

```html
<script type="module" src="/companion/mygpt-pet.js"></script>
<mygpt-pet id="companion" status="idle" size="112"></mygpt-pet>
```

```js
const pet = document.querySelector('#companion');
pet.addEventListener('pet-chat-request', () => {
  // 在此调用未来 mygpt 宿主的聊天入口。
  openMyGPTChat();
});

pet.setStatus('working');       // 宿主开始处理任务时调用
pet.setStatus('needs-input');   // 宿主明确需要用户输入时调用
pet.setStatus('ready');         // 宿主有未读结果时调用
pet.setStatus('idle');          // 默认安静陪伴
pet.setStatus('blocked');       // 实际错误或阻塞；不能根据用户长时间未操作推断
```

`openMyGPTChat` 为宿主应实现的函数，不包含在本组件中。它不建立网络连接、收集屏幕内容或读取其他应用。

### API

| 接口 | 说明 |
| --- | --- |
| `status` 属性 / `setStatus(name)` | 上表五种业务状态；方法遇到未知值抛出 RangeError；不可信 HTML 属性退回 idle |
| `animation` 属性 | 显式循环指定动作；移除后恢复业务状态映射 |
| `play(name)` | 播放一次，结束恢复当前业务状态；减少动态效果时保留首帧 |
| `look(degrees)` | 16 方向中最近的一帧；0° 向右、90° 向下、180° 向左、270° 向上 |
| `resume()` | 取消一次性动作或视线覆盖；`animation` 属性仍有效 |
| `show()` / `hide()` | 显示/隐藏并记住偏好；发出可见性事件 |
| `resetPosition()` | 清除拖动位置并回到默认右下角 |
| `size` 属性 | 72–192 CSS px；无效值使用 112 |
| `paused` 属性 | 停在首帧；与系统减少动态效果偏好一起生效 |
| `storage-key` 属性 | 挂载前指定存储键；默认 `mygpt:jonah:v1` |
| `--pet-bottom` | 宿主底部工具栏预留高度，默认 76px |
| `--pet-z-index` | 层级，默认 1000；宿主弹窗应位于宠物上方 |

事件均可冒泡并穿过 Shadow DOM：

```js
pet.addEventListener('pet-visibility-change', event => {
  // 宿主应保留一个可发现的“显示约拿”按钮，避免隐藏后无法找回。
  restoreButton.hidden = event.detail.visible;
});
pet.addEventListener('pet-error', event => {
  // asset-load-failed / invalid-atlas-size：记录宿主可处理的资源错误。
  console.warn(event.detail.reason);
});
```

元素通过 Shadow DOM 隔离样式；无外部字体、CDN、第三方脚本、模型请求或统计上报。宿主传入的文字不通过 innerHTML 渲染。

## Android 路线

当前组件只作用于包含它的页面。未来如果 mygpt 使用 WebView，可承载此组件，但需要按全项目约定在 Android Studio 中开发、构建和真机测试。若要求切换到 ChatGPT/Book/其他 App 后仍显示，则属于独立的 Android 系统悬浮窗能力，不能用网页 fixed 定位冒充，也不能声称已完成。

不使用无障碍权限、不读取其他 App、不截图、不阻止息屏。本阶段不改变 Book、StudyMate 或 ChatContextVault。

## 素材身份与来源

`companion/assets/jonah.png` 来自本次会话已经完成并启用的约拿宠物。人物为根据用户提供参考生成的完整黑色服装、自然站姿版本，保留银发、黑角、蝠翼和长尾。未把原始 WPK 或其原始预览加入仓库。

- PNG：1536×2288，RGBA，8 列×11 行；单格 192×208。
- 字节数：1,650,227。
- SHA-256：`828b0fb468382f37aaf0d62a3e86cb33e5fcad5dbde8aeb091d6778b32a77790`。
- 9 行动作帧数：6、8、8、4、5、8、6、6、6。
- 最后 2 行为 16 个视线方向；其余空单元格不参与播放。
- 当前 Work 宠物 ID：`pet_6ab1cf72af608191a912286aab4a48d0`。这仅为来源记录，组件不依赖 Work 帐号或 Pets API。
- 此处记录来源，不额外授予参考角色的商业使用或再分发权利。

## 设计对标与参考

1. [VS Code Pets](https://github.com/tonybaloney/vscode-pets/tree/2c91214beb922288cca1938cddb607abc5f806b7)，研究日期 2026-09-22，main 当时固定为 `2c91214beb922288cca1938cddb607abc5f806b7`，MIT。仅快速阅读 README 产品交互和 LICENSE，未进入源码级学习，未复制代码/图片，Drive 完整源码快照：不适用。借鉴小型宠物和按需互动的产品形态；VS Code 扩展架构不适用于当前尚无技术栈的 mygpt，因此使用浏览器原生组件。
2. [MDN 自定义元素生命周期](https://developer.mozilla.org/en-US/docs/Web/API/Web_components/Using_custom_elements)：挂载时注册监听，断开时清理；避免重连重复监听。
3. [MDN Pointer Events](https://developer.mozilla.org/en-US/docs/Web/API/Pointer_events)：统一鼠标和触摸输入、pointer capture，以及 touch-action 对原生滚动的影响。

阶段复盘：保留单一精灵图和事件接口，无游戏引擎或 WebGL 依赖；补足手机拖动阈值、可见区域约束、隐藏恢复和减少动态效果。因项目尚无宿主，不把演示 UI 当作最终 mygpt 产品架构。

## 验证与待办

```sh
npm test
# 另一个终端保持 npm start，开发环境安装 Playwright 及 Chromium 后：
npm run test:browser
```

浏览器测试依赖仅用于开发验证；当前运行环境已有 Playwright，浏览器包单独安装。测试覆盖实际触摸拖动、状态切换、图片加载、位置/隐藏持久化、减少动态效果、不同视口、断连清理与禁用 localStorage 降级。原生 Android 真机、软键盘实机交互、生产聊天后端、跨应用悬浮窗和独立人工审查均不能以模拟测试代替。

下一步：将组件接入未来选定的 mygpt 宿主，再用真实 Book 语义状态驱动展示；按 Android Studio 路线完成手机承载和真机验收。基础 PR 与本功能 PR 均需独立审阅和明确合并授权。
