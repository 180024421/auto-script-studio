-- Demo Game — 官方示例（找色 + 浮动面板）
-- 详见 examples/demo-game/README.md

bot.log("demo-game 开始")

local mode = panel.get("mode")
if mode and tostring(mode) ~= "" then
  bot.log("面板模式: " .. tostring(mode))
  if panel.is("mode", "极速") then
    bot.log("已选择极速模式")
  end
end

bot.delay(1)

-- 找色：可按抓抓页取色结果修改 RGB
local cx, cy = bot.findColor(40, 40, 40, { tol = 30, timeout = 5, optional = true })
if cx then
  bot.log(string.format("找色命中 (%d,%d)", cx, cy))
  bot.tap(cx, cy)
else
  bot.log("找色未命中（可改 RGB 或在抓抓页取色）")
end

-- 找图（需在 image/ 放置模板，见 image/README.md）
local x, y = bot.findImage("image/template.png", { threshold = 0.8, timeout = 3, optional = true })
if x then
  bot.log(string.format("找图命中 (%d,%d)", x, y))
  bot.tap(x, y)
end

bot.log("demo-game 完成")
