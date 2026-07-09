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
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
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
                "adb-ide 训练的 seg：点「从 adb-ide 导入」或\n"
                "python tools/import_adb_ide_yolo.py --project . --run D:/yolo/runs/xxx"
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
                ("从 adb-ide 导入", self._import_from_adb_ide, "primary"),
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

    def _import_from_adb_ide(self) -> None:
        project = self._require_project()
        if project is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 adb-ide 训练权重 best.pt",
            "",
            "YOLO 权重 (*.pt);;全部 (*.*)",
        )
        if not path:
            run_dir = QFileDialog.getExistingDirectory(self, "或选择训练 run 目录（含 weights/best.pt）")
            if not run_dir:
                return
            path = run_dir

        dlg = QDialog(self)
        dlg.setWindowTitle("从 adb-ide 导入 seg/detect")
        form = QFormLayout(dlg)
        imgsz_sp = QSpinBox()
        imgsz_sp.setRange(256, 640)
        imgsz_sp.setSingleStep(32)
        imgsz_sp.setValue(320)
        imgsz_sp.setToolTip("移动端推荐 320（几十 ms）；adb-ide 训练常为 640")
        form.addRow("导出 imgsz：", imgsz_sp)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            from studio.services.adb_ide_import import import_adb_ide_yolo

            result = import_adb_ide_yolo(
                project,
                Path(path),
                imgsz=imgsz_sp.value(),
                set_default=True,
                apply_preset="yolo_seg_fast" if imgsz_sp.value() <= 320 else None,
            )
        except Exception as exc:
            QMessageBox.critical(self, "导入失败", str(exc))
            return

        self.refresh()
        self.models_changed.emit()
        QMessageBox.information(
            self,
            "导入完成",
            f"任务: {result.get('task')}\n"
            f"ONNX: {result.get('onnx')}\n"
            f"imgsz: {result.get('imgsz')}\n"
            f"默认模型: {result.get('default_model')}\n\n"
            f"{result.get('hint', '')}",
        )

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
        paths = [Path(f) for f in files]
        export_imgsz: int | None = None
        if any(p.suffix.lower() == ".pt" for p in paths):
            from PySide6.QtWidgets import QInputDialog

            choice = QMessageBox.question(
                self,
                "导入 .pt",
                "检测到 PyTorch 权重。APK 需 ONNX，是否一并导出为 imgsz=320 的 ONNX？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            )
            if choice == QMessageBox.StandardButton.Cancel:
                return
            if choice == QMessageBox.StandardButton.Yes:
                export_imgsz = 320
        imported = import_models(project, paths, export_onnx_imgsz=export_imgsz)
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
        meta_lines = [
            f"{rel}",
            f"{path.suffix} · {size_kb:.1f} KB",
        ]
        if path.suffix.lower() == ".onnx":
            try:
                from studio.services.onnx_inspect import inspect_onnx

                info = inspect_onnx(path)
                task = info.get("task", "?")
                outs = info.get("outputs", 0)
                meta_lines.append(f"类型: {task} · 输出数: {outs}")
                if info.get("input_shape"):
                    meta_lines.append(f"输入: {info['input_shape']}")
            except Exception:
                pass
        meta_lines.append(
            f"labels: {labels.name}" if labels.is_file() else "（无 labels 文件）"
        )
        self.meta_label.setText("\n".join(meta_lines))
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
