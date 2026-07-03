from studio.services.panel_lua_snippets import list_value_widgets, lua_read_snippet


def test_list_value_widgets_from_screens():
    layout = {
        "enabled": True,
        "screens": [
            {
                "title": "页1",
                "widgets": [
                    {"id": "user", "type": "input", "label": "账号"},
                    {"id": "mode", "type": "select", "label": "模式", "options": ["普通", "极速"]},
                ],
            }
        ],
        "widgets": [],
    }
    items = list_value_widgets(layout)
    assert len(items) == 2
    assert items[0]["id"] == "user"
    snippet = lua_read_snippet(items[1])
    assert 'panel.get("mode")' in snippet
    assert "panel.is" in snippet
