-- 面板按钮用：槽位会话搜值 / 过滤锁定 / 清除
local M = {}

local function trim(s)
  if s == nil then return "" end
  return (tostring(s):gsub("^%s+", ""):gsub("%s+$", ""))
end

function M.ensure_pid()
  local pkg = trim(panel.get("game_pkg"))
  if pkg == "" then
    bot.toast("请先在「目标应用」下拉中选择游戏")
    return false
  end
  local ok, pid = pcall(function()
    return mem.find_pid(pkg)
  end)
  if not ok then
    bot.toast("找不到进程，请先打开游戏")
    return false
  end
  bot.set_memory_pid(pid)
  local psz = trim(panel.get("pointer_size"))
  if psz == "4" then
    bot.set_pointer_size(4)
  else
    bot.set_pointer_size(8)
  end
  return true
end

function M.search_slot(i)
  if not M.ensure_pid() then return end
  local name = trim(panel.get("mem_name_" .. i))
  local typ = trim(panel.get("mem_type_" .. i))
  local v1 = tonumber(panel.get("mem_v1_" .. i))
  if name == "" then
    bot.toast("槽位" .. i .. "：请填写名称")
    return
  end
  if typ == "" then typ = "int32" end
  if v1 == nil then
    bot.toast("槽位" .. i .. "：请填写当前值")
    return
  end
  local msg = "搜索中…"
  panel.set("mem_status_" .. i, msg)
  bot.log("[" .. name .. "] " .. msg)
  local ok, n = pcall(function()
    return mem.search(name, v1, typ)
  end)
  if not ok then
    panel.set("mem_status_" .. i, "失败")
    bot.log("[" .. name .. "] 初搜失败: " .. tostring(n))
    bot.toast("初搜失败: " .. tostring(n))
    return
  end
  msg = "候选 " .. tostring(n) .. "，请变数后过滤"
  panel.set("mem_status_" .. i, msg)
  bot.log("[" .. name .. "] " .. msg)
  bot.toast(name .. " 候选 " .. tostring(n))
end

function M.refine_slot(i)
  if not M.ensure_pid() then return end
  local name = trim(panel.get("mem_name_" .. i))
  local v2 = tonumber(panel.get("mem_v2_" .. i))
  if name == "" then
    bot.toast("槽位" .. i .. "：请填写名称")
    return
  end
  if v2 == nil then
    bot.toast("槽位" .. i .. "：请填写变化后的新值")
    return
  end
  local ok, ret = pcall(function()
    return mem.refine(name, v2)
  end)
  if not ok then
    panel.set("mem_status_" .. i, "过滤失败")
    bot.log("[" .. name .. "] 过滤失败: " .. tostring(ret))
    bot.toast(tostring(ret))
    return
  end
  local count = ret.count or 0
  local addr = ret.address or "-"
  local msg
  if count == 0 then
    msg = "无剩余候选，请重搜"
  elseif count == 1 then
    msg = "已锁定 " .. tostring(addr)
  else
    msg = "锁定首选/" .. count .. " " .. tostring(addr)
  end
  panel.set("mem_status_" .. i, msg)
  bot.log("[" .. name .. "] " .. msg)
  bot.toast(name .. " refine=" .. tostring(count))
end

function M.clear_slot(i)
  local name = trim(panel.get("mem_name_" .. i))
  if name ~= "" then
    mem.clear(name)
  end
  panel.set("mem_status_" .. i, "已清除")
  bot.toast("已清除槽位 " .. i)
end

function M.refresh_apps()
  if bot.reloadPanel() then
    bot.toast("应用列表已刷新")
  else
    bot.toast("刷新失败，请重开浮动面板")
  end
end

return M
