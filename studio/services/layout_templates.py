"""浮动面板布局模板库。"""

from __future__ import annotations

from typing import Any

LAYOUT_TEMPLATES: dict[str, dict[str, Any]] = {
    "battle": {
        "name": "战斗挂机",
        "description": "模式单选 + 多选任务 + 开始/停止",
        "layout": {
            "version": 2,
            "enabled": True,
            "panel": {
                "title": "战斗助手",
                "theme": "light",
                "width_dp": 240,
                "columns": 2,
                "show_log": True,
            },
            "widgets": [
                {"id": "lbl_b", "type": "label", "text": "战斗配置", "width": 2},
                {
                    "id": "battle_mode",
                    "type": "radio",
                    "label": "模式",
                    "options": ["普通", "极速", "省电"],
                    "default": "普通",
                    "width": 2,
                },
                {
                    "id": "battle_tasks",
                    "type": "multiselect",
                    "label": "任务",
                    "options": ["主线", "日常", "副本"],
                    "default": "日常",
                    "width": 2,
                },
                {"id": "start", "type": "start_script", "label": "开始", "color": "#2563EB", "width": 1},
                {"id": "stop", "type": "stop_script", "label": "停止", "color": "#DC2626", "width": 1},
                {"id": "collapse", "type": "collapse", "label": "收起", "color": "#64748B", "width": 2},
            ],
        },
    },
    "daily": {
        "name": "日常任务",
        "description": "标签页：签到 / 领奖 + 延迟输入",
        "layout": {
            "version": 2,
            "enabled": True,
            "panel": {
                "title": "日常助手",
                "theme": "light",
                "width_dp": 260,
                "columns": 2,
            },
            "widgets": [
                {
                    "id": "daily_tabs",
                    "type": "tabs",
                    "width": 2,
                    "tabs": [
                        {
                            "title": "签到",
                            "widgets": [
                                {
                                    "id": "sign_run",
                                    "type": "lua",
                                    "label": "一键签到",
                                    "color": "#0D9488",
                                    "width": 2,
                                    "lua": 'bot.log("签到")',
                                },
                            ],
                        },
                        {
                            "title": "领奖",
                            "widgets": [
                                {
                                    "id": "claim_run",
                                    "type": "lua",
                                    "label": "领取奖励",
                                    "color": "#D97706",
                                    "width": 2,
                                    "lua": 'bot.log("领奖")',
                                },
                            ],
                        },
                    ],
                },
                {
                    "id": "loop_delay",
                    "type": "input",
                    "label": "循环延迟(ms)",
                    "default": "1000",
                    "min": 100,
                    "max": 60000,
                    "required": True,
                    "width": 2,
                },
                {"id": "start", "type": "start_script", "label": "运行脚本", "color": "#2563EB", "width": 2},
            ],
        },
    },
    "settings": {
        "name": "参数设置",
        "description": "下拉 + 输入校验 + 应用按钮",
        "layout": {
            "version": 2,
            "enabled": True,
            "panel": {
                "title": "设置",
                "theme": "light",
                "width_dp": 220,
                "columns": 2,
            },
            "widgets": [
                {
                    "id": "env",
                    "type": "select",
                    "label": "环境",
                    "options": ["正式", "测试"],
                    "default": "正式",
                    "width": 2,
                },
                {
                    "id": "retry",
                    "type": "input",
                    "label": "重试次数",
                    "default": "3",
                    "min": 1,
                    "max": 20,
                    "required": True,
                    "width": 2,
                },
                {
                    "id": "apply",
                    "type": "lua",
                    "label": "应用设置",
                    "color": "#2563EB",
                    "width": 2,
                    "lua": 'bot.log("env=" .. panel.get("env") .. " retry=" .. panel.get("retry"))',
                },
            ],
        },
    },
}


def template_choices() -> list[tuple[str, str]]:
    return [(k, f"{v['name']} — {v['description']}") for k, v in LAYOUT_TEMPLATES.items()]


def get_template(key: str) -> dict[str, Any] | None:
    item = LAYOUT_TEMPLATES.get(key)
    if not item:
        return None
    import json

    return json.loads(json.dumps(item["layout"]))
