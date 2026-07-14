"""本机界面片段库。"""

from __future__ import annotations

from studio.services import layout_snippets as sn


def test_save_load_delete_snippet(tmp_path, monkeypatch):
    monkeypatch.setattr(sn, "snippets_root", lambda: tmp_path)
    screen = {
        "title": "登录页",
        "widgets": [
            {"type": "input", "id": "account", "layout_x": 24, "layout_y": 80, "layout_w": 670, "layout_h": 56}
        ],
    }
    path = sn.save_screen_snippet("我的登录", screen)
    assert path.is_file()
    items = sn.list_snippets()
    assert len(items) == 1
    assert items[0]["title"] == "登录页"
    loaded = sn.load_screen_snippet("我的登录")
    assert loaded is not None
    assert loaded["title"] == "登录页"
    assert loaded["widgets"][0]["id"] == "account"
    assert sn.delete_snippet("我的登录")
    assert sn.list_snippets() == []
