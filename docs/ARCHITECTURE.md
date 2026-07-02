# 项目定位

**auto-script-studio** 是独立的 Android 脚本开发与打包工具链，不依赖任何外部 IDE 项目。

```
PC Studio（抓抓/编辑/打包）  →  脚本工程（Lua + ui/layout.json + 资源）  →  Packager  →  独立 APK
                                                                              ↓
                                                            云手机 / 模拟器 / 真机 + 浮动面板
```

| 目录 | 说明 |
|------|------|
| `studio/` | PC 开发助手（PySide6）：工程、抓抓、浮动面板、Lua 编辑、ADB 联调 |
| `android-runtime/` | Android 运行时壳（无障碍/root、截屏、视觉、Lua、浮动面板） |
| `packager/` | 工程 → assets → Gradle APK |
| `tools/` | YOLO 导出、YAML→Lua 迁移、模拟器冒烟 |
| `examples/` | 示例工程 |

## 脚本形态

- **推荐语言：Lua**（`main.lua`，`bot.*` API）
- 打包后进 APK `assets/project/`，设备上**离线运行**
- PC 联调：`python -m studio.runtime.lua_runner` 或 Studio「PC 运行 Lua」

YAML 为遗留兼容，新工程请用 Lua。

## Android 输入/截屏（`project.json` → `runtime`）

| `input_mode` | 点击/滑动 | 截屏 | 适用 |
|--------------|-----------|------|------|
| `auto` | root 优先，否则无障碍 | root / 录屏 / 无障碍截图 | 云手机、模拟器 |
| `accessibility` | 无障碍手势 | MediaProjection / API30+ 无障碍截图 | 无 root 真机 |
| `root` | `su input` | `su screencap` | 已 root，免无障碍/录屏 |

## 推荐工作流

1. `start.cmd` 启动 Studio → 新建/打开工程
2. **抓抓**页 ADB 截图、取色、模板、识字/YOLO 测试（可选依赖）
3. **浮动面板**页编辑 `ui/layout.json`，抓抓页叠加预览
4. **脚本编辑** `main.lua`，PC ADB 联调
5. 打包 APK → 安装到设备 → 授权无障碍/悬浮窗 → 运行

## PC Studio 与 APK 能力对应

| 能力 | PC Studio（联调） | APK 运行时 |
|------|-------------------|------------|
| 找色/找图 | OpenCV 测试 | Kotlin NCC |
| OCR | PaddleOCR（可选） | ML Kit 中文离线 |
| YOLO | Ultralytics（可选） | ONNX Runtime |
| 浮动面板 | 布局编辑 + 截图预览 | OverlayService |
| 脚本 | Lua + lupa 联调 | LuaJ |

算法语义在 `bot.*` API 层对齐；PC 与设备实现不同，但脚本写法一致。
