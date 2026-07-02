# auto-script-studio

**独立的 Android 脚本工具链**：Lua 编写 → 打包 APK → 云手机 / 模拟器 / 真机离线运行。

支持 **无障碍 / root** 双模式、**按键精灵式浮动面板**（`ui/layout.json`）、PC 抓抓联调。  
**不依赖 adb-ide 或其他外部项目。**

## 架构

```
PC Studio  →  脚本工程（Lua + ui/layout.json + 资源）  →  Packager  →  独立 APK
                                                              ↓
                                                云手机 / 模拟器 / 真机
```

| 目录 | 说明 |
|------|------|
| `studio/` | PC 开发助手（工程 / 抓抓 / 浮动面板 / Lua 编辑） |
| `android-runtime/` | Android 运行时 |
| `packager/` | 打包 APK |
| `tools/` | YOLO 导出、YAML→Lua、模拟器冒烟 |
| `examples/` | 示例工程 |

## 能力一览

| 功能 | PC Studio | APK 运行时 |
|------|-----------|-----------|
| 找色/找图 | 抓抓 + OpenCV 测试 | ✅ |
| 识字 | PaddleOCR（可选安装） | ✅ ML Kit |
| YOLO | Ultralytics（可选安装） | ✅ ONNX |
| 浮动面板 | 布局编辑 + 截图叠加预览 | ✅ |
| 脚本 | Lua 高亮 + ADB 联调 | ✅ 离线 |

## 快速开始

```powershell
cd E:\xiangmu\auto-script-studio
.\start.cmd
```

工程页 → **打开 demo-game** → 抓抓页截图 → 查看浮动面板预览 → 打包并安装。

### 打包 APK

```powershell
python -m packager.packager_cli build examples/demo-game -o dist/demo-game.apk
```

需 JDK 17 + Android SDK（见 `docs/pack-guide.md`）。

### 可选：抓抓页 OCR / YOLO 测试

```powershell
.\.venv\Scripts\pip install paddleocr paddlepaddle ultralytics
```

## 脚本工程结构

```
my-game/
├── project.json
├── main.lua
├── ui/layout.json      # 浮动面板（可选）
├── image/
├── models/             # YOLO .onnx + .labels
└── lib/                # require 模块
```

## 文档

- [Lua API](docs/LUA.md)
- [架构说明](docs/ARCHITECTURE.md)
- [浮动面板布局](docs/ui-layout.md)
- [打包指南](docs/pack-guide.md)
- [YAML 遗留 API](docs/script-api.md)
