from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QAbstractItemView,
    QProgressBar,
    QDialog,
    QDialogButtonBox,
)

from video_processing import StitchConfig, VideoMeta, format_duration, probe_video, stitch_videos


SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".flv"}
PROJECT_OUTPUT_DIR = Path(r"D:\zll\前端\codex")


class VideoTableWidget(QTableWidget):
    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event):
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        paths = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                paths.append(url.toLocalFile())
        self.files_dropped.emit(paths)
        event.acceptProposedAction()


@dataclass
class OutputDecision:
    target_width: int
    target_height: int
    target_fps: float
    normalize: bool


class OutputConfigDialog(QDialog):
    def __init__(self, videos: list[VideoMeta], parent=None):
        super().__init__(parent)
        self.setWindowTitle("检测到参数不一致")
        self.resize(520, 340)
        self._videos = videos

        resolution_set = sorted({f"{v.width}x{v.height}" for v in videos})
        fps_set = sorted({round(v.fps, 2) for v in videos})
        first = videos[0]

        info = QLabel(
            "您添加的视频参数不一致，请选择输出方案：\n"
            f"分辨率差异：{', '.join(resolution_set)}\n"
            f"帧率差异：{', '.join(str(v) for v in fps_set)} fps"
        )
        info.setWordWrap(True)

        self.recommended_radio = QRadioButton("输出为 1080p / 30FPS（推荐）")
        self.first_radio = QRadioButton(
            f"采用第一个视频参数（{first.width}x{first.height} / {first.fps:.2f} FPS）"
        )
        self.custom_radio = QRadioButton("自定义输出参数")
        self.recommended_radio.setChecked(True)

        self.radio_group = QButtonGroup(self)
        self.radio_group.addButton(self.recommended_radio)
        self.radio_group.addButton(self.first_radio)
        self.radio_group.addButton(self.custom_radio)

        custom_box = QGroupBox("自定义参数")
        custom_layout = QGridLayout(custom_box)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(320, 7680)
        self.width_spin.setValue(1920)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(240, 4320)
        self.height_spin.setValue(1080)
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 240)
        self.fps_spin.setValue(30)
        custom_layout.addWidget(QLabel("宽度"), 0, 0)
        custom_layout.addWidget(self.width_spin, 0, 1)
        custom_layout.addWidget(QLabel("高度"), 1, 0)
        custom_layout.addWidget(self.height_spin, 1, 1)
        custom_layout.addWidget(QLabel("FPS"), 2, 0)
        custom_layout.addWidget(self.fps_spin, 2, 1)
        custom_box.setEnabled(False)
        self.custom_box = custom_box

        self.custom_radio.toggled.connect(self.custom_box.setEnabled)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(info)
        layout.addWidget(self.recommended_radio)
        layout.addWidget(self.first_radio)
        layout.addWidget(self.custom_radio)
        layout.addWidget(custom_box)
        layout.addWidget(buttons)

    def get_decision(self) -> OutputDecision:
        first = self._videos[0]
        if self.recommended_radio.isChecked():
            return OutputDecision(1920, 1080, 30.0, True)
        if self.first_radio.isChecked():
            return OutputDecision(first.width, first.height, float(first.fps), True)
        return OutputDecision(
            self.width_spin.value(),
            self.height_spin.value(),
            float(self.fps_spin.value()),
            True,
        )


class StitchWorker(QThread):
    progress_changed = pyqtSignal(int)
    status_changed = pyqtSignal(str)
    failed = pyqtSignal(str)
    completed = pyqtSignal(str)

    def __init__(self, paths: list[str], output_path: str, config: StitchConfig):
        super().__init__()
        self.paths = paths
        self.output_path = output_path
        self.config = config

    def run(self):
        try:
            stitch_videos(
                input_paths=self.paths,
                output_path=self.output_path,
                config=self.config,
                on_status=self.status_changed.emit,
                on_progress=self.progress_changed.emit,
            )
            self.completed.emit(self.output_path)
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Stitcher - Phase 1")
        self.resize(980, 640)
        self.video_items: list[VideoMeta] = []
        self.worker: StitchWorker | None = None

        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        title = QLabel("AI 视频拼接工具（第一阶段）")
        title.setStyleSheet("font-size: 22px; font-weight: 600;")
        subtitle = QLabel("拖拽或添加视频，调整顺序后开始拼接。")
        subtitle.setStyleSheet("color: #666;")

        self.table = VideoTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["文件名", "时长", "分辨率", "FPS"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.files_dropped.connect(self.add_video_paths)

        buttons_layout = QHBoxLayout()
        self.add_btn = QPushButton("添加视频")
        self.remove_btn = QPushButton("移除选中")
        self.up_btn = QPushButton("上移")
        self.down_btn = QPushButton("下移")
        buttons_layout.addWidget(self.add_btn)
        buttons_layout.addWidget(self.remove_btn)
        buttons_layout.addWidget(self.up_btn)
        buttons_layout.addWidget(self.down_btn)
        buttons_layout.addStretch()

        output_layout = QHBoxLayout()
        default_output_dir = PROJECT_OUTPUT_DIR if PROJECT_OUTPUT_DIR.exists() else Path.cwd()
        self.output_edit = QLineEdit(str(default_output_dir / "output.mp4"))
        self.output_btn = QPushButton("选择输出路径")
        output_layout.addWidget(QLabel("输出文件:"))
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)

        self.start_btn = QPushButton("开始拼接")
        self.start_btn.setMinimumHeight(40)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.status_text = QLabel("等待开始")

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(self.table)
        root.addLayout(buttons_layout)
        root.addLayout(output_layout)
        root.addWidget(self.start_btn)
        root.addWidget(self.progress)
        root.addWidget(self.status_text)

        self.setStatusBar(QStatusBar())

        self.add_btn.clicked.connect(self.on_add_clicked)
        self.remove_btn.clicked.connect(self.on_remove_clicked)
        self.up_btn.clicked.connect(self.on_move_up)
        self.down_btn.clicked.connect(self.on_move_down)
        self.output_btn.clicked.connect(self.on_pick_output)
        self.start_btn.clicked.connect(self.on_start)

    def on_add_clicked(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择视频文件",
            "",
            "Video Files (*.mp4 *.mov *.avi *.mkv *.flv)",
        )
        self.add_video_paths(files)

    def add_video_paths(self, paths: list[str]):
        existing = {os.path.normcase(item.path) for item in self.video_items}
        added = 0
        for path in paths:
            suffix = Path(path).suffix.lower()
            if suffix not in SUPPORTED_EXTENSIONS:
                continue
            normalized = os.path.normcase(path)
            if normalized in existing:
                continue
            try:
                meta = probe_video(path)
            except Exception as exc:
                QMessageBox.warning(self, "读取失败", f"无法读取视频:\n{path}\n\n{exc}")
                continue
            self.video_items.append(meta)
            existing.add(normalized)
            added += 1
        if added:
            self.refresh_table()

    def on_remove_clicked(self):
        row = self.table.currentRow()
        if row < 0:
            return
        self.video_items.pop(row)
        self.refresh_table()

    def on_move_up(self):
        row = self.table.currentRow()
        if row <= 0:
            return
        self.video_items[row - 1], self.video_items[row] = self.video_items[row], self.video_items[row - 1]
        self.refresh_table(selected=row - 1)

    def on_move_down(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.video_items) - 1:
            return
        self.video_items[row + 1], self.video_items[row] = self.video_items[row], self.video_items[row + 1]
        self.refresh_table(selected=row + 1)

    def on_pick_output(self):
        default_output_dir = PROJECT_OUTPUT_DIR if PROJECT_OUTPUT_DIR.exists() else Path.cwd()
        output, _ = QFileDialog.getSaveFileName(
            self,
            "选择输出文件",
            self.output_edit.text().strip() or str(default_output_dir / "output.mp4"),
            "MP4 Files (*.mp4)",
        )
        if output:
            if not output.lower().endswith(".mp4"):
                output += ".mp4"
            output = str((default_output_dir / Path(output).name).resolve())
            self.output_edit.setText(output)

    def refresh_table(self, selected: int | None = None):
        self.table.setRowCount(len(self.video_items))
        for row, item in enumerate(self.video_items):
            self.table.setItem(row, 0, QTableWidgetItem(Path(item.path).name))
            self.table.setItem(row, 1, QTableWidgetItem(format_duration(item.duration)))
            self.table.setItem(row, 2, QTableWidgetItem(f"{item.width}x{item.height}"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{item.fps:.2f}"))
        if selected is not None and 0 <= selected < len(self.video_items):
            self.table.selectRow(selected)

    def _resolve_output_config(self) -> StitchConfig:
        widths = {v.width for v in self.video_items}
        heights = {v.height for v in self.video_items}
        fps_values = {round(v.fps, 2) for v in self.video_items}
        is_consistent = len(widths) == 1 and len(heights) == 1 and len(fps_values) == 1

        if is_consistent:
            first = self.video_items[0]
            return StitchConfig(
                target_width=first.width,
                target_height=first.height,
                target_fps=float(first.fps),
                normalize=False,
            )

        dialog = OutputConfigDialog(self.video_items, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            raise RuntimeError("用户取消了参数配置。")

        decision = dialog.get_decision()
        return StitchConfig(
            target_width=decision.target_width,
            target_height=decision.target_height,
            target_fps=decision.target_fps,
            normalize=decision.normalize,
        )

    def _set_ui_busy(self, busy: bool):
        self.add_btn.setEnabled(not busy)
        self.remove_btn.setEnabled(not busy)
        self.up_btn.setEnabled(not busy)
        self.down_btn.setEnabled(not busy)
        self.output_btn.setEnabled(not busy)
        self.start_btn.setEnabled(not busy)
        self.table.setEnabled(not busy)

    def on_start(self):
        if not self.video_items:
            QMessageBox.information(self, "提示", "请至少添加一个视频文件。")
            return
        output_path = self.output_edit.text().strip()
        if not output_path:
            QMessageBox.warning(self, "提示", "请先设置输出路径。")
            return
        output_dir = PROJECT_OUTPUT_DIR if PROJECT_OUTPUT_DIR.exists() else Path.cwd()
        output_path = str((output_dir / Path(output_path).name).resolve())
        self.output_edit.setText(output_path)

        try:
            config = self._resolve_output_config()
        except RuntimeError as exc:
            self.status_text.setText(str(exc))
            return

        self.progress.setValue(0)
        self.status_text.setText("准备开始处理...")
        self._set_ui_busy(True)

        paths = [item.path for item in self.video_items]
        self.worker = StitchWorker(paths=paths, output_path=output_path, config=config)
        self.worker.progress_changed.connect(self.progress.setValue)
        self.worker.status_changed.connect(self.status_text.setText)
        self.worker.failed.connect(self.on_worker_failed)
        self.worker.completed.connect(self.on_worker_completed)
        self.worker.start()

    def on_worker_failed(self, message: str):
        self._set_ui_busy(False)
        self.status_text.setText("处理失败。")
        QMessageBox.critical(self, "处理失败", message)

    def on_worker_completed(self, output_path: str):
        self._set_ui_busy(False)
        self.status_text.setText("处理完成。")
        self.progress.setValue(100)
        QMessageBox.information(self, "完成", f"视频已输出到:\n{output_path}")


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
