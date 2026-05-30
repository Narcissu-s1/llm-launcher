import json
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QFileDialog, QLineEdit, QHeaderView
)
from PySide6.QtCore import Signal
from core.config import ConfigStore
from core.model_library import ModelInfo, _parse_gguf, format_size

class ModelLibraryPanel(QWidget):
    switch_model = Signal(str)
    models_changed = Signal(list)  # emit list[ModelInfo]

    @property
    def models(self):
        return list(self._models)

    def __init__(self, config: ConfigStore):
        super().__init__()
        self._config = config
        self._models = []
        # 缓存文件与 config.yaml 同目录
        cfg_path = getattr(config, "_config_path", "config.yaml")
        self._cache_file = os.path.join(os.path.dirname(os.path.abspath(cfg_path)), "model_cache.json")

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
        self._table.setColumnWidth(0, 320)
        self._table.setColumnWidth(1, 70)
        self._table.setColumnWidth(2, 80)
        self._table.setColumnWidth(3, 70)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self._table.setStyleSheet(
            "QTableWidget { background:#ffffff; border:1px solid #e2e8f0; border-radius:6px; }"
            "QTableWidget::item { padding:4px 8px; }"
            "QTableWidget::item:selected { background:#ebf8ff; color:#2d3748; }"
            "QHeaderView::section { background:#f0f4f8; color:#718096; font-weight:600; font-size:12px; padding:6px 8px; border:none; border-bottom:1px solid #e2e8f0; }"
        )
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        btn_use = QPushButton("使用此模型"); btn_use.setObjectName("btnPrimary")
        btn_use.clicked.connect(self._use_selected)
        btn_row.addStretch(); btn_row.addWidget(btn_use)
        layout.addLayout(btn_row)

        # 启动时加载缓存（不重新扫描）
        d = self._dir_input.text()
        if d:
            self._load_from_cache(d)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "选择模型目录", self._dir_input.text())
        if d:
            self._dir_input.setText(d)
            self._config.set("app.model_dir", d)
            self._load_from_cache(d)

    def _scan(self):
        d = self._dir_input.text()
        if not d:
            return
        cache = self._load_cache()
        models = []
        for root, _, files in os.walk(d):
            for fname in sorted(files):
                if not fname.lower().endswith(".gguf"):
                    continue
                if "mmproj" in fname.lower():
                    continue
                path = os.path.join(root, fname)
                try:
                    stat = os.stat(path)
                    key = f"{path}|{stat.st_mtime}|{stat.st_size}"
                except OSError:
                    key = path
                if key in cache:
                    models.append(ModelInfo(**cache[key]))
                else:
                    info = _parse_gguf(path)
                    from dataclasses import asdict
                    cache[key] = asdict(info)
                    models.append(info)
        self._save_cache(cache)
        self._models = models
        self._populate_table()
        self.models_changed.emit(self._models)

    def _use_selected(self):
        rows = self._table.selectedIndexes()
        if not rows:
            return
        row = rows[0].row()
        if row < len(self._models):
            self.switch_model.emit(self._models[row].path)

    def _populate_table(self):
        self._table.setRowCount(0)
        for m in self._models:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(m.name))
            self._table.setItem(row, 1, QTableWidgetItem(format_size(m.file_size)))
            self._table.setItem(row, 2, QTableWidgetItem(m.quant_type or "—"))
            # 优先显示原始 size_label，否则格式化 param_count
            if m.size_label:
                param_str = m.size_label
            elif m.param_count >= 1e9:
                param_str = f"{m.param_count/1e9:.1f}B"
            elif m.param_count > 0:
                param_str = f"{m.param_count/1e6:.0f}M"
            else:
                param_str = "—"
            self._table.setItem(row, 3, QTableWidgetItem(param_str))
            self._table.setItem(row, 4, QTableWidgetItem(m.architecture or "—"))

    def _load_from_cache(self, directory: str):
        """从缓存加载指定目录的扫描结果（不重新解析文件）"""
        cache = self._load_cache()
        models = []
        for key, data in cache.items():
            path = data.get("path", "")
            if not path.startswith(directory):
                continue
            if not os.path.exists(path):
                continue
            try:
                stat = os.stat(path)
                expected_key = f"{path}|{stat.st_mtime}|{stat.st_size}"
            except OSError:
                continue
            if key == expected_key:
                models.append(ModelInfo(**data))
        models.sort(key=lambda m: m.name)
        self._models = models
        self._populate_table()
        self.models_changed.emit(self._models)

    def _load_cache(self) -> dict:
        try:
            with open(self._cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_cache(self, cache: dict):
        try:
            with open(self._cache_file, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
        except OSError:
            pass
