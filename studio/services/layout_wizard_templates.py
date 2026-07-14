"""傻瓜式布局向导模板（手机自由 + 主页面表单）。"""

from __future__ import annotations

from typing import Any

from studio.services.layout_clone import clone_layout
from studio.services.screen_layout import migrate_layout, repair_all_screens

_PANEL_BASE: dict[str, Any] = {
    "title": "脚本助手",
    "theme": "light",
    "layout_mode": "free",
    "design_width": 720,
    "design_height": 1280,
    "active_screen": 0,
    "width_mode": "auto",
    "width_dp": 648,
    "height_mode": "wrap",
    "display_mode": "host",
    "auto_collapse_idle_ms": 0,
    "show_on_launch": False,
    "opacity": 0.92,
    "position": "left_center",
    "start_x": 0,
    "start_y": 0,
    "columns": 2,
    "ball_size_dp": 48,
    "show_log": True,
    "log_height_dp": 96,
    "draggable": True,
    "collapsible": True,
    "allow_design": True,
    "start_confirm_collapse": True,
    "height_dp": 1280,
}

WIZARD_CHOICES: list[dict[str, str]] = [
    {
        "key": "login",
        "title": "登录页",
        "desc": "账号 + 密码 + 自动登录开关，适合需要填号的脚本",
    },
    {
        "key": "run",
        "title": "运行设置",
        "desc": "模式 + 间隔 + 循环 + 附加功能，适合挂机类脚本",
    },
    {
        "key": "full",
        "title": "登录 + 设置（推荐）",
        "desc": "两个页签：登录信息 + 运行参数，与 demo 示例一致",
    },
    {
        "key": "remind",
        "title": "提醒 / 定时",
        "desc": "开关 + 时间范围 + 说明，适合打卡提醒、定时任务类",
    },
    {
        "key": "dual",
        "title": "双列参数",
        "desc": "左右两列参数表单，适合模式/优先级等紧凑设置",
    },
]


def _login_screen() -> dict[str, Any]:
    return {
        "title": "账号登录",
        "widgets": [
            {
                "id": "sec_login",
                "type": "section",
                "text": "登录信息",
                "layout_x": 16,
                "layout_y": 16,
                "layout_w": 688,
                "layout_h": 320,
            },
            {
                "id": "hint",
                "type": "text",
                "text": "请填写登录账号信息",
                "text_style": "title",
                "layout_x": 40,
                "layout_y": 64,
                "layout_w": 400,
                "layout_h": 40,
            },
            {
                "id": "account",
                "type": "input",
                "label": "账号",
                "placeholder": "请输入账号",
                "layout_x": 40,
                "layout_y": 120,
                "layout_w": 640,
                "layout_h": 52,
            },
            {
                "id": "password",
                "type": "input",
                "label": "密码",
                "placeholder": "请输入密码",
                "layout_x": 40,
                "layout_y": 188,
                "layout_w": 640,
                "layout_h": 52,
            },
            {
                "id": "auto_login",
                "type": "switch",
                "label": "自动登录",
                "default": "false",
                "layout_x": 40,
                "layout_y": 256,
                "layout_w": 640,
                "layout_h": 44,
            },
        ],
    }


def _run_screen() -> dict[str, Any]:
    return {
        "title": "运行设置",
        "widgets": [
            {
                "id": "sec_run",
                "type": "section",
                "text": "运行参数",
                "layout_x": 16,
                "layout_y": 16,
                "layout_w": 688,
                "layout_h": 420,
            },
            {
                "id": "mode",
                "type": "select",
                "label": "模式",
                "options": ["普通", "极速", "省电"],
                "default": "普通",
                "layout_x": 40,
                "layout_y": 72,
                "layout_w": 320,
                "layout_h": 64,
            },
            {
                "id": "priority",
                "type": "select",
                "label": "优先级",
                "options": ["高", "中", "低"],
                "default": "中",
                "layout_x": 376,
                "layout_y": 72,
                "layout_w": 304,
                "layout_h": 64,
            },
            {
                "id": "delay_sec",
                "type": "stepper",
                "label": "步骤间隔(秒)",
                "default": "2",
                "min": 1,
                "max": 60,
                "step": 1,
                "layout_x": 40,
                "layout_y": 152,
                "layout_w": 320,
                "layout_h": 48,
            },
            {
                "id": "loop_count",
                "type": "stepper",
                "label": "循环次数",
                "default": "1",
                "min": 1,
                "max": 99,
                "step": 1,
                "layout_x": 376,
                "layout_y": 152,
                "layout_w": 304,
                "layout_h": 48,
            },
            {
                "id": "features",
                "type": "multiselect",
                "label": "附加功能",
                "options": ["自动领奖", "自动签到", "跳过动画"],
                "default": "",
                "layout_x": 40,
                "layout_y": 220,
                "layout_w": 640,
                "layout_h": 120,
            },
        ],
    }


def _remind_screen() -> dict[str, Any]:
    return {
        "title": "提醒设置",
        "widgets": [
            {
                "id": "sec_remind",
                "type": "section",
                "text": "上班提醒",
                "layout_x": 16,
                "layout_y": 16,
                "layout_w": 688,
                "layout_h": 220,
            },
            {
                "id": "hint",
                "type": "text",
                "text": "到点提醒并打开钉钉（不会自动打卡）",
                "text_style": "hint",
                "layout_x": 40,
                "layout_y": 64,
                "layout_w": 640,
                "layout_h": 36,
            },
            {
                "id": "remind_on",
                "type": "switch",
                "label": "启用上班提醒",
                "default": "true",
                "layout_x": 40,
                "layout_y": 112,
                "layout_w": 640,
                "layout_h": 48,
            },
            {
                "id": "work_hours",
                "type": "time_range",
                "label": "上班—下班",
                "default_start": "08:55",
                "default_end": "17:30",
                "layout_x": 40,
                "layout_y": 168,
                "layout_w": 640,
                "layout_h": 56,
            },
            {
                "id": "sec_wifi",
                "type": "section",
                "text": "下班 WiFi 离场",
                "layout_x": 16,
                "layout_y": 256,
                "layout_w": 688,
                "layout_h": 220,
            },
            {
                "id": "wifi_hint",
                "type": "text",
                "text": "下班后离开公司 WiFi 时提醒并打开钉钉",
                "text_style": "hint",
                "layout_x": 40,
                "layout_y": 304,
                "layout_w": 640,
                "layout_h": 36,
            },
            {
                "id": "wifi_leave_on",
                "type": "switch",
                "label": "启用离场提醒",
                "default": "true",
                "layout_x": 40,
                "layout_y": 352,
                "layout_w": 640,
                "layout_h": 48,
            },
            {
                "id": "company_wifi",
                "type": "input",
                "label": "公司 WiFi",
                "placeholder": "如 HSYYYL-N28",
                "default": "HSYYYL-N28",
                "layout_x": 40,
                "layout_y": 408,
                "layout_w": 640,
                "layout_h": 52,
            },
        ],
    }


def _dual_screen() -> dict[str, Any]:
    return {
        "title": "参数",
        "widgets": [
            {
                "id": "sec_params",
                "type": "section",
                "text": "运行参数",
                "layout_x": 16,
                "layout_y": 16,
                "layout_w": 688,
                "layout_h": 260,
            },
            {
                "id": "mode",
                "type": "select",
                "label": "模式",
                "options": ["普通", "极速", "省电"],
                "default": "普通",
                "layout_x": 40,
                "layout_y": 72,
                "layout_w": 320,
                "layout_h": 64,
            },
            {
                "id": "priority",
                "type": "select",
                "label": "优先级",
                "options": ["高", "中", "低"],
                "default": "中",
                "layout_x": 376,
                "layout_y": 72,
                "layout_w": 304,
                "layout_h": 64,
            },
            {
                "id": "delay_sec",
                "type": "stepper",
                "label": "间隔(秒)",
                "default": "2",
                "min": 1,
                "max": 60,
                "step": 1,
                "layout_x": 40,
                "layout_y": 152,
                "layout_w": 320,
                "layout_h": 48,
            },
            {
                "id": "loop_count",
                "type": "stepper",
                "label": "循环次数",
                "default": "1",
                "min": 1,
                "max": 99,
                "step": 1,
                "layout_x": 376,
                "layout_y": 152,
                "layout_w": 304,
                "layout_h": 48,
            },
        ],
    }


def build_wizard_layout(key: str, *, panel_title: str = "") -> dict[str, Any]:
    """生成完整 layout.json 结构（已 migrate + repair）。"""
    screens: list[dict[str, Any]]
    title = panel_title.strip() or "脚本助手"
    theme = "light"
    if key == "login":
        screens = [_login_screen()]
        title = panel_title.strip() or "登录助手"
    elif key == "run":
        screens = [_run_screen()]
        title = panel_title.strip() or "运行助手"
    elif key == "full":
        screens = [_login_screen(), _run_screen()]
        title = panel_title.strip() or "脚本助手"
    elif key == "remind":
        screens = [_remind_screen()]
        title = panel_title.strip() or "提醒助手"
        theme = "green"
    elif key == "dual":
        screens = [_dual_screen()]
        title = panel_title.strip() or "参数助手"
        theme = "gray"
    else:
        raise ValueError(f"未知向导模板: {key}")

    raw: dict[str, Any] = {
        "version": 4,
        "enabled": True,
        "panel": {**_PANEL_BASE, "title": title, "theme": theme},
        "screens": clone_layout(screens),
        "widgets": [],
    }
    layout = migrate_layout(raw)
    repair_all_screens(layout)
    return layout


def wizard_screen_for_append(key: str) -> dict[str, Any]:
    """追加模式：返回单个 screen dict。"""
    if key == "login":
        return clone_layout(_login_screen())
    if key == "run":
        return clone_layout(_run_screen())
    if key == "remind":
        return clone_layout(_remind_screen())
    if key == "dual":
        return clone_layout(_dual_screen())
    raise ValueError("完整模板请用「替换全部」模式")
