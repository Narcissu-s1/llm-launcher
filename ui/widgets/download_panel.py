import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QProgressBar, QPlainTextEdit, QFileDialog
)
from PySide6.QtCore import QThread, Signal, Qt
from core.config import ConfigStore
from core.hf_downloader import HFDownloader, RemoteFile, HF_ENDPOINT, HF_MIRROR_ENDPOINT
from core.model_library import format_size

class _ScanWorker(QThread):
    done = Signal(list)
    error = Signal(str)

    def __init__(self, downloader: HFDownloader):
        super().__init__()
        self._dl = downloader

    def run(self):
        try:
            files = self._dl.scan()
            self.done.emit(files)
        except Exception as e:
            self.error.emit(str(e))


class _DownloadWorker(QThread):
    progress = Signal(str, int, int)  # filename, downloaded, total
    file_done = Signal(str)
    error = Signal(str)

    def __init__(self, downloader: HFDownloader, files: list, dest: str):
        super().__init__()
        self._dl = downloader
        self._files = files
        self._dest = dest

    def run(self):
        try:
            self._dl.start(
                self._files, self._dest,
                on_progress=lambda fn, d, t: self.progress.emit(fn, d, t),
                on_done=lambda fn: self.file_done.emit(fn),
            )
        except Exception as e:
            self.error.emit(str(e))


class DownloadPanel(QWidget):
    def __init__(self, config: ConfigStore):
        super().__init__()
        self._config = config
        self._remote_files: list[RemoteFile] = []
        self._selected: list[RemoteFile] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        row1 = QHBoxLayout()
        self._repo = QLineEdit(); self._repo.setPlaceholderText("Qwen/Qwen2.5-7B-Instruct-GGUF")
        self._source = QComboBox(); self._source.addItems(["Hugging Face", "HF 镜像", "ModelScope"])
        row1.addWidget(self._repo); row1.addWidget(self._source)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        self._dest = QLineEdit(); self._dest.setText(config.get("app.model_dir") or "")
        self._dest.setPlaceholderText("下载目录")
        btn_dest = QPushButton("选择"); btn_dest.clicked.connect(self._browse_dest)
        btn_scan = QPushButton("扫描"); btn_scan.setObjectName("btnPrimary"); btn_scan.clicked.connect(self._scan)
        row2.addWidget(self._dest); row2.addWidget(btn_dest); row2.addWidget(btn_scan)
        layout.addLayout(row2)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["选择", "文件名", "大小"])
        self._table.cellClicked.connect(self._toggle_row)
        layout.addWidget(self._table)

        self._progress_label = QLabel("")
        self._progress_bar = QProgressBar(); self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_label)
        layout.addWidget(self._progress_bar)

        self._log = QPlainTextEdit(); self._log.setReadOnly(True); self._log.setMaximumHeight(80)
        layout.addWidget(self._log)

        btn_row = QHBoxLayout()
        self._btn_start = QPushButton("开始下载"); self._btn_start.setObjectName("btnPrimary")
        self._btn_start.clicked.connect(self._start)
        btn_row.addStretch(); btn_row.addWidget(self._btn_start)
        layout.addLayout(btn_row)

    def _browse_dest(self):
        d = QFileDialog.getExistingDirectory(self, "选择下载目录")
        if d:
            self._dest.setText(d)

    def _get_endpoint(self):
        src = self._source.currentText()
        if src == "HF 镜像": return HF_MIRROR_ENDPOINT
        if src == "ModelScope": return "modelscope"
        return HF_ENDPOINT

    def _scan(self):
        repo = self._repo.text().strip()
        if not repo:
            return
        endpoint = self._get_endpoint()
        dl = HFDownloader(repo, endpoint)
        self._scan_worker = _ScanWorker(dl)
        self._scan_worker.done.connect(self._on_scan_done)
        self._scan_worker.error.connect(lambda e: self._log.appendPlainText(f"扫描失败: {e}"))
        self._scan_worker.start()
        self._log.appendPlainText(f"扫描 {repo} ...")

    def _on_scan_done(self, files: list):
        self._remote_files = files
        self._table.setRowCount(0)
        for f in files:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem("☐"))
            self._table.setItem(row, 1, QTableWidgetItem(f.path))
            self._table.setItem(row, 2, QTableWidgetItem(format_size(f.size) if f.size else "—"))

    def _toggle_row(self, row, col):
        item = self._table.item(row, 0)
        if item.text() == "☐":
            item.setText("☑")
            if row < len(self._remote_files):
                self._selected.append(self._remote_files[row])
        else:
            item.setText("☐")
            if row < len(self._remote_files):
                f = self._remote_files[row]
                self._selected = [s for s in self._selected if s.path != f.path]

    def _start(self):
        if not self._selected:
            return
        dest = self._dest.text()
        if not dest:
            return
        endpoint = self._get_endpoint()
        dl = HFDownloader(self._repo.text().strip(), endpoint)
        self._dl_worker = _DownloadWorker(dl, self._selected, dest)
        self._dl_worker.progress.connect(self._on_progress)
        self._dl_worker.file_done.connect(lambda fn: self._log.appendPlainText(f"完成: {fn}"))
        self._dl_worker.error.connect(lambda e: self._log.appendPlainText(f"错误: {e}"))
        self._progress_bar.setVisible(True)
        self._dl_worker.start()

    def _on_progress(self, filename: str, downloaded: int, total: int):
        pct = int(downloaded / total * 100) if total > 0 else 0
        self._progress_label.setText(f"{filename}  {format_size(downloaded)} / {format_size(total)}")
        self._progress_bar.setValue(pct)
