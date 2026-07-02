"""标签页嵌套控件可视化编辑。"""



from __future__ import annotations



from typing import Any, Callable, Optional



from PySide6.QtWidgets import (

    QGridLayout,

    QInputDialog,

    QListWidget,

    QListWidgetItem,

    QMenu,

    QPushButton,

    QVBoxLayout,

    QWidget,

)



from studio.ui.app_theme import set_button_role

from studio.ui.page_shell import section_title

from studio.services.layout_defaults import ACTION_TYPES, FORM_WIDGET_TYPES, default_widget, widget_display_name





def _button_grid(buttons: list[tuple[str, object, str]], *, columns: int = 2) -> QWidget:

    wrap = QWidget()

    grid = QGridLayout(wrap)

    grid.setContentsMargins(0, 0, 0, 0)

    grid.setHorizontalSpacing(8)

    grid.setVerticalSpacing(8)

    for i, (text, slot, role) in enumerate(buttons):

        b = QPushButton(text)

        set_button_role(b, role)

        b.clicked.connect(slot)

        b.setMinimumHeight(34)

        grid.addWidget(b, i // columns, i % columns)

    for c in range(columns):

        grid.setColumnStretch(c, 1)

    return wrap





class TabsNestedEditor(QWidget):

    """编辑 tabs 类型控件的 pages 与每页 widgets。"""



    def __init__(self, on_changed: Callable[[], None], parent=None) -> None:

        super().__init__(parent)

        self._on_changed = on_changed

        self._tabs_data: list[dict[str, Any]] = []



        root = QVBoxLayout(self)

        root.setContentsMargins(0, 0, 0, 0)

        root.setSpacing(10)



        root.addWidget(section_title("页签"))

        self.tab_list = QListWidget()

        self.tab_list.setMinimumHeight(72)

        self.tab_list.currentRowChanged.connect(self._on_tab_selected)

        root.addWidget(self.tab_list)

        root.addWidget(

            _button_grid(

                [

                    ("添加页", self._add_tab, "accent"),

                    ("删页", self._remove_tab, "ghost"),

                    ("重命名", self._rename_tab, "ghost"),

                ],

                columns=2,

            )

        )



        root.addWidget(section_title("页内控件"))

        self.widget_list = QListWidget()

        self.widget_list.setMinimumHeight(72)

        root.addWidget(self.widget_list)



        add_w = QPushButton("添加控件")

        set_button_role(add_w, "accent")

        add_w.setMenu(self._build_add_menu())

        add_w.setMinimumHeight(34)

        root.addWidget(add_w)

        root.addWidget(

            _button_grid(

                [

                    ("删除", self._remove_widget, "danger"),

                    ("上移", lambda: self._move_widget(-1), "ghost"),

                    ("下移", lambda: self._move_widget(1), "ghost"),

                ],

                columns=2,

            )

        )



    def set_tabs(self, tabs: list[dict[str, Any]]) -> None:

        import json



        self._tabs_data = json.loads(json.dumps(tabs or []))

        if not self._tabs_data:

            self._tabs_data = [{"title": "页签1", "widgets": []}, {"title": "页签2", "widgets": []}]

        self._refresh_tab_list()

        if self.tab_list.count():

            self.tab_list.setCurrentRow(0)



    def get_tabs(self) -> list[dict[str, Any]]:

        return self._tabs_data



    def _build_add_menu(self) -> QMenu:

        menu = QMenu(self)

        sub_f = menu.addMenu("表单")

        for t, desc in FORM_WIDGET_TYPES:

            if t == "tabs":

                continue

            sub_f.addAction(desc, lambda _c=False, wt=t: self._add_widget(wt))

        sub_a = menu.addMenu("动作")

        for t, desc in ACTION_TYPES:

            sub_a.addAction(desc, lambda _c=False, wt=t: self._add_widget(wt))

        return menu



    def _current_tab_widgets(self) -> Optional[list]:

        row = self.tab_list.currentRow()

        if row < 0 or row >= len(self._tabs_data):

            return None

        return self._tabs_data[row].setdefault("widgets", [])



    def _refresh_tab_list(self) -> None:

        self.tab_list.blockSignals(True)

        self.tab_list.clear()

        for t in self._tabs_data:

            n = len(t.get("widgets") or [])

            self.tab_list.addItem(QListWidgetItem(f"{t.get('title', '页签')} ({n})"))

        self.tab_list.blockSignals(False)



    def _refresh_widget_list(self) -> None:

        self.widget_list.clear()

        widgets = self._current_tab_widgets()

        if widgets is None:

            return

        for w in widgets:

            self.widget_list.addItem(QListWidgetItem(widget_display_name(w)))



    def _on_tab_selected(self, _row: int) -> None:

        self._refresh_widget_list()



    def _add_tab(self) -> None:

        n = len(self._tabs_data) + 1

        self._tabs_data.append({"title": f"页签{n}", "widgets": []})

        self._refresh_tab_list()

        self.tab_list.setCurrentRow(len(self._tabs_data) - 1)

        self._on_changed()



    def _remove_tab(self) -> None:

        row = self.tab_list.currentRow()

        if row < 0 or len(self._tabs_data) <= 1:

            return

        self._tabs_data.pop(row)

        self._refresh_tab_list()

        self.tab_list.setCurrentRow(min(row, len(self._tabs_data) - 1))

        self._on_changed()



    def _rename_tab(self) -> None:

        row = self.tab_list.currentRow()

        if row < 0:

            return

        title, ok = QInputDialog.getText(

            self, "重命名页签", "标题:", text=self._tabs_data[row].get("title", "")

        )

        if ok and title.strip():

            self._tabs_data[row]["title"] = title.strip()

            self._refresh_tab_list()

            self.tab_list.setCurrentRow(row)

            self._on_changed()



    def _add_widget(self, wtype: str) -> None:

        widgets = self._current_tab_widgets()

        if widgets is None:

            return

        widgets.append(default_widget(wtype, len(widgets) + 1))

        self._refresh_tab_list()

        self._refresh_widget_list()

        self.widget_list.setCurrentRow(len(widgets) - 1)

        self._on_changed()



    def _remove_widget(self) -> None:

        widgets = self._current_tab_widgets()

        row = self.widget_list.currentRow()

        if widgets is None or row < 0:

            return

        widgets.pop(row)

        self._refresh_tab_list()

        self._refresh_widget_list()

        self._on_changed()



    def _move_widget(self, delta: int) -> None:

        widgets = self._current_tab_widgets()

        row = self.widget_list.currentRow()

        if widgets is None or row < 0:

            return

        new_row = row + delta

        if new_row < 0 or new_row >= len(widgets):

            return

        widgets[row], widgets[new_row] = widgets[new_row], widgets[row]

        self._refresh_widget_list()

        self.widget_list.setCurrentRow(new_row)

        self._on_changed()

