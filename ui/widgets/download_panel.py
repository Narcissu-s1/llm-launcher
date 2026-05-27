import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QProgressBar, QPlainTextEdit, QFileDialog
)
from PySide6.QtCore import Signal
from core.config import ConfigStore
from core.hf_downloader import HFDownloader, RemoteFile, DownloadTask, HF_ENDPOINT, HF_MIRROR_ENDPOINT
from core.model_library import format_size


class DownloadPanel(QWidget):
    def __init__(self, config: ConfigStore):
        super().__init__()
        self._config = config
        self._remote_files: list[RemoteFile] = []
        self._selected: list[RemoteFile] = []
        self._dl = HFDownloader()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        row1 = QHBoxLayout()
        self._repo = QLineEdit()
        self._repo.setPlaceholderText("Qwen/Qwen2.5-7B-Instruct-GGUF")
        self._source = QComboBox()
        self._source.addItems(["Hugging Face", "HF 镜像", "ModelScope"])
        row1.addWidget(self._repo)
        row1.addWidget(self._source)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        self._dest = QLineEdit()
        self._dest.setText(config.get("app.model_dir") or "")
        self._dest.setPlaceholderText("下载目录")
        btn_dest = QPushButton("选择")
        btn_dest.clicked.connect(self._browse_dest)
        btn_scan = QPushButton("扫描")
        btn_scan.setObjectName("btnPrimary")
        btn_scan.clicked.connect(self._scan)
        row2.addWidget(self._dest)
        row2.addWidget(btn_dest)
        row2.addWidget(btn_scan)
        layout.addLayout(row2)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["选择", "文件名", "大小"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.cellClicked.connect(self._toggle_row)
        layout.addWidget(self._table)

        self._progress_label = QLabel("")
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_label)
        layout.addWidget(self._progress_bar)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(120)
        layout.addWidget(self._log)

        btn_row = QHBoxLayout()
        self._btn_copy_log = QPushButton("复制日志")
        self._btn_copy_log.clicked.connect(self._copy_log)
        self._btn_start = QPushButton("开始下载")
        self._btn_start.setObjectName("btnPrimary")
        self._btn_start.clicked.connect(self._start)
        btn_row.addWidget(self._btn_copy_log)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_start)
        layout.addLayout(btn_row)

    def _browse_dest(self):
        d = QFileDialog.getExistingDirectory(self, "选择下载目录")
        if d:
            self._dest.setText(d)

    def _get_source_params(self):
        src = self._source.currentText()
        if src == "HF 镜像":
            return HF_MIRROR_ENDPOINT, "hf"
        if src == "ModelScope":
            return HF_ENDPOINT, "modelscope"
        return HF_ENDPOINT, "hf"

    def _log_msg(self, msg: str):
        self._log.appendPlainText(msg)

    def _scan(self):
        repo = self._repo.text().strip()
        if not repo:
            return
        self._log.clear()
        self._table.setRowCount(0)
        self._remote_files.clear()
        self._selected.clear()
        endpoint, source = self._get_source_params()
        self._log_msg(f"扫描 {repo} ...")
        self._dl.scan(
            repo_id=repo,
            on_done=self._on_scan_done,
            on_log=self._log_msg,
            endpoint=endpoint,
            source=source,
        )

    def _on_scan_done(self, result):
        if isinstance(result, Exception):
            self._log_msg(f"扫描失败: {result}")
            return
        self._remote_files = result
        self._table.setRowCount(0)
        for f in self._remote_files:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem("☐"))
            self._table.setItem(row, 1, QTableWidgetItem(f.name))
            self._table.setItem(row, 2, QTableWidgetItem(format_size(f.size) if f.size else "—"))

    def _toggle_row(self, row, col):
        item = self._table.item(row, 0)
        if row >= len(self._remote_files):
            return
        f = self._remote_files[row]
        if item.text() == "☐":
            item.setText("☑")
            self._selected.append(f)
        else:
            item.setText("☐")
            self._selected = [s for s in self._selected if s.path != f.path]

    def _on_progress(self, task: DownloadTask):
        pct = int(task.downloaded / task.total * 100) if task.total > 0 else 0
        self._progress_label.setText(
            f"{task.filename}  {format_size(task.downloaded)} / {format_size(task.total)}"
        )
        self._progress_bar.setValue(pct)

    def _on_done(self, tasks: list):
        ok = sum(1 for t in tasks if t.status == "done")
        fail = sum(1 for t in tasks if t.status == "error")
        self._log_msg(f"下载完成：{ok} 成功，{fail} 失败")
        self._progress_bar.setVisible(False)

    def _start(self):
        if not self._selected:
            return
        dest = self._dest.text().strip()
        if not dest:
            return
        repo = self._repo.text().strip()
        endpoint, source = self._get_source_params()
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._log_msg(f"开始下载 {len(self._selected)} 个文件...")
        self._dl.start(
            files=self._selected,
            repo_id=repo,
            save_dir=dest,
            on_progress=self._on_progress,
            on_done=self._on_done,
            on_log=self._log_msg,
            endpoint=endpoint,
            source=source,
        )

    def _copy_log(self):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._log.toPlainText())
