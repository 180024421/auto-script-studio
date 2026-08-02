-- 扫城 APK 入口：读取面板配置 → 调用原生扫城状态机（与 saocheng_pc_debug 一致）
bot.log("扫城工程启动")

local conf = 0.30
if bot.runSaocheng then
  bot.runSaocheng({ conf = conf, auto = true })
else
  bot.log("当前环境无 runSaocheng，请使用打包后的 APK")
end
