# 教程 02：浮动面板与脚本联动

## 目标

用 `ui/layout.json` 做开始/停止按钮，脚本读取 `panel.*` 表单。

## 步骤

1. 浮动面板页编辑 `examples/demo-game/ui/layout.json`
2. 添加 `select` / `input` 等控件，记住控件 `id`（如 `mode`）
3. 在 `main.lua` 中：

```lua
local mode = panel.get("mode")
bot.log("当前模式: " .. tostring(mode))
if panel.is("mode", "极速") then
  -- 极速逻辑
end
```

4. 打包安装后，在设备上展开悬浮窗，填写表单后点**开始**

## 显示模式

- `display_mode: host` — **demo-game 默认**：主 Activity 填表，启停由悬浮球控制
- `display_mode: minimal` — 悬浮猫 + 紧凑控制条
- `display_mode: form` — 悬浮窗内完整表单

在 Studio **浮动面板** 页顶栏「展示」下拉可切换，无需手改 JSON。

详见 [ui-layout.md](../ui-layout.md) 与 [layout-parity.md](../layout-parity.md)。
