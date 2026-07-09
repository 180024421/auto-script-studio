# auto-script-studio

**独立的 Android 游戏/应用自动化脚本工具链**：在 PC 上编写 Lua 脚本、设计浮动控制面板、调试视觉能力，一键打包为可离线运行的 APK，部署到云手机、模拟器或真机。

对标按键精灵的「脚本 + 悬浮窗」体验，同时提供完整的 PC 开发助手。  
**不依赖 adb-ide、script-control-center 或其他外部项目。**

<p align="center">
  <img src="images/jimeng.png" alt="吉祥物" width="120" />
</p>

> 演示 GIF 制作后请放入 `docs/assets/` 并在下方取消注释。  
> `<!-- ![Studio 总览](docs/assets/studio-overview.png) -->`

---

## 项目能做什么

| 场景 | 说明 |
|------|------|
| 手游/应用挂机脚本 | Lua 控制点击、滑动、找图找色、识字、YOLO 目标检测 |
| 可视化控制面板 | 按键精灵式浮动窗：表单输入、多标签页、开始/停止脚本 |
| PC 联调 | ADB 连接设备截图取色，与 APK 运行时使用同一套 `bot.*` API 语义 |
| 独立分发 | 打包成单个 APK，脚本与资源内嵌，设备端无需 PC 即可运行 |
| 多运行环境 | 无障碍 / root 双模式，适配无 root 真机、模拟器、云手机 |

---

## 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│  PC Studio（PySide6）                                            │
│  工程管理 │ 抓抓联调 │ 浮动面板编辑 │ Lua 脚本 │ 打包安装          │
└────────────────────────────┬────────────────────────────────────┘
                             │ 脚本工程目录
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  脚本工程（Lua + ui/layout.json + image/ + models/）             │
└────────────────────────────┬────────────────────────────────────┘
                             │ Packager
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  独立 APK（android-runtime）                                     │
│  LuaJ 脚本 │ 找图/找色 │ OCR │ YOLO │ OverlayService 悬浮窗     │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
                    云手机 / 模拟器 / 真机
```

| 目录 | 职责 |
|------|------|
| `studio/` | PC 开发助手：工程、抓抓、浮动面板 WYSIWYG 编辑、Lua 高亮编辑、ADB 联调、异步打包 |
| `android-runtime/` | Android 运行时壳：无障碍/root 自动化、截屏、视觉算法、Lua 执行、悬浮窗 |
| `packager/` | 将工程资源编译进 APK assets，调用 Gradle 构建 |
| `tools/` | YOLO 导出、YAML→Lua 迁移、模拟器冒烟等辅助工具 |
| `examples/` | 示例工程（如 `demo-game`） |
| `docs/` | Lua API、架构、浮动面板、打包指南 |
| `tests/` | Python 单元测试（布局、打包、视觉、脚本等） |

---

## PC Studio 功能

启动：`.\start.cmd` 或 `python -m studio`

### 1. 工程页

- 新建 / 打开 / 最近工程 / 导入导出 ZIP
- 编辑 `project.json`（应用名、图标、入口脚本、运行模式等）
- **打包安装**：后台异步构建 APK，不阻塞界面；支持自定义图标与应用信息
- 设备列表与 ADB 连接状态

### 2. 抓抓页

- ADB 实时截图，叠加到手机画布
- **取色**、**框选模板**、保存到 `image/`
- 找图 / 找色 / OCR / YOLO **本地测试**（与设备端 API 语义对齐）
- 浮动面板布局**截图叠加预览**，所见即所得对照实机效果

### 3. 浮动面板页

- 编辑 `ui/layout.json`（v3 数据模型）
- **多界面标签** + 每页**自由布局**（720×1280 设计坐标）
- 表单控件：输入框、下拉、开关、滑条、单选、多选、时间范围、文字说明等
- 底部 chrome：**开始 / 停止** 脚本按钮
- 拖动、缩放、网格吸附、撤销重做、复制粘贴、界面导入导出
- **极简悬浮模式**（`display_mode: minimal`）：实机仅显示悬浮猫 + 紧凑控制条，可配置日志区、左侧停靠、空闲自动收起

### 4. 脚本页

- Lua 语法高亮编辑器
- **指令工具箱**：常用 `bot.*` 命令一键插入
- 侧边栏：浮动面板控件树、附件图库、YOLO 模型管理
- **PC 运行 Lua**：通过 ADB 在已连接设备上联调
- 面板状态与脚本变量 `panel.*` 联动

---

## APK 运行时功能

打包后脚本与资源内嵌于 `assets/project/`，设备上**完全离线**执行。

### 自动化能力

| 能力 | 实现 | 说明 |
|------|------|------|
| 点击 / 滑动 / 长按 | 无障碍手势 或 `su input` | `project.json` 配置 `input_mode` |
| 截屏 | MediaProjection / root screencap / 无障碍截图 | 按环境自动选择 |
| 找图 | OpenCV NCC 模板匹配 | `bot.findImage` |
| 找色 | 多点找色 | `bot.findColor` |
| 识字 | ML Kit 中文离线 OCR | `bot.findText` / `bot.recognizeText` |
| YOLO | ONNX Runtime（detect + seg） | `bot.yoloDetect` / `bot.findYolo` |
| 无障碍控件 | 节点查找与点击 | `bot.findNode` |

### 浮动面板（OverlayService）

- 渲染 `ui/layout.json`，支持 **form 全面板** 与 **minimal 极简条** 两种展示模式
- 透明悬浮球、可拖动、展开控制条（开始/停止/日志）
- 脚本通过 `panel.控件id` 读取用户输入
- 运行日志与主界面同步显示
- 可选启动时自动弹出、无操作自动收起

### 运行模式（`project.json` → `runtime`）

| `input_mode` | 点击/滑动 | 截屏 | 适用 |
|--------------|-----------|------|------|
| `auto` | root 优先，否则无障碍 | 多种回退 | 云手机、模拟器 |
| `accessibility` | 无障碍手势 | 录屏 / API30+ 截图 | 无 root 真机 |
| `root` | `su input` | `su screencap` | 已 root 环境 |

---

## 脚本工程结构

```
my-game/
├── project.json          # 入口、运行模式、应用信息
├── main.lua              # 主脚本（推荐）
├── ui/
│   └── layout.json       # 浮动面板布局（可选）
├── image/                # 找图模板、抓抓截图
├── models/               # YOLO .onnx + .labels
└── lib/                  # 可选 Lua 模块（require）
```

脚本语言推荐 **Lua**（`bot.*` API）；YAML 为遗留兼容。

---

## 能力对照：PC vs APK

| 功能 | PC Studio（联调） | APK 运行时 |
|------|-------------------|------------|
| 找色 / 找图 | OpenCV 测试 | ✅ Kotlin NCC |
| 识字 | PaddleOCR（可选安装） | ✅ ML Kit |
| YOLO | Ultralytics（可选安装） | ✅ ONNX |
| 浮动面板 | 布局编辑 + 截图预览 | ✅ OverlayService |
| 脚本执行 | Lua + ADB 联调 | ✅ LuaJ 离线 |
| 打包 | Gradle 构建 APK | — |

PC 与设备实现不同，但 **`bot.*` API 语义一致**，联调通过的脚本可直接打包运行。

---

## 快速开始

详见 **[5 分钟上手](docs/getting-started.md)**。

```powershell
cd auto-script-studio
.\start.cmd
```

1. 工程页 → **打开** `examples/demo-game`
2. 抓抓页 → ADB 连接设备 → 截图取色
3. 浮动面板页 → 预览/编辑布局
4. 脚本页 → 编辑 `main.lua` → PC 运行测试
5. 工程页 → **打包安装** → 设备授权无障碍与悬浮窗 → 运行

### 命令行打包

```powershell
python -m packager.packager_cli build examples/demo-game -o dist/demo-game.apk
```

需 JDK 17 + Android SDK，详见 [打包指南](docs/pack-guide.md)。

### 可选：PC 端 OCR / YOLO 测试依赖

```powershell
.\.venv\Scripts\pip install paddleocr paddlepaddle ultralytics
```

### 运行测试

```powershell
python -m pytest tests/ -q
```

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [快速上手](docs/getting-started.md) | 5 分钟跑通 demo-game |
| [Lua API](docs/LUA.md) | `bot.*`、`panel.*` 脚本接口 |
| [架构说明](docs/ARCHITECTURE.md) | 模块划分、工作流、运行模式 |
| [浮动面板布局](docs/ui-layout.md) | `layout.json` v3 数据模型与控件 |
| [打包指南](docs/pack-guide.md) | JDK/SDK 配置、签名、CI |
| [与按键精灵对比](docs/comparison-anjian.md) | 能力对照 |
| [工具生态](docs/ECOSYSTEM.md) | 关联开源项目 |
| [定制服务](docs/services.md) | 接单套餐说明 |
| [教程目录](docs/tutorials/01-find-color.md) | 找色 / 面板 / 部署 |
| [FAQ](docs/faq.md) | 常见问题 |
| [YAML 遗留 API](docs/script-api.md) | 旧版 YAML 脚本（不推荐新项目） |

---

## 技术栈

- **PC**：Python 3.11+、PySide6、OpenCV、可选 PaddleOCR / Ultralytics
- **Android**：Kotlin、LuaJ、ONNX Runtime、ML Kit、AccessibilityService
- **构建**：Gradle (AGP)、JDK 17

---

## 许可证

[MIT License](LICENSE)

## 相关项目

| 项目 | 说明 |
|------|------|
| [adb-ide](https://github.com/180024421/adb-ide) | 抓图 / OCR / YOLO 开发 IDE |
| [script-control-center](https://github.com/180024421/adb-batch-runner) | 多开批量中控（完整版） |
| [adb-batch-runner](https://github.com/180024421/adb-batch-runner) | 轻量 Web 批量运行 |
| [jiaoben](https://github.com/180024421/jiaoben) | 卡密发卡与脚本监控 |

定制开发见 [docs/services.md](docs/services.md)。问题反馈请使用 [GitHub Issues](../../issues)。

## 免责声明

仅供学习交流。请遵守游戏/应用用户协议；不得用于外挂、破解、破坏公平竞技等用途。
