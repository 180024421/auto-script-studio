# Lua 脚本（推荐）

APK 内默认使用 **Lua** 执行 `main.lua`，由 LuaJ 虚拟机 + Kotlin `bot` API 驱动找图/找色/识字/YOLO。

## 工程结构

```
project.json      # entry: "main.lua", script_language: "lua"
main.lua          # 设备端执行的脚本
image/            # 模板图
models/           # YOLO .onnx + .labels
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
| `bot.findText(text, opts)` | 识字定位 |
| `bot.recognizeText(opts)` | 全屏识字列表 |
| `bot.yoloDetect(opts)` | YOLO 检测列表 |
| `bot.findYolo(opts)` | 找 YOLO 目标并返回坐标 |
| `bot.yoloSwipe(opts)` | 对 YOLO 目标滑动 |
| `bot.log(msg)` | 写日志 |

### opts 常用字段

- `timeout` 秒、`threshold`、`tol`、`click=true`
- `optional=true` 找不到不抛错，返回 `nil`
- YOLO: `model`, `class_name`, `conf`, `pick`（`best_conf`/`largest`/`nearest`）, `frac={0.5,0.3}`

## 示例

```lua
bot.delay(1)
local x, y = bot.findImage("image/btn.png", { threshold = 0.9, timeout = 15, click = true })
if not x then
  bot.log("未找到按钮")
end

local hx, hy = bot.findYolo({
  model = "models/ui.onnx",
  class_name = "hand",
  conf = 0.35,
  pick = "largest",
  click = true,
})
```

## 打包

```powershell
python -m packager.packager_cli build examples/ldplayer-test -o dist/test.apk
```

## YAML（旧）

`entry` 为 `.yaml` 时仍走 YAML 引擎，仅作兼容；新工程请用 Lua。
