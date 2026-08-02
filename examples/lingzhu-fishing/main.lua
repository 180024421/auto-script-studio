-- 腾芝洋领主钓鱼辅助（auto-script-studio / 云手机 APK）
-- 忠实移植自 lingzhu_pc.py -> lingzhu_engine.py / lingzhu_fishing.py
-- 关键点：
--   1) 收线用 bot.reelHold 连续按住（等价 PC ReelHoldController 的重叠 swipe），
--      press=持续按住、release=立即抬起，识别与按住互不阻塞。
--   2) 圆弧量规控制器完整移植（带鱼带中心权重 / 滑脱恢复 / 跳变抑制 / 弧端 / 接触冷却 / 收线锁 / 迟滞）。
--   3) 屏幕分辨率来自 bot.screenSize()，据此缩放 pivot 偏移与像素余量（训练基准 720x1280）。
-- bot.yoloDetect 返回字段：x/y=中心，left/top=左上，width/height=宽高，class_name，confidence

local M = {
  model = "models/lingzhu.onnx",
  yolo_conf = 0.35,
  menu_conf = 0.55,          -- menu_min_conf
  loop_sleep = 0.0,          -- 依赖检测耗时自然限速
  tap_delay = 0.35,          -- tap_delay_ms
  menu_cooldown = 1.5,       -- menu_tap_cooldown_ms

  -- 参考分辨率（像素类参数基准）
  ref_w = 720,
  ref_h = 1280,

  -- fanwei 尺寸筛选（相对屏宽/高）
  fanwei_reroll_enabled = true,
  fanwei_min_w_ratio = 0.085,
  fanwei_min_h_ratio = 0.083,
  fanwei_min_area_ratio = 0.0083,
  fanwei_check_delay = 0.6,  -- fanwei_check_delay_ms
  fanhui_min_conf = 0.50,
  fanhui_fallback_x_ratio = 0.08,
  fanhui_fallback_y_ratio = 0.92,
  max_fanwei_reroll = 40,

  -- 圆弧量规控制（弧度 / 度，与 Python 配置一致）
  pivot_offset_y = -120,        -- 基准值，运行时按屏高缩放
  approach_margin_px = 14,      -- 基准值，运行时缩放
  contain_margin_px = 6,        -- 基准值，运行时缩放
  overlap_iou_min = 0.02,
  press_error_rad = 0.07,
  release_error_rad = -0.05,
  approach_release_rad = 0.14,
  reengage_rad = 0.11,
  contact_cooldown_ms = 380,
  slip_recovery_ms = 480,
  jump_guard_deg = 26.0,
  align_max_deg = 12.0,
  contact_max_deg = 18.0,
  band_min_span_deg = 10.0,
  band_max_span_deg = 52.0,
  band_center_weight = 0.42,
  arc_edge_ratio = 0.12,
  vel_smooth_alpha = 0.35,
  predict_ms = 120,
  hold_lock_ms = 400,
  min_hold_ms = 100,
  max_hold_ms = 420,

  log_interval = 30,
}

-- 运行时按真实分辨率解析出的像素参数
local R = {
  screen_w = 720,
  screen_h = 1280,
  pivot_offset_y_px = -120,
  approach_margin_px = 14,
  contain_margin_px = 6,
}

local state = {
  fishing_locked = false,
  fanwei_ok = false,
  prefer_paogan_only = false,
  fanwei_reroll_count = 0,
  last_menu_tap_at = nil,
  last_cast_tap_at = nil,
  last_fanhui_tap_at = nil,

  -- 弧控状态
  fw_ang_min = nil,
  fw_ang_max = nil,
  yu_ang_min = nil,
  yu_ang_max = nil,
  prev_arc_err = nil,
  prev_ctrl_err = nil,
  prev_ts = nil,
  yu_ang_vel = 0.0,
  fw_ang_vel = 0.0,
  last_action = "release",
  press_since = nil,
  contact_since = nil,
  slip_since = nil,
  had_contact = false,

  -- 连续按住状态
  holding = false,

  tick = 0,
}

local math_pi = math.pi
local math_atan2 = math.atan2 or function(y, x) return math.atan(y, x) end
local math_deg = math.deg
local math_rad = math.rad
local math_abs = math.abs
local math_min = math.min
local math_max = math.max
local math_floor = math.floor

local function now_ms()
  if bot.nowMs then return bot.nowMs() end
  return os.clock() * 1000.0
end

local function now()
  return now_ms() / 1000.0
end

local function log(msg)
  bot.log("[灵珠] " .. msg)
end

local function delay(s)
  if s and s > 0 then bot.delay(s) end
end

-- ===== 检测项取值（Kotlin: x/y=中心, left/top, width/height）=====
local function cx(d) return d.x or d.center_x or ((d.left or 0) + (d.width or d.w or 0) / 2) end
local function cy(d) return d.y or d.center_y or ((d.top or 0) + (d.height or d.h or 0) / 2) end
local function dw(d) return d.width or d.w or 0 end
local function dh(d) return d.height or d.h or 0 end
local function dleft(d) return d.left or (cx(d) - dw(d) / 2) end
local function dtop(d) return d.top or (cy(d) - dh(d) / 2) end
local function dright(d) return dleft(d) + dw(d) end
local function dbottom(d) return dtop(d) + dh(d) end

local function contains_point(d, px, py, margin)
  margin = margin or 0
  return px >= dleft(d) - margin and px <= dright(d) + margin
     and py >= dtop(d) - margin and py <= dbottom(d) + margin
end

local function iou_with(a, b)
  local ax1, ay1, ax2, ay2 = dleft(a), dtop(a), dright(a), dbottom(a)
  local bx1, by1, bx2, by2 = dleft(b), dtop(b), dright(b), dbottom(b)
  local ix1, iy1 = math_max(ax1, bx1), math_max(ay1, by1)
  local ix2, iy2 = math_min(ax2, bx2), math_min(ay2, by2)
  local iw, ih = math_max(0, ix2 - ix1), math_max(0, iy2 - iy1)
  local inter = iw * ih
  if inter <= 0 then return 0.0 end
  local ua = dw(a) * dh(a) + dw(b) * dh(b) - inter
  if ua <= 0 then return 0.0 end
  return inter / ua
end

local function norm_angle_diff(a, b)
  local d = a - b
  while d > math_pi do d = d - 2 * math_pi end
  while d < -math_pi do d = d + 2 * math_pi end
  return d
end

local function ema(prev, value, alpha)
  return alpha * value + (1.0 - alpha) * prev
end

-- ===== 检测 =====
local function detect_all()
  return bot.yoloDetect({ model = M.model, conf = M.yolo_conf })
end

local function find_best(dets, class_name, min_conf)
  min_conf = min_conf or 0
  local best = nil
  for i = 1, #dets do
    local d = dets[i]
    if d.class_name == class_name and (d.confidence or 0) >= min_conf then
      if not best or (d.confidence or 0) > (best.confidence or 0) then
        best = d
      end
    end
  end
  return best
end

local function menu_button(dets, class_name, min_conf)
  return find_best(dets, class_name, min_conf)
end

-- ===== 状态维护 =====
local function reset_track()
  state.fishing_locked = false
  state.fw_ang_min = nil
  state.fw_ang_max = nil
  state.yu_ang_min = nil
  state.yu_ang_max = nil
  state.prev_arc_err = nil
  state.prev_ctrl_err = nil
  state.prev_ts = nil
  state.yu_ang_vel = 0.0
  state.fw_ang_vel = 0.0
  state.last_action = "release"
  state.press_since = nil
  state.contact_since = nil
  state.slip_since = nil
  state.had_contact = false
end

local function note_menu_tap(ts) state.last_menu_tap_at = ts end

local function note_cast_tap(ts)
  state.last_cast_tap_at = ts
  state.fanwei_ok = false
  state.prefer_paogan_only = false
  state.fishing_locked = false
end

local function note_fanhui_tap(ts)
  state.last_fanhui_tap_at = ts
  state.fanwei_ok = false
  state.fishing_locked = false
  state.prefer_paogan_only = true
  state.fanwei_reroll_count = state.fanwei_reroll_count + 1
  state.fw_ang_min = nil
  state.fw_ang_max = nil
  state.yu_ang_min = nil
  state.yu_ang_max = nil
  state.prev_arc_err = nil
  state.prev_ctrl_err = nil
  state.prev_ts = nil
  state.yu_ang_vel = 0.0
  state.fw_ang_vel = 0.0
  state.last_action = "release"
  state.press_since = nil
  state.contact_since = nil
  state.slip_since = nil
  state.had_contact = false
end

-- ===== 阶段判定 =====
local function detect_phase(dets)
  local yu = find_best(dets, "yu")
  local fanwei = find_best(dets, "fanwei")
  local shouxian = find_best(dets, "shouxian")
  if fanwei and shouxian then state.fishing_locked = true; return "fishing" end
  if yu and fanwei then state.fishing_locked = true; return "fishing" end
  if state.fishing_locked and fanwei then return "fishing" end
  local paogan = menu_button(dets, "paogan", M.menu_conf)
  local jixu = menu_button(dets, "jixu", M.menu_conf)
  if paogan or (jixu and not fanwei) then
    state.fishing_locked = false
    return "menu"
  end
  return "idle"
end

local function menu_click_target(dets)
  local paogan = menu_button(dets, "paogan", M.menu_conf)
  if paogan then return paogan end
  if state.prefer_paogan_only then return nil end
  return menu_button(dets, "jixu", M.menu_conf)
end

local function fanhui_tap_target(dets)
  local fh = menu_button(dets, "fanhui", M.fanhui_min_conf)
  if fh then return cx(fh), cy(fh), "fanhui" end
  return math_floor(R.screen_w * M.fanhui_fallback_x_ratio),
         math_floor(R.screen_h * M.fanhui_fallback_y_ratio),
         "fanhui(fallback)"
end

local function fanwei_size_ok(fw)
  local wr = dw(fw) / math_max(1, R.screen_w)
  local hr = dh(fw) / math_max(1, R.screen_h)
  local ar = (dw(fw) * dh(fw)) / math_max(1, R.screen_w * R.screen_h)
  return wr >= M.fanwei_min_w_ratio and hr >= M.fanwei_min_h_ratio and ar >= M.fanwei_min_area_ratio
end

-- ===== 圆弧几何 =====
local function gauge_pivot(shouxian)
  return cx(shouxian), cy(shouxian) + R.pivot_offset_y_px
end

local function arc_angle(x, y, px, py)
  return math_atan2(y - py, x - px)
end

local function bbox_near(yu, fanwei)
  if iou_with(fanwei, yu) >= M.overlap_iou_min then return true end
  return contains_point(fanwei, cx(yu), cy(yu), R.approach_margin_px)
end

local function arc_caught(chase_err)
  return math_abs(chase_err) <= M.approach_release_rad
end

local function arc_approaching(chase_err, yu, fanwei)
  if not bbox_near(yu, fanwei) then return false end
  return math_abs(chase_err) <= math_rad(M.contact_max_deg)
end

local function arc_overshot(chase_err)
  return chase_err < M.release_error_rad
end

local function update_yu_band(ang_yu)
  if not state.yu_ang_min then
    state.yu_ang_min = ang_yu
    state.yu_ang_max = ang_yu
    return
  end
  state.yu_ang_min = math_min(state.yu_ang_min, ang_yu)
  state.yu_ang_max = math_max(state.yu_ang_max, ang_yu)
  local span = state.yu_ang_max - state.yu_ang_min
  local max_span = math_rad(M.band_max_span_deg)
  if span > max_span then
    local half = max_span / 2.0
    state.yu_ang_min = ang_yu - half
    state.yu_ang_max = ang_yu + half
  end
end

local function control_error(ang_yu, ang_fw)
  local chase = norm_angle_diff(ang_yu, ang_fw)
  if not state.yu_ang_min or not state.yu_ang_max then
    return chase, chase, 0.0
  end
  local span = state.yu_ang_max - state.yu_ang_min
  if span < math_rad(M.band_min_span_deg) then
    return chase, chase, 0.0
  end
  local band_c = (state.yu_ang_min + state.yu_ang_max) / 2.0
  local center = norm_angle_diff(band_c, ang_fw)
  local w = M.band_center_weight
  return (1.0 - w) * chase + w * center, chase, center
end

local function arc_metrics(yu, fanwei, shouxian, ts)
  local px, py = gauge_pivot(shouxian)
  local ang_yu = arc_angle(cx(yu), cy(yu), px, py)
  local ang_fw = arc_angle(cx(fanwei), cy(fanwei), px, py)
  update_yu_band(ang_yu)
  local ctrl_err, chase_err, center_err = control_error(ang_yu, ang_fw)
  local aligned = arc_caught(chase_err)
  local approaching = arc_approaching(chase_err, yu, fanwei)
  local inside = aligned
  local contact = approaching or aligned

  if not state.fw_ang_min then
    state.fw_ang_min = ang_fw
    state.fw_ang_max = ang_fw
  else
    state.fw_ang_min = math_min(state.fw_ang_min, ang_fw)
    state.fw_ang_max = math_max(state.fw_ang_max, ang_fw)
  end

  if state.prev_ts and state.prev_ctrl_err then
    local dt = math_max(0.008, math_min(0.25, ts - state.prev_ts))
    local rel = ctrl_err - state.prev_ctrl_err
    while rel > math_pi do rel = rel - 2 * math_pi end
    while rel < -math_pi do rel = rel + 2 * math_pi end
    local raw_vel = rel / dt
    state.yu_ang_vel = ema(state.yu_ang_vel, raw_vel, M.vel_smooth_alpha)
    state.fw_ang_vel = ema(state.fw_ang_vel, raw_vel, M.vel_smooth_alpha)
  end

  state.prev_arc_err = chase_err
  state.prev_ctrl_err = ctrl_err
  state.prev_ts = ts
  return ctrl_err, chase_err, center_err, ang_yu, ang_fw, inside, contact
end

local function arc_control(ctrl_err, chase_err, center_err, ang_fw, inside, contact, slipped, ts)
  local predict_s = M.predict_ms / 1000.0
  local pred_err = ctrl_err + (state.yu_ang_vel - state.fw_ang_vel) * predict_s
  local chase_deg = math_deg(chase_err)
  local band_deg = 0.0
  if state.yu_ang_min and state.yu_ang_max then
    band_deg = math_deg(state.yu_ang_max - state.yu_ang_min)
  end

  if slipped then state.slip_since = ts end

  if state.slip_since then
    local since_ms = (ts - state.slip_since) * 1000.0
    if since_ms < M.slip_recovery_ms then
      if chase_err <= M.release_error_rad then
        return "release", string.format("滑脱恢复 %.0fms d=%.1f", since_ms, chase_deg)
      end
      state.slip_since = nil
    end
  end

  if state.prev_arc_err and not contact and not inside then
    local jump = math_abs(math_deg(norm_angle_diff(chase_err, state.prev_arc_err)))
    if jump > M.jump_guard_deg then
      return "release", string.format("跳变抑制 d=%.1f", chase_deg)
    end
  end

  local span = 0.5
  if state.fw_ang_max and state.fw_ang_min then
    span = math_max(state.fw_ang_max - state.fw_ang_min, 0.15)
  end
  local edge_rad = span * M.arc_edge_ratio
  local at_right = state.fw_ang_max ~= nil
    and ang_fw >= state.fw_ang_max - edge_rad
    and chase_err < M.release_error_rad
  local at_left = state.fw_ang_min ~= nil
    and ang_fw <= state.fw_ang_min + edge_rad

  if inside then
    return "release", string.format("对齐 d=%.1f", chase_deg)
  end
  if arc_overshot(chase_err) then
    return "release", string.format("超出 d=%.1f", chase_deg)
  end
  if contact and not inside and chase_err <= 0 then
    return "release", string.format("接近 d=%.1f", chase_deg)
  end
  if state.last_action == "press" and chase_err > 0 and chase_err < M.approach_release_rad then
    return "release", string.format("收线到位 d=%.1f", chase_deg)
  end
  if pred_err > 0 and pred_err < M.approach_release_rad and state.yu_ang_vel < 0 then
    return "release", string.format("预判接近 d=%.1f", math_deg(pred_err))
  end
  if at_right then
    return "release", string.format("弧右端 d=%.1f", chase_deg)
  end

  if state.contact_since then
    local since_ms = (ts - state.contact_since) * 1000.0
    if since_ms < M.contact_cooldown_ms and ctrl_err < M.reengage_rad then
      return "release", string.format("接触冷却 %.0fms d=%.1f", since_ms, chase_deg)
    end
  end

  local want_press = pred_err > M.press_error_rad or ctrl_err > M.press_error_rad
  local want_release = pred_err < M.release_error_rad and ctrl_err < M.release_error_rad

  if state.press_since and state.last_action == "press" then
    local held_ms = (ts - state.press_since) * 1000.0
    if held_ms < M.hold_lock_ms and ctrl_err > M.release_error_rad then
      want_release = false
    end
  end

  if at_left and ctrl_err > M.press_error_rad * 0.5 then
    want_press = true
    want_release = false
  end

  if want_press and not want_release then
    local tag = (band_deg >= M.band_min_span_deg) and string.format("带鱼%.0f", band_deg) or "追鱼"
    return "press", string.format("%s d=%.1f", tag, math_deg(ctrl_err))
  end
  if want_release then
    return "release", string.format("松开 d=%.1f", math_deg(ctrl_err))
  end
  if state.last_action == "press" then
    return "press", string.format("迟滞收线 d=%.1f", math_deg(ctrl_err))
  end
  return "release", string.format("迟滞松开 d=%.1f", math_deg(ctrl_err))
end

local function control_frame(yu, fanwei, shouxian, ts)
  local ctrl_err, chase_err, center_err, _ang_yu, ang_fw, inside, contact =
    arc_metrics(yu, fanwei, shouxian, ts)
  local slipped = state.had_contact and not arc_caught(chase_err)
  local action, msg = arc_control(ctrl_err, chase_err, center_err, ang_fw, inside, contact, slipped, ts)

  if contact or inside then state.contact_since = ts end
  state.had_contact = state.had_contact or arc_caught(chase_err)
  if action == "press" and state.last_action ~= "press" then
    state.press_since = ts
  elseif action == "release" then
    state.press_since = nil
  end
  state.last_action = action
  return action, msg
end

-- ===== 连续按住控制 =====
local function set_hold(want, x, y)
  if want then
    if not state.holding then
      bot.reelHold(true, math_floor(x + 0.5), math_floor(y + 0.5))
      state.holding = true
      log(string.format("按住 (%d,%d)", math_floor(x + 0.5), math_floor(y + 0.5)))
    end
  else
    if state.holding then
      bot.reelHold(false, 0, 0)
      state.holding = false
      log("松开")
    end
  end
end

-- ===== 点击 =====
local function do_tap(x, y, label, ts)
  set_hold(false)
  x = math_floor(x + 0.5)
  y = math_floor(y + 0.5)
  log(string.format("点击 %s (%d,%d)", label or "", x, y))
  bot.tap(x, y)
  local kind = (label or ""):gsub("%(.*%)", "")
  if kind == "paogan" then
    note_cast_tap(ts); note_menu_tap(ts)
  elseif kind:sub(1, 6) == "fanhui" then
    note_fanhui_tap(ts); note_menu_tap(ts)
  elseif kind == "jixu" then
    reset_track(); note_menu_tap(ts)
  else
    note_menu_tap(ts)
  end
  delay(M.tap_delay)
end

-- ===== 主决策（对应 analyze_fishing）=====
-- 返回: action, x, y, class, msg
local function analyze(dets, ts)
  local phase = detect_phase(dets)

  if phase == "menu" then
    state.fishing_locked = false
    local target = menu_click_target(dets)
    if target then
      local cooldown = math_max(0.5, M.menu_cooldown)
      if state.last_menu_tap_at and (ts - state.last_menu_tap_at) < cooldown then
        return "wait", 0, 0, "", "已点击 " .. target.class_name .. "，等待界面…"
      end
      return "tap", cx(target), cy(target), target.class_name, "点击 " .. target.class_name
    end
    if state.prefer_paogan_only then
      return "wait", 0, 0, "", "等待 paogan 按钮…"
    end
    return "wait", 0, 0, "", "菜单态但未找到可点击目标"
  end

  if phase ~= "fishing" then
    reset_track()
    return "idle", 0, 0, "", "等待进入钓鱼界面"
  end

  local yu = find_best(dets, "yu")
  local fanwei = find_best(dets, "fanwei")
  local shouxian = find_best(dets, "shouxian")

  -- 抛竿后 fanwei 尺寸筛选（不达标点返回重抛）
  if M.fanwei_reroll_enabled and not state.fanwei_ok then
    if not state.last_cast_tap_at then
      state.fanwei_ok = true
    else
      if (ts - state.last_cast_tap_at) < M.fanwei_check_delay then
        return "wait", 0, 0, "", "抛竿后等待 fanwei 稳定…"
      end
      if not fanwei then
        return "wait", 0, 0, "", "等待 fanwei 出现…"
      end
      if fanwei_size_ok(fanwei) then
        state.fanwei_ok = true
        return "wait", 0, 0, "", string.format("fanwei 合格 w=%.2f 开始收线", dw(fanwei) / R.screen_w)
      end
      if state.fanwei_reroll_count >= M.max_fanwei_reroll then
        state.fanwei_ok = true
        return "wait", 0, 0, "", "fanwei 重抛已达上限，继续"
      end
      local cooldown = math_max(0.5, M.menu_cooldown)
      if state.last_menu_tap_at and (ts - state.last_menu_tap_at) < cooldown then
        return "wait", 0, 0, "", string.format("fanwei 偏小 w=%.2f，等待点击 fanhui…", dw(fanwei) / R.screen_w)
      end
      local fx, fy, fclass = fanhui_tap_target(dets)
      return "tap", fx, fy, fclass,
        string.format("fanwei 偏小 w=%.2f，点返回重抛", dw(fanwei) / R.screen_w)
    end
  end

  if not fanwei then return "wait", 0, 0, "", "缺少 fanwei" end
  if not yu then return "wait", 0, 0, "", "缺少 yu" end
  if not shouxian then return "wait", 0, 0, "", "缺少 shouxian" end

  local action, msg = control_frame(yu, fanwei, shouxian, ts)
  return action, cx(shouxian), cy(shouxian), "", msg
end

-- ===== 应用决策 =====
local function apply_decision(action, x, y, class, ts)
  if action == "press" then
    set_hold(true, x, y)
  elseif action == "release" then
    set_hold(false)
  elseif action == "tap" then
    do_tap(x, y, class, ts)
  elseif action == "idle" then
    set_hold(false)
  end
  -- action == "wait"：保持当前按住状态不变（对应 PC _apply_reel 的 wait 分支）
end

-- ===== 初始化屏幕尺寸与缩放参数 =====
local function init_scale()
  local w, h = bot.screenSize()
  if not w or w <= 0 then w = M.ref_w end
  if not h or h <= 0 then h = M.ref_h end
  R.screen_w = w
  R.screen_h = h
  local sh = h / M.ref_h
  local sw = w / M.ref_w
  local s = (sh + sw) / 2.0
  R.pivot_offset_y_px = math_floor(M.pivot_offset_y * sh + 0.5)
  R.approach_margin_px = math_max(4, math_floor(M.approach_margin_px * s + 0.5))
  R.contain_margin_px = math_max(2, math_floor(M.contain_margin_px * s + 0.5))
  log(string.format("屏幕 %dx%d pivotY=%d approachM=%d", w, h, R.pivot_offset_y_px, R.approach_margin_px))
end

-- ========== 主循环 ==========
log("腾芝洋领主钓鱼辅助启动")
delay(1)
init_scale()

state.last_log_ms = now_ms()
state.fps_frames = 0
state.fps_since_ms = now_ms()

while true do
  local t0 = now_ms()
  local ts = t0 / 1000.0
  local dets = detect_all()
  local infer_ms = now_ms() - t0
  state.fps_frames = state.fps_frames + 1

  local action, msg = "idle", "无检测"
  if dets and #dets > 0 then
    local a, x, y, class, m = analyze(dets, ts)
    apply_decision(a, x, y, class, ts)
    action, msg = a, m
  else
    set_hold(false)
  end

  local tnow = now_ms()
  if tnow - state.last_log_ms >= 500 then
    local elapsed = math_max(1, tnow - state.fps_since_ms)
    local fps = state.fps_frames * 1000.0 / elapsed
    local yud = find_best(dets or {}, "yu")
    local fwd = find_best(dets or {}, "fanwei")
    local sxd = find_best(dets or {}, "shouxian")
    local nyu = yud and 1 or 0
    local nfw = fwd and 1 or 0
    local nsx = sxd and 1 or 0
    local fw_wr = fwd and (dw(fwd) / math_max(1, R.screen_w)) or 0
    local fw_hr = fwd and (dh(fwd) / math_max(1, R.screen_h)) or 0
    log(string.format("fps=%.1f infer=%.0fms hold=%s det[yu=%d fw=%d sx=%d n=%d] fw[wr=%.3f hr=%.3f ok=%s] | %s | %s",
      fps, infer_ms, tostring(state.holding), nyu, nfw, nsx, dets and #dets or 0,
      fw_wr, fw_hr, tostring(state.fanwei_ok), action, msg or ""))
    state.last_log_ms = tnow
    state.fps_frames = 0
    state.fps_since_ms = tnow
  end

  delay(M.loop_sleep)
end
