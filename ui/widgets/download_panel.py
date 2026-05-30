import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QProgressBar, QPlainTextEdit, QFileDialog, QCheckBox, QHeaderView,
    QListWidget, QListWidgetItem, QAbstractItemView,
)
from PySide6.QtCore import Signal, Qt
from core.config import ConfigStore
from core.hf_downloader import (
    HFDownloader, RemoteFile, DownloadTask, SearchResult,
    HF_ENDPOINT, HF_MIRROR_ENDPOINT,
)
from core.model_library import format_size


def _format_downloads(n: int) -> str:
    """格式化下载量"""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


class DownloadPanel(QWidget):
    # 跨线程安全信号
    _sig_scan_done = Signal(object)   # list[RemoteFile] | Exception
    _sig_progress  = Signal(object)   # DownloadTask
    _sig_done      = Signal(object)   # list[DownloadTask]
    _sig_log       = Signal(str)
    _sig_search_done = Signal(object) # list[SearchResult] | Exception

    def __init__(self, config: ConfigStore):
        super().__init__()
        self._config = config
        self._remote_files: list[RemoteFile] = []
        self._dl = HFDownloader()

        # 连接跨线程信号到主线程槽
        self._sig_scan_done.connect(self._on_scan_done)
        self._sig_progress.connect(self._on_progress)
        self._sig_done.connect(self._on_done)
        self._sig_log.connect(self._log_msg)
        self._sig_search_done.connect(self._on_search_done)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # 搜索行
        search_row = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索模型仓库，返回下载量前 50")
        self._search_input.returnPressed.connect(self._search)
        self._btn_search = QPushButton("搜索")
        self._btn_search.clicked.connect(self._search)
        search_row.addWidget(self._search_input)
        search_row.addWidget(self._btn_search)
        layout.addLayout(search_row)

        # 搜索结果列表（默认隐藏）
        self._search_results = QListWidget()
        self._search_results.setMaximumHeight(150)
        self._search_results.setVisible(False)
        self._search_results.itemDoubleClicked.connect(self._on_search_selected)
        layout.addWidget(self._search_results)

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

        # 列：选择（复选框）/ 文件名 / 大小
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["选择", "文件名", "大小"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(0, 50)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(2, 80)
        self._table.verticalHeader().setVisible(False)
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
        self._btn_cancel = QPushButton("取消")
        self._btn_cancel.setObjectName("btnStop")
        self._btn_cancel.setEnabled(False)
        self._btn_cancel.clicked.connect(self._cancel)
        self._btn_start = QPushButton("开始下载")
        self._btn_start.setObjectName("btnPrimary")
        self._btn_start.clicked.connect(self._start)
        btn_row.addWidget(self._btn_copy_log)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_cancel)
        btn_row.addWidget(self._btn_start)
        layout.addLayout(btn_row)

    def _browse_dest(self):
        d = QFileDialog.getExistingDirectory(self, "选择下载目录", self._dest.text())
        if d:
            self._dest.setText(d)
            self._config.set("app.model_dir", d)

    def _get_source_params(self):
        idx = self._source.currentIndex()
        if idx == 1:
            return HF_MIRROR_ENDPOINT, "hf"
        if idx == 2:
            return "", "modelscope"
        return HF_ENDPOINT, "hf"

    def _log_msg(self, msg: str):
        self._log.appendPlainText(msg)

    def _scan(self):
        repo = self._repo.text().strip()
        if not repo:
            return
        endpoint, source = self._get_source_params()
        self._log_msg(f"扫描 {repo} ...")
        self._dl.scan(
            repo_id=repo,
            endpoint=endpoint,
            source=source,
            on_done=lambda r: self._sig_scan_done.emit(r),
            on_log=lambda m: self._sig_log.emit(m),
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

            # 复选框居中
            cb = QCheckBox()
            cb.setChecked(False)
            cell = QWidget()
            cell_layout = QHBoxLayout(cell)
            cell_layout.addWidget(cb)
            cell_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            self._table.setCellWidget(row, 0, cell)

            self._table.setItem(row, 1, QTableWidgetItem(f.name))
            self._table.setItem(row, 2, QTableWidgetItem(format_size(f.size) if f.size else "—"))

    def _get_selected(self) -> list[RemoteFile]:
        selected = []
        for row in range(self._table.rowCount()):
            cell = self._table.cellWidget(row, 0)
            if cell:
                cb = cell.findChild(QCheckBox)
                if cb and cb.isChecked() and row < len(self._remote_files):
                    selected.append(self._remote_files[row])
        return selected

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
        self._btn_cancel.setEnabled(False)
        self._btn_start.setEnabled(True)

    def _start(self):
        selected = self._get_selected()
        if not selected:
            self._log_msg("请先勾选要下载的文件")
            return
        dest = self._dest.text().strip()
        if not dest:
            self._log_msg("请先选择下载目录")
            return
        repo = self._repo.text().strip()
        endpoint, source = self._get_source_params()
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._btn_cancel.setEnabled(True)
        self._btn_start.setEnabled(False)
        self._log_msg(f"开始下载 {len(selected)} 个文件...")
        self._dl.start(
            files=selected,
            repo_id=repo,
            save_dir=dest,
            on_progress=lambda t: self._sig_progress.emit(t),
            on_done=lambda t: self._sig_done.emit(t),
            on_log=lambda m: self._sig_log.emit(m),
            endpoint=endpoint,
            source=source,
        )

    def _cancel(self):
        self._dl.cancel()

    def _copy_log(self):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._log.toPlainText())

    # ------------------------------------------------------------------
    # 搜索
    # ------------------------------------------------------------------

    def _search(self):
        keyword = self._search_input.text().strip()
        if not keyword:
            return
        endpoint, source = self._get_source_params()
        self._btn_search.setEnabled(False)
        self._search_results.clear()
        self._search_results.setVisible(False)
        self._log_msg(f"搜索: {keyword}")
        self._dl.search(
            keyword=keyword,
            endpoint=endpoint,
            source=source,
            on_done=lambda r: self._sig_search_done.emit(r),
            on_log=lambda m: self._sig_log.emit(m),
        )

    def _on_search_done(self, result):
        self._btn_search.setEnabled(True)
        if isinstance(result, Exception):
            self._log_msg(f"搜索失败: {result}")
            return
        if not result:
            self._log_msg("未找到匹配的模型")
            self._search_results.setVisible(False)
            return
        self._search_results.clear()
        for item in result:
            text = f"{item.repo_id}  ⬇{_format_downloads(item.downloads)}  ♥{item.likes}"
            QListWidgetItem(text, self._search_results)
        self._search_results.setVisible(True)
        self._log_msg(f"找到 {len(result)} 个仓库，双击选择")

    def _on_search_selected(self, item: QListWidgetItem):
        text = item.text()
        repo_id = text.split("  ")[0].strip()
        self._repo.setText(repo_id)
        self._search_results.setVisible(False)
        self._log_msg(f"已选择: {repo_id}")
