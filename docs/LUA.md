# Lua 脚本（推荐）

APK 内默认使用 **Lua** 执行 `main.lua`，由 LuaJ 虚拟机 + Kotlin `bot` API 驱动找图/找色/识字/YOLO/无障碍控件。

## 工程结构

```
project.json      # entry: "main.lua", script_language: "lua"
main.lua          # 设备端执行的脚本
ui/layout.json    # 浮动面板布局（按键精灵式，可选）
image/            # 模板图
models/           # YOLO .onnx + .labels
lib/              # 可选 Lua 模块
```

## API（全局 `bot` 或 `require("autoscript")`）

| 函数 | 说明 |
|------|------|
| `bot.delay(seconds)` | 等待 |
| `bot.tap(x, y)` | 点击 |
| `bot.swipe(x1,y1,x2,y2 [,duration_ms])` | 滑动 |
| `bot.longPress(x, y [,duration_ms])` | 长按 |
| `bot.findImage(path, opts)` | 找图，返回 `x,y` 或 `nil` |
| `bot.findColor(b,g,r, opts)` | 找色 BGR |
| `bot.findText(text, opts)` | OCR 识字定位 |
| `bot.findNode(opts)` | 无障碍控件查找（`text` / `id`） |
| `bot.recognizeText(opts)` | 全屏识字列表 |
| `bot.yoloDetect(opts)` | YOLO 检测列表 |
| `bot.findYolo(opts)` | 找 YOLO 目标并返回坐标 |
| `bot.yoloSwipe(opts)` | 对 YOLO 目标滑动 |
| `bot.log(msg)` | 写日志 |

### opts 常用字段

- `timeout` 秒、`threshold`、`tol`、`click=true`
- `optional=true` 找不到不抛错，返回 `nil`
- `findNode`: `text`, `id`, `match_mode`, `index`
- YOLO: `model`, `class_name`, `conf`, `pick`, `frac={0.5,0.3}`

## lib 模块

```lua
-- lib/utils.lua
local M = {}
function M.greet() bot.log("hello") end
return M

-- main.lua
local utils = require("utils")
utils.greet()
```

## 浮动面板 ui/layout.json

在 PC Studio「浮动面板」页编辑，或手写 JSON：

```json
{
  "enabled": true,
  "panel": { "title": "脚本助手", "columns": 2, "show_log": true },
  "buttons": [
    { "type": "start_script", "label": "开始", "color": "#4CAF50" },
    { "type": "stop_script", "label": "停止", "color": "#E53935" },
    { "type": "tap", "label": "攻击", "x": 900, "y": 600 },
    { "type": "lua", "label": "快捷", "lua": "bot.tap(100,200)" }
  ]
}
```

按钮类型：`start_script` / `stop_script` / `tap` / `swipe` / `long_press` / `lua` / `collapse`

## 打包

```powershell
python -m packager.packager_cli build examples/demo-game -o dist/demo.apk
```

## YAML（遗留）

`entry` 为 `.yaml` 时仍走 YAML 引擎；新工程请用 Lua。可用 `tools/yaml_to_lua.py` 迁移。
