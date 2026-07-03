from studio.services.layout_clone import clone_layout, clone_widget
from studio.services.screen_layout import active_screen_widgets, editor_widget_list, migrate_layout


def test_clone_layout_independent():
    a = {"panel": {"title": "A"}, "screens": [{"widgets": [{"id": "x"}]}]}
    b = clone_layout(a)
    b["panel"]["title"] = "B"
    assert a["panel"]["title"] == "A"


def test_editor_widget_list_uses_active_screen():
    layout = migrate_layout(
        {
            "version": 3,
            "panel": {"layout_mode": "grid", "active_screen": 0},
            "screens": [
                {"title": "页1", "widgets": [{"id": "a", "type": "input", "label": "A"}]},
            ],
            "widgets": [{"id": "start", "type": "start_script", "label": "运行"}],
        }
    )
    widgets = editor_widget_list(layout)
    assert any(w.get("id") == "a" for w in widgets)
    assert not any(w.get("id") == "start" for w in widgets)
    assert widgets is active_screen_widgets(layout)
