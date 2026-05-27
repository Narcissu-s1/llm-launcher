from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QFileDialog, QLineEdit
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
        self._dir_input.setText(config.get("app.model_dir", ""))
        btn_browse = QPushButton("选择目录")
        btn_scan = QPushButton("扫描")
        btn_browse.clicked.connect(self._browse)
        btn_scan.clicked.connect(self._scan)
        row.addWidget(self._dir_input); row.addWidget(btn_browse); row.addWidget(btn_scan)
        layout.addLayout(row)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["文件名", "大小", "量化"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
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
            self._table.setItem(row, 1, QTableWidgetItem(format_size(m.size)))
            self._table.setItem(row, 2, QTableWidgetItem(m.quant or "—"))

    def _use_selected(self):
        rows = self._table.selectedIndexes()
        if not rows:
            return
        row = rows[0].row()
        if row < len(self._models):
            self.switch_model.emit(self._models[row].path)
