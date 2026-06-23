# auto-script-studio

**Android 脚本**：Lua 编写 → 打包 APK → 云手机 / 模拟器 / 真机运行。  
**Windows 脚本请用 [adb-ide](../adb-ide)**（本仓库不管 Windows 自动化）。

支持 **无障碍** 与 **root** 两种设备控制方式（`runtime.input_mode`：`auto` / `accessibility` / `root`）。详见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 架构

```
PC Studio（开发）  →  脚本工程（YAML/Lua + 资源）  →  Packager  →  独立 APK
                                                              ↓
                                                    云手机 / 模拟器 / 真机
```

| 目录 | 说明 |
|------|------|
| `studio/` | PC 开发助手（PySide6，ADB 联调、抓图、打包入口） |
| `android-runtime/` | Android 运行时壳（无障碍 + 截屏 + 视觉 + 脚本引擎） |
| `packager/` | 将脚本工程注入运行时并签名 APK |
| `tools/` | YOLO/OCR 模型导出等工具 |
| `examples/` | 示例脚本工程 |
| `docs/` | 脚本 API、打包指南 |

## 仓库

- GitHub: https://github.com/180024421/auto-script-studio

## 能力一览

| 功能 | PC Studio（ADB 联调） | APK 运行时 |
|------|----------------------|-----------|
| 找色 | 抓抓页取色 + 测试 | ✅ |
| 找图 | 框选存模板 + OpenCV 测试 | ✅ NCC 模板匹配 |
| 识字 / 找字 | PaddleOCR 测试（可选安装） | ✅ ML Kit 中文离线 |
| YOLO | Ultralytics 测试（可选安装） | ✅ ONNX 推理 |
| 脚本 | YAML 编辑 | ✅ flows/actions |
| 打包 APK | 一键打包 | 云手机/模拟器独立运行 |

## 快速开始

### 1. 查看示例工程

```powershell
cd E:\xiangmu\auto-script-studio
dir examples\demo-game
```

### 2. 打包 APK（需 Android SDK + JDK 17）

```powershell
python -m packager.packager_cli build examples/demo-game -o dist/demo-game.apk
```

### 3. 编译运行时（开发）

```powershell
cd android-runtime
.\gradlew.bat :app:assembleDebug
```

### 4. PC Studio

```powershell
cd E:\xiangmu\auto-script-studio
.\start.cmd
```

或分步执行：

```powershell
.\setup-studio.cmd
.\run-studio.cmd
```

- **工程**：新建/打开/打包
- **抓抓**：ADB 截图、取色、存模板、测试找色/找图/识字/YOLO
- **脚本编辑**：编辑 `main.yaml`

可选安装 PC 端识字/YOLO 测试：

```powershell
.\.venv\Scripts\pip install paddleocr paddlepaddle ultralytics
```

### 5. YOLO 模型导出（打进 APK）

```powershell
python tools/export_yolo_onnx.py --pt D:\models\best.pt --out examples\demo-game\models\ui
```

生成 `models/ui.onnx` + `models/ui.labels`，打包时自动进 APK。

## 脚本工程结构

```
my-game/
├── project.json      # 包名、应用名、图标、入口
├── main.yaml         # 入口脚本（flows/actions）
├── image/            # 模板图
├── models/           # YOLO ncnn 模型（可选）
└── lib/              # 可选 Lua（后续）
```

## 文档

- [脚本 API](docs/script-api.md) — 对齐 adb-ide YAML 语义
- [打包指南](docs/pack-guide.md)
- [工程配置 Schema](docs/project-schema.json)

## 体积目标

- 基础运行时（找色 + 找图 + YAML + YOLO 占位）：~15–22 MB（arm64）
- 含离线 OCR：+8–12 MB
- 用户资源（图 + 模型）：按工程而定

## 与 adb-ide 关系

- **开发阶段**：PC 可用 adb-ide 或本 Studio 做 ADB 联调
- **算法语义**：`game.yaml` actions/flows 与 adb-ide 一致
- **模型链路**：adb-ide 训练 `.pt` → `tools/export_yolo_ncnn.py` → 工程 `models/`
