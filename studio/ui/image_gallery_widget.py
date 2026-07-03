"""工程附件（识图素材）：添加/删除/导出 + 预览 + 复制 findImage 代码。"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QGuiApplication, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from studio.services import lua_snippets
from studio.services.project_images import (
    delete_all_images,
    delete_images,
    export_images,
    image_rel_path,
    import_images,
    list_images,
    resolve_image_dir,
)
from studio.ui.app_theme import set_button_role
from studio.ui.page_shell import hint_label, section_title, tool_button_row


class ZoomImageView(QScrollArea):
    """可滚动的图片预览，滚轮缩放。"""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("ImageZoomView")
        self.setWidgetResizable(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label = QLabel()
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setObjectName("ZoomImageLabel")
        self.setWidget(self._label)
        self._source: Optional[Path] = None
        self._pixmap: Optional[QPixmap] = None
        self._zoom = 1.0
        self._fit_mode = True

    def clear_image(self) -> None:
        self._source = None
        self._pixmap = None
        self._label.setText("选择图片预览")
        self._label.setPixmap(QPixmap())

    def source_path(self) -> Optional[Path]:
        return self._source

    def set_image_file(self, path: Path) -> None:
        pix = QPixmap(str(path))
        if pix.isNull():
            self.clear_image()
            self._label.setText(f"无法加载: {path.name}")
            return
        self._source = path
        self._pixmap = pix
        self._fit_mode = True
        self._apply_zoom()

    def set_fit_mode(self, enabled: bool) -> None:
        self._fit_mode = enabled
        self._apply_zoom()

    def zoom_in(self) -> None:
        self._fit_mode = False
        self._zoom = min(4.0, self._zoom * 1.2)
        self._apply_zoom()

    def zoom_out(self) -> None:
        self._fit_mode = False
        self._zoom = max(0.1, self._zoom / 1.2)
        self._apply_zoom()

    def reset_zoom(self) -> None:
        self._fit_mode = False
        self._zoom = 1.0
        self._apply_zoom()

    def fit_to_view(self) -> None:
        self._fit_mode = True
        self._apply_zoom()

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if self._pixmap is None or self._pixmap.isNull():
            super().wheelEvent(event)
            return
        delta = event.angleDelta().y()
        if delta == 0:
            super().wheelEvent(event)
            return
        self._fit_mode = False
        factor = 1.15 if delta > 0 else 1 / 1.15
        self._zoom = max(0.1, min(4.0, self._zoom * factor))
        self._apply_zoom()
        event.accept()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._fit_mode:
            self._apply_zoom()

    def _apply_zoom(self) -> None:
        if self._pixmap is None or self._pixmap.isNull():
            return
        if self._fit_mode:
            viewport = self.viewport()
            if viewport is None:
                return
            max_w = max(120, viewport.width() - 16)
            max_h = max(120, viewport.height() - 16)
            scaled = self._pixmap.scaled(
                max_w,
                max_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._label.setPixmap(scaled)
            self._label.resize(scaled.size())
            return
        w = max(1, int(self._pixmap.width() * self._zoom))
        h = max(1, int(self._pixmap.height() * self._zoom))
        scaled = self._pixmap.scaled(
            w,
            h,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._label.setPixmap(scaled)
        self._label.resize(scaled.size())


class ImageGalleryWidget(QWidget):
    images_changed = Signal()

    def __init__(self, project_dir_getter: Callable[[], Path | None]) -> None:
        super().__init__()
        self._project_dir_getter = project_dir_getter
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        bar = QHBoxLayout()
        bar.addWidget(section_title("附件"))
        self.path_label = QLabel()
        self.path_label.setObjectName("InfoBar")
        self.path_label.setWordWrap(True)
        bar.addWidget(self.path_label, 1)
        open_dir_btn = QPushButton("打开目录")
        set_button_role(open_dir_btn, "ghost")
        open_dir_btn.clicked.connect(self._open_image_dir)
        bar.addWidget(open_dir_btn)
        root.addLayout(bar)

        tool_button_row(
            root,
            [
                ("添加", self.add_images, "primary"),
                ("删除", self.delete_selected, "danger"),
                ("删除全部", self.delete_all, "ghost"),
                ("导出", self.export_selected, "ghost"),
                ("导出全部", self.export_all, "ghost"),
            ],
            columns=5,
        )

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setObjectName("ImageGallerySplit")

        list_wrap = QWidget()
        list_lay = QVBoxLayout(list_wrap)
        list_lay.setContentsMargins(0, 0, 0, 0)
        list_lay.setSpacing(4)
        list_lay.addWidget(hint_label("双击复制 findImage 代码；Ctrl/Shift 可多选删除"))
        self.thumb_list = QListWidget()
        self.thumb_list.setObjectName("ImageThumbList")
        self.thumb_list.setIconSize(QSize(72, 72))
        self.thumb_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.thumb_list.currentItemChanged.connect(self._on_thumb_changed)
        self.thumb_list.itemDoubleClicked.connect(self._copy_current)
        list_lay.addWidget(self.thumb_list, 1)
        split.addWidget(list_wrap)

        preview_wrap = QWidget()
        preview_lay = QVBoxLayout(preview_wrap)
        preview_lay.setContentsMargins(0, 0, 0, 0)
        preview_lay.setSpacing(4)
        self._viewer = ZoomImageView()
        zoom_bar = QHBoxLayout()
        self.meta_label = QLabel("—")
        self.meta_label.setObjectName("InfoBar")
        self.meta_label.setWordWrap(True)
        zoom_bar.addWidget(self.meta_label, 1)
        for text, slot in [
            ("适应", self._viewer.fit_to_view),
            ("100%", self._viewer.reset_zoom),
            ("放大", self._viewer.zoom_in),
            ("缩小", self._viewer.zoom_out),
        ]:
            btn = QPushButton(text)
            set_button_role(btn, "ghost")
            btn.clicked.connect(slot)
            zoom_bar.addWidget(btn)
        copy_btn = QPushButton("复制 findImage")
        set_button_role(copy_btn, "accent")
        copy_btn.clicked.connect(self._copy_current)
        zoom_bar.addWidget(copy_btn)
        preview_lay.addLayout(zoom_bar)
        preview_lay.addWidget(self._viewer, 1)
        self.usage_label = QLabel()
        self.usage_label.setObjectName("InfoBar")
        self.usage_label.setWordWrap(True)
        self.usage_label.setText(
            "附件说明：图片保存在工程 image/ 目录，脚本中用 bot.findImage(\"image/xxx.png\") 引用。"
            "打包 APK 时会一并打入。"
        )
        preview_lay.addWidget(self.usage_label)
        split.addWidget(preview_wrap)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 3)
        split.setSizes([220, 520])
        root.addWidget(split, 1)

        self._viewer.clear_image()

    def _require_project(self) -> Path | None:
        project = self._project_dir_getter()
        if not project:
            QMessageBox.warning(self, "提示", "请先打开工程")
            return None
        return project

    def _selected_paths(self) -> list[Path]:
        out: list[Path] = []
        for item in self.thumb_list.selectedItems():
            raw = item.data(Qt.ItemDataRole.UserRole)
            if raw:
                out.append(Path(str(raw)))
        return out

    def _notify_changed(self) -> None:
        self.images_changed.emit()

    def on_project_opened(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        project = self._project_dir_getter()
        self.thumb_list.clear()
        self._viewer.clear_image()
        self.meta_label.setText("—")
        if not project:
            self.path_label.setText("（请先打开工程）")
            return
        img_dir = resolve_image_dir(project)
        self.path_label.setText(str(img_dir))
        images = list_images(project)
        if not images:
            self.path_label.setText(f"{img_dir}（暂无附件，可点「添加」或抓抓页截图）")
            return
        for path in images:
            rel = image_rel_path(project, path)
            item = QListWidgetItem(path.name)
            item.setToolTip(rel)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            pix = QPixmap(str(path))
            if not pix.isNull():
                item.setIcon(
                    pix.scaled(
                        72,
                        72,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            self.thumb_list.addItem(item)
        self.thumb_list.setCurrentRow(0)

    def add_images(self) -> None:
        project = self._require_project()
        if project is None:
            return
        start = str(resolve_image_dir(project))
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "添加附件图片",
            start,
            "图片 (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if not paths:
            return
        imported = import_images(project, [Path(p) for p in paths])
        if not imported:
            QMessageBox.warning(self, "添加失败", "未导入任何有效图片（请检查格式或文件是否损坏）")
            return
        self.refresh()
        self._notify_changed()
        names = "\n".join(p.name for p in imported[:8])
        more = f"\n…等共 {len(imported)} 个" if len(imported) > 8 else ""
        QMessageBox.information(self, "添加完成", f"已添加附件:\n{names}{more}")

    def delete_selected(self) -> None:
        project = self._require_project()
        if project is None:
            return
        paths = self._selected_paths()
        if not paths:
            QMessageBox.warning(self, "提示", "请先选择要删除的图片")
            return
        names = "\n".join(p.name for p in paths[:6])
        more = f"\n…等共 {len(paths)} 个" if len(paths) > 6 else ""
        ans = QMessageBox.question(
            self,
            "确认删除",
            f"确定删除以下附件？\n{names}{more}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        n = delete_images(paths)
        self.refresh()
        self._notify_changed()
        QMessageBox.information(self, "完成", f"已删除 {n} 个附件")

    def delete_all(self) -> None:
        project = self._require_project()
        if project is None:
            return
        images = list_images(project)
        if not images:
            QMessageBox.information(self, "提示", "当前没有附件可删除")
            return
        ans = QMessageBox.question(
            self,
            "确认删除全部",
            f"确定删除全部 {len(images)} 个附件？此操作不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        n = delete_all_images(project)
        self.refresh()
        self._notify_changed()
        QMessageBox.information(self, "完成", f"已删除全部 {n} 个附件")

    def export_selected(self) -> None:
        paths = self._selected_paths()
        if not paths:
            QMessageBox.warning(self, "提示", "请先选择要导出的图片")
            return
        if len(paths) == 1:
            src = paths[0]
            dest, _ = QFileDialog.getSaveFileName(
                self,
                "导出附件",
                src.name,
                "图片 (*.png *.jpg *.jpeg *.webp *.bmp)",
            )
            if not dest:
                return
            shutil.copy2(src, dest)
            QMessageBox.information(self, "完成", f"已导出到:\n{dest}")
            return
        dest_dir = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if not dest_dir:
            return
        exported = export_images(paths, Path(dest_dir))
        QMessageBox.information(self, "完成", f"已导出 {len(exported)} 个文件到:\n{dest_dir}")

    def export_all(self) -> None:
        project = self._require_project()
        if project is None:
            return
        images = list_images(project)
        if not images:
            QMessageBox.information(self, "提示", "当前没有附件可导出")
            return
        dest_dir = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if not dest_dir:
            return
        exported = export_images(images, Path(dest_dir))
        QMessageBox.information(self, "完成", f"已导出 {len(exported)} 个文件到:\n{dest_dir}")

    def _on_thumb_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            self._viewer.clear_image()
            self.meta_label.setText("—")
            return
        path = Path(str(current.data(Qt.ItemDataRole.UserRole)))
        project = self._project_dir_getter()
        rel = image_rel_path(project, path) if project else path.name
        try:
            size_kb = path.stat().st_size / 1024
        except OSError:
            size_kb = 0
        pix = QPixmap(str(path))
        if not pix.isNull():
            self.meta_label.setText(f"{rel}\n{pix.width()}×{pix.height()} px · {size_kb:.1f} KB")
        else:
            self.meta_label.setText(rel)
        self._viewer.set_image_file(path)

    def _copy_current(self) -> None:
        project = self._require_project()
        if project is None:
            return
        item = self.thumb_list.currentItem()
        if item is None:
            QMessageBox.warning(self, "提示", "请先选择一张图片")
            return
        path = Path(str(item.data(Qt.ItemDataRole.UserRole)))
        rel = image_rel_path(project, path)
        snippet = lua_snippets.find_image(rel)
        QGuiApplication.clipboard().setText(snippet)
        QMessageBox.information(
            self,
            "已复制",
            f"findImage 代码已复制到剪贴板:\n{rel}\n\n请粘贴到 main.lua",
        )

    def _open_image_dir(self) -> None:
        project = self._require_project()
        if project is None:
            return
        img_dir = resolve_image_dir(project)
        img_dir.mkdir(parents=True, exist_ok=True)
        path_str = str(img_dir)
        try:
            if sys.platform == "win32":
                os.startfile(path_str)  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.run(["open", path_str], check=False)
            else:
                subprocess.run(["xdg-open", path_str], check=False)
        except Exception as exc:
            QMessageBox.warning(self, "打开目录失败", str(exc))
