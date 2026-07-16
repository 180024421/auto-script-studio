-- 会话内存锁定示例：面板完成「初搜→过滤」后，主脚本循环读数。
-- 使用前：Root + 面板选择目标应用（会记住，无需每次填写）

local PKG = panel.get("game_pkg")
if PKG == nil or PKG == "" then
  bot.toast("请先在面板选择目标应用")
  bot.log("game_pkg 未选择")
  return
end
local ok, pid = pcall(function()
  return mem.find_pid(PKG)
end)
if not ok then
  bot.toast("找不到进程: " .. PKG .. "，请先打开游戏")
  bot.log("find_pid failed: " .. tostring(pid))
  return
end
bot.set_memory_pid(pid)
bot.set_pointer_size(8)
bot.log("pid=" .. tostring(pid))

local function slot_name(i)
  local n = panel.get("mem_name_" .. i)
  if n == nil or n == "" then return nil end
  return n
end

-- 等待用户在面板锁定至少一个字段
bot.toast("请在面板填写名称/类型/数值并「初搜→过滤锁定」")
local locked = {}
for round = 1, 120 do
  locked = {}
  for i = 1, 3 do
    local name = slot_name(i)
    if name then
      local addr = mem.get_address(name)
      if addr then
        locked[#locked + 1] = name
      end
    end
  end
  if #locked > 0 then break end
  bot.delay(1)
end

if #locked == 0 then
  bot.toast("未锁定任何地址，退出")
  return
end

bot.toast("已锁定: " .. table.concat(locked, ", "))
while true do
  for _, name in ipairs(locked) do
    local ok2, val = pcall(function()
      return mem.read_cached(name)
    end)
    if ok2 then
      bot.log(name .. "=" .. tostring(val))
    else
      bot.log(name .. " 读取失败，需重新锁定: " .. tostring(val))
    end
  end
  bot.delay(2)
end
