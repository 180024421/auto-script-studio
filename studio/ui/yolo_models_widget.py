"""工程 YOLO 模型管理：导入/删除/导出、编辑 labels、设默认模型。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from studio.services.yolo_models import (
    delete_models,
    export_models,
    import_models,
    labels_path_for,
    list_yolo_models,
    load_class_names,
    model_rel_path,
    models_dir,
    read_default_model_rel,
    save_labels,
    set_default_model,
)
from studio.ui.app_theme import set_button_role
from studio.ui.page_shell import hint_label, section_title, tool_button_row


class YoloModelsWidget(QWidget):
    models_changed = Signal()

    def __init__(self, project_dir_getter: Callable[[], Path | None]) -> None:
        super().__init__()
        self._project_dir_getter = project_dir_getter
        self._current_model: Optional[Path] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)
        root.addWidget(section_title("YOLO 模型"))
        root.addWidget(
            hint_label(
                "APK 运行需 models/*.onnx + 同名 .labels。\n"
                "导出：python tools/export_yolo_onnx.py --pt best.pt --out models/ui"
            )
        )

        split = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        self.model_list = QListWidget()
        self.model_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.model_list.currentItemChanged.connect(self._on_model_selected)
        left_lay.addWidget(self.model_list, 1)
        tool_button_row(
            left_lay,
            [
                ("导入模型", self._import_models, "accent"),
                ("删除", self._delete_selected, "ghost"),
                ("导出", self._export_selected, "ghost"),
            ],
            columns=1,
        )
        tool_button_row(
            left_lay,
            [
                ("设为默认", self._set_default, "primary"),
                ("打开目录", self._open_models_dir, "ghost"),
            ],
            columns=1,
        )
        self.default_label = QLabel("默认模型：—")
        self.default_label.setObjectName("InfoBar")
        self.default_label.setWordWrap(True)
        left_lay.addWidget(self.default_label)
        split.addWidget(left)

        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.addWidget(section_title("类别 labels"))
        self.meta_label = QLabel("—")
        self.meta_label.setObjectName("InfoBar")
        self.meta_label.setWordWrap(True)
        right_lay.addWidget(self.meta_label)
        self.labels_edit = QPlainTextEdit()
        self.labels_edit.setPlaceholderText("每行一个类别名，保存后写入 模型名.labels")
        right_lay.addWidget(self.labels_edit, 1)
        btn_row = QHBoxLayout()
        save_labels_btn = QPushButton("保存 labels")
        set_button_role(save_labels_btn, "accent")
        save_labels_btn.clicked.connect(self._save_labels)
        reload_btn = QPushButton("重新加载")
        set_button_role(reload_btn, "ghost")
        reload_btn.clicked.connect(self._reload_labels)
        btn_row.addWidget(save_labels_btn)
        btn_row.addWidget(reload_btn)
        btn_row.addStretch()
        right_lay.addLayout(btn_row)
        split.addWidget(right)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 3)
        root.addWidget(split, 1)

    def on_project_opened(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        project = self._project_dir_getter()
        self.model_list.clear()
        self._current_model = None
        self.labels_edit.clear()
        self.meta_label.setText("—")
        if not project:
            self.default_label.setText("默认模型：—")
            return
        default_rel = read_default_model_rel(Path(project))
        self.default_label.setText(f"默认模型：{default_rel or '（未设置）'}")
        for path in list_yolo_models(Path(project)):
            rel = model_rel_path(Path(project), path)
            item = QListWidgetItem(path.name)
            item.setToolTip(str(path))
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            if rel == default_rel:
                item.setText(f"★ {path.name}")
            self.model_list.addItem(item)

    def _require_project(self) -> Path | None:
        project = self._project_dir_getter()
        if not project:
            QMessageBox.warning(self, "提示", "请先打开工程")
            return None
        return Path(project)

    def _selected_paths(self) -> list[Path]:
        paths: list[Path] = []
        for item in self.model_list.selectedItems():
            paths.append(Path(str(item.data(Qt.ItemDataRole.UserRole))))
        return paths

    def _import_models(self) -> None:
        project = self._require_project()
        if project is None:
            return
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "导入 YOLO 模型",
            "",
            "YOLO 模型 (*.onnx *.pt)",
        )
        if not files:
            return
        imported = import_models(project, [Path(f) for f in files])
        if not imported:
            QMessageBox.warning(self, "提示", "未导入有效模型")
            return
        self.refresh()
        self.models_changed.emit()
        QMessageBox.information(self, "完成", f"已导入 {len(imported)} 个模型到 models/")

    def _delete_selected(self) -> None:
        project = self._require_project()
        if project is None:
            return
        paths = self._selected_paths()
        if not paths:
            QMessageBox.warning(self, "提示", "请先选择模型")
            return
        if (
            QMessageBox.question(self, "确认删除", f"删除 {len(paths)} 个模型及 labels？")
            != QMessageBox.StandardButton.Yes
        ):
            return
        delete_models(paths)
        self.refresh()
        self.models_changed.emit()

    def _export_selected(self) -> None:
        paths = self._selected_paths()
        if not paths:
            QMessageBox.warning(self, "提示", "请先选择模型")
            return
        dest = QFileDialog.getExistingDirectory(self, "导出到目录")
        if not dest:
            return
        exported = export_models(paths, Path(dest))
        QMessageBox.information(self, "完成", f"已导出 {len(exported)} 个文件")

    def _set_default(self) -> None:
        project = self._require_project()
        if project is None:
            return
        item = self.model_list.currentItem()
        if item is None:
            QMessageBox.warning(self, "提示", "请先选择一个模型")
            return
        path = Path(str(item.data(Qt.ItemDataRole.UserRole)))
        rel = model_rel_path(project, path)
        set_default_model(project, rel)
        self.refresh()
        self.models_changed.emit()
        QMessageBox.information(self, "完成", f"已设默认模型:\n{rel}")

    def _open_models_dir(self) -> None:
        project = self._require_project()
        if project is None:
            return
        d = models_dir(project)
        d.mkdir(parents=True, exist_ok=True)
        path_str = str(d)
        try:
            if sys.platform == "win32":
                os.startfile(path_str)  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.run(["open", path_str], check=False)
            else:
                subprocess.run(["xdg-open", path_str], check=False)
        except Exception as exc:
            QMessageBox.warning(self, "打开失败", str(exc))

    def _on_model_selected(self, current: QListWidgetItem | None, _prev) -> None:
        if current is None:
            self._current_model = None
            self.labels_edit.clear()
            self.meta_label.setText("—")
            return
        path = Path(str(current.data(Qt.ItemDataRole.UserRole)))
        self._current_model = path
        project = self._project_dir_getter()
        rel = model_rel_path(Path(project), path) if project else path.name
        labels = labels_path_for(path)
        try:
            size_kb = path.stat().st_size / 1024
        except OSError:
            size_kb = 0
        self.meta_label.setText(
            f"{rel}\n{path.suffix} · {size_kb:.1f} KB"
            + (f"\nlabels: {labels.name}" if labels.is_file() else "\n（无 labels 文件）")
        )
        self._reload_labels()

    def _reload_labels(self) -> None:
        if self._current_model is None:
            return
        names = load_class_names(self._current_model)
        self.labels_edit.setPlainText("\n".join(names))

    def _save_labels(self) -> None:
        if self._current_model is None:
            QMessageBox.warning(self, "提示", "请先选择模型")
            return
        lines = [ln.strip() for ln in self.labels_edit.toPlainText().splitlines() if ln.strip()]
        out = save_labels(self._current_model, lines)
        self.models_changed.emit()
        QMessageBox.information(self, "完成", f"已保存:\n{out.name}")
