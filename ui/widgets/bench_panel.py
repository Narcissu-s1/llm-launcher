import os
import re
import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QListWidget, QPushButton, QLineEdit, QSpinBox, QComboBox,
    QPlainTextEdit, QTableWidget, QTableWidgetItem,
    QLabel, QGroupBox, QSizePolicy, QCheckBox,
)

from core.config import ConfigStore


def _find_llama_bench(config_path: str) -> str:
    names = ["llama-bench.exe", "llama-bench"]
    dirs = []
    if config_path and os.path.isdir(config_path):
        dirs.append(config_path)
    dirs += [os.getcwd(), os.path.join(os.getcwd(), "bin")]
    for d in dirs:
        for name in names:
            p = os.path.join(d, name)
            if os.path.isfile(p):
                return p
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    raise FileNotFoundError("找不到 llama-bench.exe，请在设置中指定 llama.cpp 目录")


class _BenchWorker(QThread):
    line = Signal(str)
    done = Signal(int)
    error = Signal(str)

    def __init__(self, cmd: list):
        super().__init__()
        self._cmd = cmd
        self._proc = None

    def stop(self):
        if self._proc:
            self._proc.terminate()

    def run(self):
        try:
            self._proc = subprocess.Popen(
                self._cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            for ln in self._proc.stdout:
                self.line.emit(ln.rstrip())
            self._proc.wait()
            self.done.emit(self._proc.returncode)
        except Exception as e:
            self.error.emit(str(e))


class BenchPanel(QWidget):
    def __init__(self, config: ConfigStore, library=None):
        super().__init__()
        self._config = config
        self._library = library
        self._worker: _BenchWorker | None = None
        self._queue: list = []
        self._all_output: list = []
        self._build_ui()
        if library is not None:
            library.models_changed.connect(self._on_models_changed)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)

        # 模型列表
        model_box = QGroupBox("测试模型（可添加多个进行对比）")
        mv = QVBoxLayout(model_box)
        sel_row = QHBoxLayout()
        self._model_combo = QComboBox()
        self._model_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn_add = QPushButton("添加到列表")
        btn_add.clicked.connect(self._add_model)
        sel_row.addWidget(QLabel("从模型库选择:"))
        sel_row.addWidget(self._model_combo)
        sel_row.addWidget(btn_add)
        mv.addLayout(sel_row)
        list_row = QHBoxLayout()
        self._model_list = QListWidget()
        self._model_list.setMaximumHeight(80)
        btn_del = QPushButton("删除")
        btn_del.clicked.connect(self._del_model)
        list_row.addWidget(self._model_list)
        list_row.addWidget(btn_del)
        mv.addLayout(list_row)
        root.addWidget(model_box)

        # 参数表单
        param_box = QGroupBox("测试参数（多轮对话场景）")
        form = QFormLayout(param_box)
        _p_vals = [128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536, 131072]
        _n_vals = [128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536, 131072]
        _d_vals = [0, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536, 131072]
        _b_vals = [128, 256, 512, 1024, 2048, 4096]
        self._n_prompt_cbs, prompt_row = self._make_checkbox_row(_p_vals, {512})
        self._n_gen_cbs,    gen_row    = self._make_checkbox_row(_n_vals, {128})
        self._n_depth_cbs,  depth_row  = self._make_checkbox_row(_d_vals, {0})
        self._batch_cbs,    batch_row  = self._make_checkbox_row(_b_vals, {2048})  # 2048 在列表中
        self._ngl = QLineEdit("99")
        self._ngl.setPlaceholderText("逗号分隔多值，如 0,32,99")
        self._repetitions = QSpinBox()
        self._repetitions.setRange(1, 100)
        self._repetitions.setValue(3)
        _kv_types = ["f16", "f32", "bf16", "q8_0", "q4_0", "q4_1", "iq4_nl", "q5_0", "q5_1"]
        self._ctk = QComboBox(); self._ctk.addItems(_kv_types)
        self._ctv = QComboBox(); self._ctv.addItems(_kv_types)
        self._fa  = QCheckBox("启用 Flash Attention")
        self._output_fmt = QComboBox()
        self._output_fmt.addItems(["md", "csv", "json", "jsonl", "sql"])
        form.addRow("历史缓存 (-d)", depth_row)
        form.addRow("新输入长度 (-p)", prompt_row)
        form.addRow("生成长度 (-n)", gen_row)
        form.addRow("Batch Size (-b)", batch_row)
        form.addRow("GPU 层数 (-ngl)", self._ngl)
        form.addRow("K 缓存类型 (-ctk)", self._ctk)
        form.addRow("V 缓存类型 (-ctv)", self._ctv)
        form.addRow("", self._fa)
        form.addRow("重复次数 (-r)", self._repetitions)
        form.addRow("输出格式 (-o)", self._output_fmt)
        root.addWidget(param_box)

        # 按钮行
        btn_row = QHBoxLayout()
        self._btn_run = QPushButton("运行")
        self._btn_run.clicked.connect(self._run)
        self._btn_stop = QPushButton("停止")
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._stop)
        btn_clear = QPushButton("清空")
        btn_clear.clicked.connect(self._clear)
        self._status_label = QLabel("")
        btn_row.addWidget(self._btn_run)
        btn_row.addWidget(self._btn_stop)
        btn_row.addWidget(btn_clear)
        btn_row.addStretch()
        btn_row.addWidget(self._status_label)
        root.addLayout(btn_row)

        # 输出区
        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self._output.setMinimumHeight(150)
        root.addWidget(self._output, stretch=2)

        # 汇总表格（初始隐藏）
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(["模型", "n-prompt", "n-gen", "ngl", "t/s prompt", "t/s gen"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.hide()
        root.addWidget(self._table, stretch=1)

    @staticmethod
    def _make_checkbox_row(values: list, checked: set):
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        cbs = {}
        for v in values:
            cb = QCheckBox(str(v))
            cb.setChecked(v in checked)
            row.addWidget(cb)
            cbs[v] = cb
        row.addStretch()
        return cbs, widget

    def _add_model(self):
        path = self._model_combo.currentData()
        if path and not self._model_list.findItems(path, Qt.MatchFlag.MatchExactly):
            self._model_list.addItem(path)

    def _on_models_changed(self, models: list):
        current = self._model_combo.currentData()
        self._model_combo.clear()
        for m in models:
            self._model_combo.addItem(m.name, m.path)
        # 恢复之前选中的项
        if current:
            idx = self._model_combo.findData(current)
            if idx >= 0:
                self._model_combo.setCurrentIndex(idx)

    def _del_model(self):
        for item in self._model_list.selectedItems():
            self._model_list.takeItem(self._model_list.row(item))

    def _build_cmds(self) -> list:
        exe = _find_llama_bench(self._config.get("app.llama_cpp_dir") or "")
        models = [self._model_list.item(i).text() for i in range(self._model_list.count())]
        ngl_values = [v.strip() for v in self._ngl.text().split(",") if v.strip()]
        fmt = self._output_fmt.currentText()
        cmds = []
        for model in models:
            for ngl in ngl_values:
                cmd = [
                    exe,
                    "-m", Path(model).as_posix(),
                    "-d", ",".join(str(v) for v, cb in self._n_depth_cbs.items() if cb.isChecked()) or "0",
                    "-p", ",".join(str(v) for v, cb in self._n_prompt_cbs.items() if cb.isChecked()) or "512",
                    "-n", ",".join(str(v) for v, cb in self._n_gen_cbs.items() if cb.isChecked()) or "128",
                    "-b", ",".join(str(v) for v, cb in self._batch_cbs.items() if cb.isChecked()) or "2048",
                    "-ngl", ngl,
                    "-ctk", self._ctk.currentText(),
                    "-ctv", self._ctv.currentText(),
                    "-fa", "1" if self._fa.isChecked() else "0",
                    "-r", str(self._repetitions.value()),
                    "-o", fmt,
                ]
                cmds.append(cmd)
        return cmds

    def _run(self):
        if self._model_list.count() == 0:
            self._output.appendPlainText("[错误] 请先添加至少一个模型")
            return
        try:
            cmds = self._build_cmds()
        except FileNotFoundError as e:
            self._output.appendPlainText(f"[错误] {e}")
            return
        self._queue = cmds
        self._all_output = []
        self._table.setRowCount(0)
        self._table.hide()
        self._btn_run.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._next_task()

    def _next_task(self):
        if not self._queue:
            self._finish()
            return
        cmd = self._queue.pop(0)
        total = len(self._all_output) // 1 + 1  # 任务序号近似
        self._status_label.setText(f"运行中...")
        self._output.appendPlainText(f"\n{'='*60}")
        self._output.appendPlainText(f">>> {' '.join(cmd)}")
        self._output.appendPlainText('='*60)
        self._worker = _BenchWorker(cmd)
        self._worker.line.connect(self._on_line)
        self._worker.done.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _stop(self):
        self._queue.clear()
        if self._worker:
            self._worker.stop()

    def _clear(self):
        self._output.clear()
        self._all_output.clear()
        self._table.setRowCount(0)
        self._table.hide()
        self._status_label.setText("")

    def _on_line(self, line: str):
        self._output.appendPlainText(line)
        self._output.verticalScrollBar().setValue(
            self._output.verticalScrollBar().maximum()
        )
        self._all_output.append(line)

    def _on_done(self, code: int):
        self._output.appendPlainText(f"--- 完成（退出码 {code}）---")
        self._worker = None
        if self._queue:
            self._next_task()
        else:
            self._finish()

    def _on_error(self, msg: str):
        self._output.appendPlainText(f"[错误] {msg}")
        self._queue.clear()
        self._worker = None
        self._btn_run.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._status_label.setText("出错")

    def _finish(self):
        self._btn_run.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._status_label.setText("完成")
        if self._output_fmt.currentText() == "md":
            self._populate_table()

    def _populate_table(self):
        # 解析 md 表格数据行：| model | ... | n_prompt | n_gen | ... | t/s prompt | t/s gen |
        # llama-bench md 格式列顺序：model | size | params | backend | ngl | n_batch | n_ubatch | flash_attn | n_prompt | n_gen | n_depth | test | t/s
        # 每个测试有两行：pp（prompt processing）和 tg（token generation）
        pattern = re.compile(
            r'\|\s*([^|]+?)\s*\|'   # model
            r'[^|]*\|[^|]*\|[^|]*\|'  # size, params, backend
            r'\s*(\d+)\s*\|'        # ngl
            r'[^|]*\|[^|]*\|[^|]*\|'  # n_batch, n_ubatch, flash_attn
            r'\s*(\d+)\s*\|'        # n_prompt
            r'\s*(\d+)\s*\|'        # n_gen
            r'[^|]*\|'              # n_depth
            r'\s*([^|]+?)\s*\|'     # test (pp/tg)
            r'\s*([\d.]+)\s*\|'     # t/s
        )
        rows: dict = {}  # key=(model,ngl,n_prompt,n_gen) -> {pp, tg}
        for ln in self._all_output:
            m = pattern.match(ln)
            if not m:
                continue
            model, ngl, n_prompt, n_gen, test, ts = m.groups()
            model = model.strip()
            test = test.strip()
            key = (model, ngl, n_prompt, n_gen)
            if key not in rows:
                rows[key] = {}
            if "pp" in test:
                rows[key]["pp"] = ts
            elif "tg" in test:
                rows[key]["tg"] = ts

        if not rows:
            return

        self._table.setRowCount(len(rows))
        for r, (key, vals) in enumerate(rows.items()):
            model, ngl, n_prompt, n_gen = key
            for c, val in enumerate([
                os.path.basename(model), n_prompt, n_gen, ngl,
                vals.get("pp", "—"), vals.get("tg", "—"),
            ]):
                self._table.setItem(r, c, QTableWidgetItem(val))
        self._table.resizeColumnsToContents()
        self._table.show()
