-- 钉钉打卡提醒：到点 Toast + 打开钉钉（依赖钉钉自身「极速/自动打卡」）
-- 不需要 root；不代点打卡按钮。

local DINGTALK_PKG = "com.alibaba.android.rimet"

bot.toast("该打卡了，正在打开钉钉…")
bot.delay(0.3)

local ok = bot.openApp(DINGTALK_PKG)
if ok then
  bot.log("已打开钉钉，请确认自动打卡完成")
else
  bot.toast("打开钉钉失败：请确认已安装钉钉")
  bot.log("openApp 失败: " .. DINGTALK_PKG)
end
