"""全部命令：树形浏览、搜索、帮助说明、插入（对齐按键精灵手机助手）。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from studio.services.bot_command_catalog import BotCommand, all_commands, commands_by_category
from studio.ui.app_theme import set_button_role
from studio.ui.page_shell import hint_label, section_title


class ScriptAllCommandsWidget(QWidget):
    insert_code = Signal(str)
    copy_code = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._cmd_by_id: dict[str, BotCommand] = {}
        self._selected: BotCommand | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索命令（tap、找图、YOLO、panel…）")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search)
        root.addWidget(self.search_edit)

        split = QSplitter(Qt.Orientation.Vertical)
        split.setChildrenCollapsible(False)

        tree_wrap = QWidget()
        tree_lay = QVBoxLayout(tree_wrap)
        tree_lay.setContentsMargins(0, 0, 0, 0)
        tree_lay.setSpacing(4)
        tree_lay.addWidget(section_title("命令列表"))
        self.tree = QTreeWidget()
        self.tree.setObjectName("AllCommandsTree")
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.currentItemChanged.connect(self._on_tree_selection)
        tree_lay.addWidget(self.tree, 1)
        split.addWidget(tree_wrap)

        help_wrap = QFrame()
        help_wrap.setObjectName("CommandHelpPanel")
        help_lay = QVBoxLayout(help_wrap)
        help_lay.setContentsMargins(8, 8, 8, 8)
        help_lay.setSpacing(6)
        help_lay.addWidget(section_title("帮助"))
        self.help_view = QTextBrowser()
        self.help_view.setObjectName("CommandHelpView")
        self.help_view.setOpenExternalLinks(False)
        self.help_view.setMinimumHeight(120)
        help_lay.addWidget(self.help_view, 1)

        btn_row = QHBoxLayout()
        self.insert_btn = QPushButton("插入")
        set_button_role(self.insert_btn, "accent")
        self.insert_btn.setEnabled(False)
        self.insert_btn.clicked.connect(self._insert)
        copy_btn = QPushButton("复制")
        set_button_role(copy_btn, "ghost")
        copy_btn.setEnabled(False)
        copy_btn.clicked.connect(self._copy)
        self._copy_btn = copy_btn
        btn_row.addWidget(self.insert_btn)
        btn_row.addWidget(copy_btn)
        btn_row.addStretch()
        help_lay.addLayout(btn_row)
        split.addWidget(help_wrap)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        split.setSizes([220, 180])
        root.addWidget(split, 1)

        root.addWidget(
            hint_label("选中叶子命令查看说明 · 复杂参数可在「基本命令」Tab 可视化配置"),
        )

        self._build_tree()
        self._show_placeholder()

    def _build_tree(self) -> None:
        self.tree.clear()
        self._cmd_by_id.clear()
        for category, cmds in commands_by_category().items():
            cat_item = QTreeWidgetItem([category])
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            cat_item.setData(0, Qt.ItemDataRole.UserRole, "")
            font = cat_item.font(0)
            font.setBold(True)
            cat_item.setFont(0, font)
            for cmd in cmds:
                leaf = QTreeWidgetItem([f"{cmd.name}"])
                leaf.setData(0, Qt.ItemDataRole.UserRole, cmd.id)
                leaf.setToolTip(0, cmd.api)
                cat_item.addChild(leaf)
                self._cmd_by_id[cmd.id] = cmd
            self.tree.addTopLevelItem(cat_item)
            cat_item.setExpanded(True)

    def _on_search(self, text: str) -> None:
        q = text.strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            cat = self.tree.topLevelItem(i)
            if cat is None:
                continue
            cat_visible = False
            for j in range(cat.childCount()):
                child = cat.child(j)
                if child is None:
                    continue
                cmd_id = str(child.data(0, Qt.ItemDataRole.UserRole) or "")
                cmd = self._cmd_by_id.get(cmd_id)
                match = not q or (cmd is not None and q in cmd.search_blob)
                child.setHidden(not match)
                if match:
                    cat_visible = True
            cat.setHidden(not cat_visible)
            if cat_visible:
                cat.setExpanded(True)

    def _on_tree_selection(self, current: QTreeWidgetItem | None, _prev) -> None:
        if current is None:
            self._selected = None
            self._show_placeholder()
            return
        cmd_id = str(current.data(0, Qt.ItemDataRole.UserRole) or "")
        cmd = self._cmd_by_id.get(cmd_id)
        if cmd is None:
            self._selected = None
            self._show_placeholder()
            return
        self._selected = cmd
        self._show_help(cmd)
        self.insert_btn.setEnabled(True)
        self._copy_btn.setEnabled(True)

    def _show_placeholder(self) -> None:
        self.help_view.setHtml(
            "<p style='color:#64748b'>在上方树中选择一条命令，查看功能说明与语法。</p>"
        )
        self.insert_btn.setEnabled(False)
        self._copy_btn.setEnabled(False)

    def _show_help(self, cmd: BotCommand) -> None:
        params = cmd.params_help.replace("\n", "<br>")
        self.help_view.setHtml(
            f"<p><b>命令名称</b><br>{cmd.name} · <code>{cmd.api}</code></p>"
            f"<p><b>命令功能</b><br>{cmd.description}</p>"
            f"<p><b>语法格式</b><br><code>{cmd.syntax}</code></p>"
            f"<p><b>参数说明</b><br>{params}</p>"
            f"<p><b>分类</b> {cmd.category}</p>"
        )

    def _insert(self) -> None:
        if self._selected:
            self.insert_code.emit(self._selected.snippet)

    def _copy(self) -> None:
        if self._selected:
            self.copy_code.emit(self._selected.snippet)
