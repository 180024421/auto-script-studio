# 扫城脚本示例

国战类游戏的「定时扫城」流程：整点等待 → YOLO 识别地图/城池 → 选将 → 出征 → 换页计数。

> 与其他示例不同：**核心流程不在 Lua 里**。`main.lua` 只做「读面板配置 → 调 `bot.runSaocheng`」，
> 状态机实现在设备运行时的 `android-runtime/script/src/main/java/com/autoscript/script/saocheng/`
> （12 个 Kotlin 文件）。因此：
>
> - **PC 联调跑不了**（`bot.runSaocheng` 只注册在 APK 侧），Studio 里会打印
>   「当前环境无 runSaocheng，请使用打包后的 APK」。
> - 改流程逻辑要重编 APK，不能靠「热替换推送」。
> - `project.json` 里的 `"features": ["saocheng"]` 目前**没有任何代码读取**（packager 与 Gradle
>   都不看它），打出来的 APK 一律包含这套逻辑。它是给「未来按 feature 裁剪构建」留的占位。

## 文件

| 文件 | 作用 |
|------|------|
| `main.lua` | 入口，读配置后调原生状态机 |
| `saocheng_config.json` | 城池列表、武将（`name` / `hourly_limit` / `enabled`）、置信度等 |
| `cities.json` | 城池 ID 与坐标数据（供 `CityData` 使用） |
| `models/ui.onnx` + `ui.labels` | 界面元素检测模型（`project.json` → `default_yolo_model`） |
| `ui/layout.json` | 浮动面板：开始/停止、武将开关、置信度等 |

面板配置改动通过 `SaochengPanelSync` 同步进运行时状态机。

## 运行

1. `.\start.cmd` → 工程页打开本目录
2. 运行目标选 **打包安装**（见 `docs/pack-guide.md`）：
   ```powershell
   python -m packager.packager_cli build examples/saocheng-game -o dist/saocheng.apk
   ```
3. 装好后开无障碍 + 录屏权限，进游戏再用面板启动

## 配置要点

- `runtime.input_mode: auto`（root 优先，否则无障碍）、`screenshot_mode: media_projection`
- `runtime.default_yolo_imgsz: 640`、`perf.yolo_nnapi: false`（NNAPI 失败已回退 CPU，可按机型开）
- `license.enabled: false` —— 自用不需要卡密；对外分发再开

## 拿它当模板？

适合「流程固定、界面靠 YOLO 认」的挂机需求。若你希望逻辑留在 Lua 里（可热替换、可 PC 联调），
参考 `examples/lingzhu-fishing/main.lua` 的纯 Lua 状态机写法，而不是这套原生实现。
