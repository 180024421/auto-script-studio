-- Auto-generated / LDPlayer 冒烟测试（Lua）

bot.log("ldplayer-test 开始")
bot.delay(1)

-- 中心色 BGR（由 run_emulator_test.py 生成时可覆盖）
bot.findColor(222, 222, 222, { tol = 18, timeout = 8 })

local x, y = bot.findImage("image/center_tpl.png", { threshold = 0.85, timeout = 10 })
if x then
  bot.log(string.format("模板命中 (%d,%d)", x, y))
  bot.tap(x, y)
else
  bot.tap(640, 360)
end

bot.log("ldplayer-test 完成")
