-- Demo Game — 可运行示例（找色 + 面板表单）

bot.log("demo-game 开始")

-- 浮动面板表单（需 APK 浮动面板或 PC 预览填写后运行）
-- local mode = panel.get("mode")
-- if panel.is("mode", "极速") then bot.log("极速") end
-- if panel.has("tasks", "日常") then bot.log("含日常") end

bot.delay(1)
-- 找色：屏幕中心附近灰色（模拟器桌面常见色）
local cx, cy = bot.findColor(40, 40, 40, { tol = 30, timeout = 5, optional = true })
if cx then
  bot.log(string.format("找色命中 (%d,%d)", cx, cy))
else
  bot.log("找色未命中，跳过")
end

-- 找图（需 image/center.png）
local x, y = bot.findImage("image/center.png", { threshold = 0.8, timeout = 5, optional = true })
if x then
  bot.log(string.format("找图命中 (%d,%d)", x, y))
  bot.tap(x, y)
end

-- 无障碍控件示例（需目标应用在前台）
-- local nx, ny = bot.findNode({ text = "设置", timeout = 3, optional = true })

bot.log("demo-game 完成")
