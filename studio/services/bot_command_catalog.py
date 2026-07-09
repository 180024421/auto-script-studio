"""bot / panel Lua API 命令目录（全部命令浏览、搜索、帮助、插入）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BotCommand:
    id: str
    category: str
    name: str
    api: str
    syntax: str
    description: str
    params_help: str
    keywords: str
    snippet: str

    @property
    def search_blob(self) -> str:
        return " ".join(
            (
                self.id,
                self.category,
                self.name,
                self.api,
                self.syntax,
                self.description,
                self.params_help,
                self.keywords,
            )
        ).lower()


def _commands() -> list[BotCommand]:
    return [
        # —— 触摸 ——
        BotCommand(
            id="bot.delay",
            category="触摸命令",
            name="等待 Delay",
            api="bot.delay",
            syntax="bot.delay(seconds)",
            description="暂停脚本执行指定秒数。",
            params_help="seconds：等待时间（秒，可为小数）。",
            keywords="delay 等待 延时 暂停 sleep",
            snippet="bot.delay(1)",
        ),
        BotCommand(
            id="bot.tap",
            category="触摸命令",
            name="点击 Tap",
            api="bot.tap",
            syntax="bot.tap(x, y)",
            description="在屏幕指定坐标点击一次。",
            params_help="x, y：屏幕像素坐标（整数）。",
            keywords="tap 点击 触控 touch",
            snippet="bot.tap(100, 200)",
        ),
        BotCommand(
            id="bot.swipe",
            category="触摸命令",
            name="滑动 Swipe",
            api="bot.swipe",
            syntax="bot.swipe(x1, y1, x2, y2 [, duration_ms])",
            description="从起点滑动到终点。",
            params_help="x1,y1：起点；x2,y2：终点；duration_ms：时长毫秒（默认 300）。",
            keywords="swipe 滑动 划 drag",
            snippet="bot.swipe(540, 1600, 540, 600, 350)",
        ),
        BotCommand(
            id="bot.longPress",
            category="触摸命令",
            name="长按 LongPress",
            api="bot.longPress",
            syntax="bot.longPress(x, y [, duration_ms])",
            description="在坐标处长按。",
            params_help="x, y：坐标；duration_ms：按住时长毫秒（默认 500）。",
            keywords="longPress 长按 press hold",
            snippet="bot.longPress(100, 200, 800)",
        ),
        # —— 控件 ——
        BotCommand(
            id="bot.findNode",
            category="控件命令",
            name="找控件 FindNode",
            api="bot.findNode",
            syntax="bot.findNode(opts)",
            description="通过无障碍树按文字或 resource-id 查找控件，返回中心坐标。",
            params_help=(
                "opts 表字段：text、id、match_mode（contains/equals/starts_with）、"
                "timeout、index、click=true、optional=true。\n"
                "仅 APK + 无障碍服务可用；PC 调试请设 optional=true。"
            ),
            keywords="findNode 控件 无障碍 node accessibility",
            snippet=(
                'local nx, ny = bot.findNode({ text = "设置", timeout = 10, optional = true })\n'
                "if nx then\n"
                '  bot.log(string.format("控件 (%d,%d)", nx, ny))\n'
                "end"
            ),
        ),
        # —— 颜色 ——
        BotCommand(
            id="bot.findColor",
            category="颜色命令",
            name="找色 FindColor",
            api="bot.findColor",
            syntax="bot.findColor(b, g, r, opts)",
            description="在屏幕中查找与目标 BGR 相近的像素点。",
            params_help=(
                "b,g,r：OpenCV BGR 分量（0–255）；opts：tol 容差、timeout、"
                "roi={x,y,w,h}、click=true、optional=true。"
            ),
            keywords="findColor 找色 color bgr",
            snippet="local cx, cy = bot.findColor(0, 128, 255, { tol = 15, timeout = 10, optional = true })",
        ),
        # —— 图色 ——
        BotCommand(
            id="bot.findImage",
            category="图色命令",
            name="找图 FindImage",
            api="bot.findImage",
            syntax='bot.findImage(path, opts)',
            description="模板匹配找图，返回匹配中心坐标。",
            params_help=(
                "path：工程内模板路径；opts：threshold、timeout、roi、click=true、optional=true；"
                "多尺度：scale_min、scale_max、scale_step（默认 1.0）。"
            ),
            keywords="findImage 找图 template 模板 image scale 多尺度",
            snippet=(
                'local x, y = bot.findImage("image/模板.png", { threshold = 0.9, timeout = 15, '
                "scale_min = 0.9, scale_max = 1.1, scale_step = 0.05, optional = true })\n"
                "if x then bot.log(string.format(\"找图 (%d,%d)\", x, y)) end"
            ),
        ),
        BotCommand(
            id="bot.waitGoneImage",
            category="图色命令",
            name="等待模板消失",
            api="bot.waitGoneImage",
            syntax='bot.waitGoneImage(path, opts)',
            description="轮询直到模板在屏幕上消失或超时。",
            params_help="path：模板路径；opts：threshold、timeout、roi、optional=true。",
            keywords="waitGoneImage 消失 gone 等待",
            snippet=(
                'bot.waitGoneImage("image/loading.png", { threshold = 0.9, timeout = 30, optional = true })'
            ),
        ),
        BotCommand(
            id="bot.waitStable",
            category="图色命令",
            name="等待画面稳定",
            api="bot.waitStable",
            syntax="bot.waitStable(opts)",
            description="连续多帧画面差异低于阈值时认为稳定。",
            params_help="opts：timeout、stable_frames、diff_threshold、roi。",
            keywords="waitStable 稳定 stable 等待",
            snippet="bot.waitStable({ timeout = 15, stable_frames = 3, diff_threshold = 8 })",
        ),
        BotCommand(
            id="bot.findMultiColor",
            category="颜色命令",
            name="多点找色",
            api="bot.findMultiColor",
            syntax="bot.findMultiColor(opts)",
            description="相对偏移的多点颜色同时匹配，返回锚点坐标。",
            params_help=(
                "opts.points：{{dx, dy, {{b,g,r}}}, ...} 相对首点偏移与 BGR；"
                "tol、timeout、roi、click=true。"
            ),
            keywords="findMultiColor 多点 找色 multi color",
            snippet=(
                "local mx, my = bot.findMultiColor({\n"
                "  points = {\n"
                "    {0, 0, {0, 128, 255}},\n"
                "    {10, 0, {0, 120, 250}},\n"
                "  },\n"
                "  tol = 15, timeout = 10, optional = true,\n"
                "})"
            ),
        ),
        # —— 文字 ——
        BotCommand(
            id="bot.findText",
            category="文字命令",
            name="识字定位 FindText",
            api="bot.findText",
            syntax='bot.findText(text, opts)',
            description="OCR 识别屏幕文字并定位目标字符串。",
            params_help=(
                "text：目标文字；opts：match_mode、min_confidence、timeout、roi、click=true。"
            ),
            keywords="findText ocr 识字 文字 text",
            snippet=(
                'local tx, ty = bot.findText("确定", { match_mode = "contains", timeout = 12, optional = true })\n'
                "if tx then bot.log(string.format(\"文字 (%d,%d)\", tx, ty)) end"
            ),
        ),
        BotCommand(
            id="bot.recognizeText",
            category="文字命令",
            name="全屏识字 RecognizeText",
            api="bot.recognizeText",
            syntax="bot.recognizeText(opts)",
            description="识别 ROI 内全部文字，返回列表。",
            params_help=(
                "opts：min_confidence、limit、roi。返回项含 text、x、y、confidence。"
            ),
            keywords="recognizeText ocr 识字 列表",
            snippet=(
                "local hits = bot.recognizeText({ min_confidence = 0.5, limit = 30 })\n"
                "for i, h in ipairs(hits) do\n"
                '  bot.log(string.format("[%d] %s @ (%d,%d)", i, h.text, h.x, h.y))\n'
                "end"
            ),
        ),
        # —— YOLO ——
        BotCommand(
            id="bot.yoloDetect",
            category="YOLO命令",
            name="YOLO 检测",
            api="bot.yoloDetect",
            syntax="bot.yoloDetect(opts)",
            description="对当前屏幕做 YOLO 推理，返回检测框列表。",
            params_help=(
                "opts：model、class_name、conf、roi、limit。\n"
                "每项含 class_name、confidence、x、y、w、h、center_x、center_y；"
                "seg 模型另有 has_mask、mask_center_x/y、mask_area。"
            ),
            keywords="yoloDetect 检测 detect onnx",
            snippet=(
                'local dets = bot.yoloDetect({ model = "models/ui.onnx", conf = 0.35 })\n'
                "for i, d in ipairs(dets) do\n"
                '  bot.log(string.format("%s %.2f", d.class_name, d.confidence))\n'
                "end"
            ),
        ),
        BotCommand(
            id="bot.findYolo",
            category="YOLO命令",
            name="找 YOLO 类",
            api="bot.findYolo",
            syntax="bot.findYolo(opts)",
            description="查找指定 YOLO 类别目标并返回点击坐标。",
            params_help=(
                "opts：model、class_name、conf、pick（best_conf/largest/largest_mask）、frac、"
                "use_mask_center / use_box_center（seg）、mask_decode_max、tap_dx/tap_dy、"
                "click=true、roi、optional。largest_mask 比 best_conf 慢（需解码多个掩码）。"
            ),
            keywords="findYolo yolo 找类 点击 seg mask largest_mask",
            snippet=(
                'local yx, yy = bot.findYolo({ model = "models/ui.onnx", class_name = "hand", '
                "conf = 0.35, use_mask_center = true, pick = \"best_conf\", optional = true })\n"
                "if yx then bot.tap(yx, yy) end"
            ),
        ),
        BotCommand(
            id="bot.yoloSwipe",
            category="YOLO命令",
            name="找类并滑动",
            api="bot.yoloSwipe",
            syntax="bot.yoloSwipe(opts)",
            description="对 YOLO 目标中心执行方向滑动。",
            params_help="opts：model、class_name、direction（up/down/left/right）、distance、duration_ms、frac、roi。",
            keywords="yoloSwipe 滑动 swipe yolo",
            snippet=(
                'bot.yoloSwipe({ model = "models/ui.onnx", class_name = "hand", direction = "up", '
                "distance = 400, duration_ms = 350 })"
            ),
        ),
        # —— 浮动面板 ——
        BotCommand(
            id="panel.get",
            category="浮动面板",
            name="读取控件值",
            api="panel.get",
            syntax='panel.get(widget_id)',
            description="读取浮动面板上控件的当前值。",
            params_help="widget_id：layout.json 中定义的控件 id。",
            keywords="panel get 浮动面板 读取",
            snippet='local mode = panel.get("run_mode")\nbot.log("mode=" .. tostring(mode))',
        ),
        BotCommand(
            id="panel.set",
            category="浮动面板",
            name="设置控件值",
            api="panel.set",
            syntax='panel.set(widget_id, value)',
            description="设置浮动面板控件值（会触发界面更新）。",
            params_help="widget_id：控件 id；value：字符串值。",
            keywords="panel set 浮动面板 设置",
            snippet='panel.set("run_mode", "auto")',
        ),
        BotCommand(
            id="panel.is",
            category="浮动面板",
            name="判断控件值",
            api="panel.is",
            syntax='panel.is(widget_id, expected)',
            description="判断控件当前值是否等于期望值。",
            params_help="widget_id、expected：字符串比较。",
            keywords="panel is 判断 等于",
            snippet='if panel.is("run_mode", "auto") then\n  bot.log("自动模式")\nend',
        ),
        BotCommand(
            id="panel.has",
            category="浮动面板",
            name="判断多选包含",
            api="panel.has",
            syntax='panel.has(widget_id, option)',
            description="判断多选类控件是否包含某选项。",
            params_help="widget_id：控件 id；option：选项值。",
            keywords="panel has 多选 checkbox",
            snippet='if panel.has("features", "blood") then\n  bot.log("已选血压")\nend',
        ),
        BotCommand(
            id="panel.isOn",
            category="浮动面板",
            name="判断开关",
            api="panel.isOn",
            syntax="panel.isOn(widget_id)",
            description="判断开关类控件是否为开启状态。",
            params_help="widget_id：开关控件 id。",
            keywords="panel isOn 开关 toggle",
            snippet='if panel.isOn("auto_fight") then\n  bot.log("自动战斗开")\nend',
        ),
        BotCommand(
            id="panel.getTimeRange",
            category="浮动面板",
            name="读取时间段",
            api="panel.getTimeRange",
            syntax="panel.getTimeRange(widget_id)",
            description="读取时间段控件的起止时间。",
            params_help="返回表 { start = \"HH:MM\", end = \"HH:MM\" }。",
            keywords="panel getTimeRange 时间 段",
            snippet=(
                'local tr = panel.getTimeRange("work_hours")\n'
                'bot.log(tr.start .. " - " .. tr.end)'
            ),
        ),
        BotCommand(
            id="panel.values",
            category="浮动面板",
            name="全部控件值",
            api="panel.values",
            syntax="panel.values()",
            description="返回所有浮动面板控件当前值的表。",
            params_help="无参数；键为 widget_id，值为字符串。",
            keywords="panel values 全部 快照",
            snippet='local all = panel.values()\nfor k, v in pairs(all) do bot.log(k .. "=" .. v) end',
        ),
        BotCommand(
            id="panel.snapshot",
            category="浮动面板",
            name="面板快照",
            api="panel.snapshot",
            syntax="panel.snapshot()",
            description="与 panel.values() 相同，获取面板状态快照。",
            params_help="无参数。",
            keywords="panel snapshot 快照",
            snippet="local snap = panel.snapshot()",
        ),
        BotCommand(
            id="panel.watch",
            category="浮动面板",
            name="监听控件变化",
            api="panel.watch",
            syntax='panel.watch(widget_id, callback)',
            description="注册控件值变化回调（APK 运行时有效）。",
            params_help="callback：function(newValue) … end。",
            keywords="panel watch 监听 回调",
            snippet=(
                'panel.watch("run_mode", function(v)\n'
                '  bot.log("run_mode -> " .. v)\n'
                "end)"
            ),
        ),
        BotCommand(
            id="panel.unwatch",
            category="浮动面板",
            name="取消监听",
            api="panel.unwatch",
            syntax="panel.unwatch(widget_id [, callback])",
            description="取消 panel.watch 注册的监听。",
            params_help="不传 callback 时移除该 id 全部监听。",
            keywords="panel unwatch 取消监听",
            snippet='panel.unwatch("run_mode")',
        ),
        # —— 其它 ——
        BotCommand(
            id="bot.log",
            category="其它",
            name="输出日志 Log",
            api="bot.log",
            syntax='bot.log(message)',
            description="输出日志到运行日志面板。",
            params_help="message：字符串。",
            keywords="log 日志 print 输出",
            snippet='bot.log("hello")',
        ),
        BotCommand(
            id="bot.trace",
            category="其它",
            name="调试 Trace",
            api="bot.trace",
            syntax='bot.trace(tag, message)',
            description="写入带 tag 的 trace 日志，便于过滤调试。",
            params_help="tag：分类标签；message：说明文字。",
            keywords="trace 调试 debug",
            snippet='bot.trace("loop", "进入主循环")',
        ),
    ]


_COMMANDS: list[BotCommand] | None = None


def all_commands() -> list[BotCommand]:
    global _COMMANDS
    if _COMMANDS is None:
        _COMMANDS = _commands()
    return _COMMANDS


def commands_by_category() -> dict[str, list[BotCommand]]:
    out: dict[str, list[BotCommand]] = {}
    for cmd in all_commands():
        out.setdefault(cmd.category, []).append(cmd)
    return out


def find_command(cmd_id: str) -> BotCommand | None:
    for cmd in all_commands():
        if cmd.id == cmd_id:
            return cmd
    return None


def search_commands(query: str) -> list[BotCommand]:
    q = query.strip().lower()
    if not q:
        return all_commands()
    return [c for c in all_commands() if q in c.search_blob]
