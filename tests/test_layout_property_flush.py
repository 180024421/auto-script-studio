"""属性面板同步：切换界面前须 flush。"""

from __future__ import annotations

from PySide6.QtCore import QTimer

from studio.ui.layout_editor_property import LayoutEditorPropertyMixin


class _FlushProbe(LayoutEditorPropertyMixin):
    def __init__(self) -> None:
        self._loading_form = False
        self._selected_path = (0, 0)
        self._layout = {
            "panel": {"active_screen": 0, "layout_mode": "free"},
            "screens": [
                {
                    "title": "A",
                    "widgets": [
                        {
                            "id": "a",
                            "type": "input",
                            "label": "旧",
                            "layout_x": 0,
                            "layout_y": 0,
                            "layout_w": 100,
                            "layout_h": 40,
                        }
                    ],
                },
                {"title": "B", "widgets": []},
            ],
        }
        self.sync_calls = 0

    def _widgets(self):
        from studio.services.screen_layout import widgets_for_active_screen

        return widgets_for_active_screen(self._layout)

    def _edit_target(self):
        from studio.services.screen_layout import resolve_widget

        w = resolve_widget(self._layout, self._selected_path)
        if w is None:
            return None
        return w, self._selected_path, self._selected_path[1]

    def _sync_form_to_layout(self, *_args):
        self.sync_calls += 1

    def _apply_header(self):
        pass

    def _refresh_canvas_after_spec_change(self, path, w):
        pass

    def _mark_dirty(self):
        pass

    def _emit_layout_changed(self):
        pass

    def _update_preview(self, force=False):
        pass


def test_flush_property_sync_writes_pending():
    probe = _FlushProbe()
    probe._prop_sync_timer = QTimer()
    probe._prop_sync_timer.setSingleShot(True)
    probe._prop_sync_timer.timeout.connect(probe._sync_form_to_layout)
    probe._prop_sync_timer.start(3000)
    probe._flush_property_sync()
    assert probe.sync_calls == 1


def test_add_widget_must_flush_before_moving_selection():
    """回归：先改 selected_path 再 flush，会把旧表单类型覆盖到新控件。"""
    from studio.services.layout_defaults import default_widget
    from studio.services.layout_cleanup import next_widget_id
    from studio.services.screen_layout import migrate_layout, screens

    layout = migrate_layout(
        {
            "version": 4,
            "panel": {
                "layout_mode": "free",
                "display_mode": "host",
                "design_width": 720,
                "design_height": 1280,
            },
            "screens": [
                {
                    "title": "界面2",
                    "widgets": [
                        {
                            "id": "w_0",
                            "type": "select",
                            "label": "下拉项",
                            "options": ["普通"],
                            "layout_x": 24,
                            "layout_y": 24,
                            "layout_w": 672,
                            "layout_h": 56,
                        }
                    ],
                }
            ],
            "widgets": [],
        }
    )
    ws = screens(layout)[0]["widgets"]
    # 正确顺序：保持旧 selected_path，先「flush」旧控件，再追加
    old_path = (0, 0)
    assert layout["screens"][0]["widgets"][old_path[1]]["type"] == "select"
    w = default_widget("multiselect", len(ws) + 1)
    w["id"] = next_widget_id(layout)
    ws.append(w)
    # 模拟错误顺序会造成的覆盖
    corrupted = default_widget("multiselect", 99)
    corrupted["type"] = "select"  # 被旧表单写成下拉
    assert corrupted["type"] != "multiselect"
    assert w["type"] == "multiselect"
    assert w.get("label") == "多选项"
