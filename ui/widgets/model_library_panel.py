from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QFileDialog, QLineEdit, QHeaderView
)
from PySide6.QtCore import Signal
from core.config import ConfigStore
from core.model_library import scan_directory, format_size

class ModelLibraryPanel(QWidget):
    switch_model = Signal(str)

    def __init__(self, config: ConfigStore):
        super().__init__()
        self._config = config
        self._models = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        row = QHBoxLayout()
        self._dir_input = QLineEdit()
        self._dir_input.setReadOnly(True)
        self._dir_input.setText(config.get("app.model_dir") or "")
        btn_browse = QPushButton("选择目录")
        btn_scan = QPushButton("扫描")
        btn_browse.clicked.connect(self._browse)
        btn_scan.clicked.connect(self._scan)
        row.addWidget(self._dir_input); row.addWidget(btn_browse); row.addWidget(btn_scan)
        layout.addLayout(row)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["文件名", "大小", "量化", "参数量", "架构"])
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.setColumnWidth(0, 260)  # 文件名列加宽
        self._table.setColumnWidth(1, 70)
        self._table.setColumnWidth(2, 80)
        self._table.setColumnWidth(3, 70)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        btn_use = QPushButton("使用此模型"); btn_use.setObjectName("btnPrimary")
        btn_use.clicked.connect(self._use_selected)
        btn_row.addStretch(); btn_row.addWidget(btn_use)
        layout.addLayout(btn_row)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "选择模型目录", self._dir_input.text())
        if d:
            self._dir_input.setText(d)
            self._config.set("app.model_dir", d)
            self._config.save()

    def _scan(self):
        d = self._dir_input.text()
        if not d:
            return
        self._models = scan_directory(d)
        self._table.setRowCount(0)
        for m in self._models:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(m.name))
            self._table.setItem(row, 1, QTableWidgetItem(format_size(m.file_size)))
            self._table.setItem(row, 2, QTableWidgetItem(m.quant_type or "—"))
            param_str = f"{m.param_count/1e9:.1f}B" if m.param_count >= 1e9 else (f"{m.param_count/1e6:.0f}M" if m.param_count > 0 else "—")
            self._table.setItem(row, 3, QTableWidgetItem(param_str))
            self._table.setItem(row, 4, QTableWidgetItem(m.architecture or "—"))

    def _use_selected(self):
        rows = self._table.selectedIndexes()
        if not rows:
            return
        row = rows[0].row()
        if row < len(self._models):
            self.switch_model.emit(self._models[row].path)
