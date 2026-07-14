-- 读取浮动面板（全部页签）
local account = panel.get("account") or ""
local password = panel.get("password") or ""
local auto_login = panel.get("auto_login")
local w_2 = panel.get("w_2") or "普通"
local priority = panel.get("priority") or "高"
local delay_sec = panel.get("delay_sec") or "1"
local loop_count = panel.get("loop_count") or "1"
local features = panel.get("features") or ""

bot.log(string.format("账号: %s", tostring(account)))
bot.log(string.format("密码: %s", password ~= "" and "******" or "(空)"))
bot.log(string.format("自动登录: %s", tostring(auto_login)))
bot.log(string.format("等级: %s", tostring(w_2)))
bot.log(string.format("优先级: %s", tostring(priority)))
bot.log(string.format("步骤间隔(秒): %s", tostring(delay_sec)))
bot.log(string.format("循环次数: %s", tostring(loop_count)))
bot.log(string.format("附加功能: %s", tostring(features)))

if panel.is("w_2", "普通") then
  bot.log(">> 普通模式")
elseif panel.is("w_2", "极速") then
  bot.log(">> 极速模式")
elseif panel.is("w_2", "省电") then
  bot.log(">> 省电模式")
end
-- 读取浮动面板（全部页签）
local account = panel.get("account") or ""
local password = panel.get("password") or ""
local auto_login = panel.get("auto_login")
local mode = panel.get("mode") or "普通"
local priority = panel.get("priority") or "高"
local delay_sec = panel.get("delay_sec") or "1"
local loop_count = panel.get("loop_count") or "1"
local features = panel.get("features") or ""

bot.log(string.format("账号: %s", tostring(account)))
bot.log(string.format("密码: %s", password ~= "" and "******" or "(空)"))
bot.log(string.format("自动登录: %s", tostring(auto_login)))
bot.log(string.format("模式: %s", tostring(mode)))
bot.log(string.format("优先级: %s", tostring(priority)))
bot.log(string.format("步骤间隔(秒): %s", tostring(delay_sec)))
bot.log(string.format("循环次数: %s", tostring(loop_count)))
bot.log(string.format("附加功能: %s", tostring(features)))

if panel.is("mode", "普通") then
  bot.log(">> 普通模式")
elseif panel.is("mode", "极速") then
  bot.log(">> 极速模式")
elseif panel.is("mode", "省电") then
  bot.log(">> 省电模式")
end
-- 读取浮动面板（全部页签）
local account = panel.get("account") or ""
local password = panel.get("password") or ""
local auto_login = panel.get("auto_login")
local mode = panel.get("mode") or "普通"
local priority = panel.get("priority") or "高"
local delay_sec = panel.get("delay_sec") or "1"
local loop_count = panel.get("loop_count") or "1"
local features = panel.get("features") or ""

bot.log(string.format("账号: %s", tostring(account)))
bot.log(string.format("密码: %s", password ~= "" and "******" or "(空)"))
bot.log(string.format("自动登录: %s", tostring(auto_login)))
bot.log(string.format("模式: %s", tostring(mode)))
bot.log(string.format("优先级: %s", tostring(priority)))
bot.log(string.format("步骤间隔(秒): %s", tostring(delay_sec)))
bot.log(string.format("循环次数: %s", tostring(loop_count)))
bot.log(string.format("附加功能: %s", tostring(features)))

if panel.is("mode", "普通") then
  bot.log(">> 普通模式")
elseif panel.is("mode", "极速") then
  bot.log(">> 极速模式")
elseif panel.is("mode", "省电") then
  bot.log(">> 省电模式")
end
-- 读取浮动面板（全部页签）
local account = panel.get("account") or ""
local password = panel.get("password") or ""
local auto_login = panel.get("auto_login")
local mode = panel.get("mode") or "普通"
local priority = panel.get("priority") or "高"
local delay_sec = panel.get("delay_sec") or "1"
local loop_count = panel.get("loop_count") or "1"
local features = panel.get("features") or ""

bot.log(string.format("账号: %s", tostring(account)))
bot.log(string.format("密码: %s", password ~= "" and "******" or "(空)"))
bot.log(string.format("自动登录: %s", tostring(auto_login)))
bot.log(string.format("模式: %s", tostring(mode)))
bot.log(string.format("优先级: %s", tostring(priority)))
bot.log(string.format("步骤间隔(秒): %s", tostring(delay_sec)))
bot.log(string.format("循环次数: %s", tostring(loop_count)))
bot.log(string.format("附加功能: %s", tostring(features)))

if panel.is("mode", "普通") then
  bot.log(">> 普通模式")
elseif panel.is("mode", "极速") then
  bot.log(">> 极速模式")
elseif panel.is("mode", "省电") then
  bot.log(">> 省电模式")
end
-- Demo Game — 浮动面板展示示例
-- 读取面板配置并输出日志，便于在实机查看控件效果

bot.log("======== Demo 助手 ========")

local account = panel.get("account") or ""
local password = panel.get("password") or ""
local autoLogin = panel.get("auto_login")
local mode = panel.get("mode") or "普通"
local priority = panel.get("priority") or ""
local delaySec = panel.get("delay_sec") or "2"
local loopCount = panel.get("loop_count") or "1"
local features = panel.get("features") or ""

bot.log(string.format("账号: %s", account))
bot.log(string.format("密码: %s", password ~= "" and "******" or "(空)"))
bot.log(string.format("自动登录: %s", tostring(autoLogin)))
bot.log(string.format("模式: %s | 优先级: %s", mode, priority))
bot.log(string.format("间隔: %s 秒 | 循环: %s 次", delaySec, loopCount))
bot.log(string.format("附加功能: %s", features))

if panel.is("mode", "极速") then
  bot.log(">> 极速模式：步骤间隔缩短")
elseif panel.is("mode", "省电") then
  bot.log(">> 省电模式：降低操作频率")
else
  bot.log(">> 普通模式")
end

local loops = tonumber(loopCount) or 1
for i = 1, loops do
  bot.log(string.format("--- 第 %d / %d 轮 ---", i, loops))
  bot.delay(tonumber(delaySec) or 1)
  local cx, cy = bot.findColor(40, 40, 40, { tol = 30, timeout = 2, optional = true })
  if cx then
    bot.log(string.format("找色命中 (%d,%d)", cx, cy))
  else
    bot.log("找色未命中（演示跳过）")
  end
end

bot.log("======== 演示完成 ========")
