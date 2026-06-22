# auto-script-studio

Android 脚本开发助手 + 打包运行时。对标 **按键精灵手机助手** + **adb-ide** 能力，面向云手机 / 模拟器独立运行。

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

### 4. PC Studio（后续完善）

```powershell
cd studio
pip install -r requirements.txt
python -m studio.main
```

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
