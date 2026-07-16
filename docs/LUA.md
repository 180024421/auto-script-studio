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
| `bot.waitGoneImage(path, opts)` | 等待模板消失 |
| `bot.waitStable(opts)` | 等待画面稳定 |
| `bot.findMultiColor(opts)` | 多点找色（opts.points） |
| `bot.trace(tag, msg)` | 调试 trace 日志 |
| `bot.log(msg)` | 写日志 |
| `bot.toast(msg)` | Toast 提醒（真机） |
| `bot.openApp(packageName)` | 按包名打开应用（如钉钉 `com.alibaba.android.rimet`），无需 root |
| `bot.listApps()` | 可启动应用列表，每项 `{label, package}` |
| `bot.reloadPanel()` | 刷新浮动面板（更新应用下拉等） |
| `bot.read_chain(module, offset, offsets, type?)` | 按模块+偏移链读内存（需 root） |
| `bot.load_bases(jsonPath)` | 加载 ce-base SCC JSON，返回可调用读数表 |
| `bot.set_memory_pid(pid)` | 设置读内存目标 PID |
| `bot.set_pointer_size(4\|8)` | 指针宽度 |

### 内存会话搜值（全局 `mem`，需 root）

用于「无稳定基址」时：按画面值搜索 → 变数过滤 → 本局锁定地址。

| 函数 | 说明 |
|------|------|
| `mem.find_pid(package)` | 按包名找 PID |
| `mem.search(key, value, type?)` | 精确搜值，返回候选数；`type` 默认 `int32`，可选 `float`/`int64` |
| `mem.refine(key, newValue)` | 在候选上过滤；返回 `{count, locked, address?}` |
| `mem.read_cached(key, type?)` | 读已锁定地址 |
| `mem.get_address(key)` | 返回 `0x...` 或 nil |
| `mem.candidates(key)` | 当前候选数量 |
| `mem.clear(key?)` | 清除一个或全部会话 |
| `mem.lock(key, address, type?)` | 手动锁定地址 |
| `mem.aob_scan(pattern [, module] [, all])` | AOB 扫描；默认返回首个 `0x...`，`all=true` 返回地址表 |
| `mem.read(address, type?)` | 按地址读类型值（配合 aob_scan） |
| `mem.list_modules(refresh?)` | 模块基址表 |
| `mem.read_chain` / `mem.load_bases` | 同 `bot.*` |

示例工程：`examples/mem-lock`（浮动面板 3 槽位，名称自填）。

### opts 常用字段

- `timeout` 秒、`threshold`、`tol`、`click=true`
- `optional=true` 找不到不抛错，返回 `nil`
- 找图多尺度：`scale_min` / `scale_max` / `scale_step`（默认 1.0）
- `findNode`: `text`, `id`, `match_mode`（`contains`/`equals`/`starts_with`）, `index`, `click`
- YOLO: `model`, `class_name`, `conf`, `pick`（含 `largest_mask`）, `frac`, `use_mask_center`, `use_box_center`
- YOLO seg：`runtime.yolo_auto_mask_center=true` 时自动用掩码质心

### `bot.yoloDetect` 返回列表元素

每个检测项为表，字段固定如下（PC 调试与 APK 一致）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `class_name` | string | 类别名（来自 `.labels`） |
| `confidence` | number | 置信度 0~1 |
| `x`, `y` | int | 框左上角 |
| `w`, `h` | int | 框宽高 |
| `center_x`, `center_y` | int | 框中心点 |
| `has_mask` | bool | 是否为 seg 掩码结果（detect 模型恒为 `false`） |
| `mask_center_x`, `mask_center_y` | int | 掩码质心（仅 `has_mask=true`） |
| `mask_area` | int | 掩码前景像素数（仅 `has_mask=true`） |

```lua
local dets = bot.yoloDetect({ model = "models/ui.onnx", class_name = "hand" })
for _, d in ipairs(dets) do
  if d.has_mask then
    bot.log(d.class_name .. " mask@" .. d.mask_center_x .. "," .. d.mask_center_y)
  else
    bot.log(d.class_name .. " box@" .. d.center_x)
  end
end

-- seg 模型：点击掩码中心而非框中心
local x, y = bot.findYolo({
  model = "models/ui-seg.onnx",
  class_name = "hand",
  use_mask_center = true,
  click = true,
})
```

### 工程 `models/` 目录

- 放置 `*.onnx`（APK 推理）及同名 `*.labels`（每行一个类别名）
- PC Studio 脚本页「模型」Tab 可导入、编辑 labels、设默认模型（写入 `project.json` → `runtime.default_yolo_model`）
- 从 `.pt` 导出：`python tools/export_yolo_onnx.py --pt best.pt --out models/ui`

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
