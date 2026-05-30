# ui/control_panel.py
"""左侧控制面板：模型选择、参数配置、预设管理、启停按钮"""

import json
import logging
import os
import sys
import winreg

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QSpinBox, QGroupBox, QFormLayout,
    QFileDialog, QScrollArea, QSizePolicy, QCheckBox,
    QMessageBox, QInputDialog, QFrame,
)
from PySide6.QtCore import Signal

from core.config import ConfigStore
from core.process_manager import ProcessSupervisor, PortInUseError, ProcessError
from ui.confirm_dialog import ConfirmDialog
from ui.widgets.param_groups import (
    KVCacheParams, InferenceParams, SamplingParams,
    ReasoningParams, MultimodalParams, SecurityParams, SpeculativeParams,
)

logger = logging.getLogger(__name__)

# param_groups 返回的键名 → process_manager 期望的键名
_REMAP = {
    "ctk": "cache_type_k",
    "ctv": "cache_type_v",
    "kvu": "kv_unified",
    "temperature": "temp",
}
_REMAP_BACK = {v: k for k, v in _REMAP.items()}


class ControlPanel(QWidget):
    set_model_path = Signal(str)  # 接收 ModelLibraryPanel.switch_model 信号
    started = Signal(dict)        # 启动成功后发出，携带 params

    def __init__(self, config: ConfigStore, supervisor: ProcessSupervisor):
        super().__init__()
        self._config = config
        self._supervisor = supervisor
        self._build_ui()
        self._restore()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # 模型文件
        root.addWidget(QLabel("模型文件"))
        row = QHBoxLayout()
        self._model_path = QLineEdit()
        self._model_path.setReadOnly(True)
        self._btn_browse_model = QPushButton("浏览")
        self._btn_browse_model.clicked.connect(self._browse_model)
        row.addWidget(self._model_path)
        row.addWidget(self._btn_browse_model)
        root.addLayout(row)

        # mmproj（可选）
        root.addWidget(QLabel("mmproj（可选）"))
        row2 = QHBoxLayout()
        self._mmproj_path = QLineEdit()
        self._mmproj_path.setReadOnly(True)
        self._mmproj_path.setPlaceholderText("留空自动检测")
        self._btn_browse_mmproj = QPushButton("浏览")
        self._btn_browse_mmproj.clicked.connect(self._browse_mmproj)
        row2.addWidget(self._mmproj_path)
        row2.addWidget(self._btn_browse_mmproj)
        root.addLayout(row2)

        # 路由模式
        self._router_mode = QCheckBox("路由模式（多模型，--models-dir）")
        self._router_mode.setToolTip(
            "启用后以路由模式启动服务器，自动扫描目录中的 GGUF 模型\n"
            "通过 /v1/models 列出模型，请求中指定 model 字段路由到对应模型"
        )
        self._router_mode.stateChanged.connect(self._toggle_router_mode)
        root.addWidget(self._router_mode)

        row_router = QHBoxLayout()
        self._models_dir = QLineEdit()
        self._models_dir.setReadOnly(True)
        self._models_dir.setPlaceholderText("选择模型文件所在的上一级目录")
        self._btn_browse_models_dir = QPushButton("浏览")
        self._btn_browse_models_dir.clicked.connect(self._browse_models_dir)
        row_router.addWidget(self._models_dir)
        row_router.addWidget(self._btn_browse_models_dir)
        root.addLayout(row_router)

        # llama.cpp 目录（自动查找 llama-server.exe）
        root.addWidget(QLabel("llama.cpp 目录"))
        row3 = QHBoxLayout()
        self._server_path = QLineEdit()
        self._server_path.setReadOnly(True)
        self._server_path.setPlaceholderText("留空自动搜索 PATH")
        self._btn_browse_server = QPushButton("浏览")
        self._btn_browse_server.clicked.connect(self._browse_server)
        row3.addWidget(self._server_path)
        row3.addWidget(self._btn_browse_server)
        root.addLayout(row3)

        # 基础参数
        basic = QGroupBox("基础参数")
        form = QFormLayout(basic)
        self._port = QSpinBox()
        self._port.setRange(1024, 65535)
        self._port.setValue(8080)
        self._ctx = QComboBox()
        self._ctx.addItems(["2048", "4096", "8192", "16384", "32768"])
        # 路由模式下额外增加 64K~256K 的上下文选项
        self._router_ctx_extra = ["65536", "131072", "262144"]
        self._ngl = QSpinBox()
        self._ngl.setRange(-1, 9999)
        self._ngl.setSpecialValueText("全部（-1）")
        self._ngl.setValue(-1)
        self._np = QComboBox()
        self._np.addItems(["1", "2", "4", "8"])
        self._host = QComboBox()
        self._host.addItem("127.0.0.1（仅本机）", "127.0.0.1")
        self._host.addItem("0.0.0.0（局域网）", "0.0.0.0")
        form.addRow("端口", self._port)
        form.addRow("上下文长度", self._ctx)
        form.addRow("GPU 层数", self._ngl)
        form.addRow("并发数", self._np)
        form.addRow("监听地址", self._host)
        root.addWidget(basic)

        # 高级参数（滚动区）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        adv_widget = QWidget()
        adv_layout = QVBoxLayout(adv_widget)
        adv_layout.setContentsMargins(0, 0, 0, 0)
        adv_layout.setSpacing(4)
        self._kv_params = KVCacheParams()
        self._inf_params = InferenceParams()
        self._samp_params = SamplingParams()
        self._rea_params = ReasoningParams()
        self._mm_params = MultimodalParams()
        self._sec_params = SecurityParams()
        self._spec_params = SpeculativeParams()
        for w in [self._kv_params, self._inf_params, self._samp_params,
                  self._rea_params, self._mm_params, self._sec_params, self._spec_params]:
            adv_layout.addWidget(w)
        adv_layout.addStretch()
        scroll.setWidget(adv_widget)
        root.addWidget(scroll, stretch=1)

        # 预设管理
        preset_box = QGroupBox("预设")
        pl = QHBoxLayout(preset_box)
        self._preset_combo = QComboBox()
        self._preset_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._btn_preset_save = QPushButton("保存")
        self._btn_preset_load = QPushButton("载入")
        self._btn_preset_delete = QPushButton("删除")
        self._btn_preset_export = QPushButton("导出")
        self._btn_preset_import = QPushButton("导入")
        for w in [self._preset_combo, self._btn_preset_save, self._btn_preset_load,
                  self._btn_preset_delete, self._btn_preset_export, self._btn_preset_import]:
            pl.addWidget(w)
        self._btn_preset_save.clicked.connect(self._save_preset)
        self._btn_preset_load.clicked.connect(self._load_preset)
        self._btn_preset_delete.clicked.connect(self._delete_preset)
        self._btn_preset_export.clicked.connect(self._export_presets)
        self._btn_preset_import.clicked.connect(self._import_presets)
        root.addWidget(preset_box)

        # 选项行
        opts_row = QHBoxLayout()
        self._autostart = QCheckBox("开机自启")
        self._autostart.setChecked(bool(self._config.get("app.autostart")))
        self._autostart.stateChanged.connect(self._toggle_autostart)
        self._auto_browser = QCheckBox("启动后打开浏览器")
        self._auto_browser.setChecked(bool(self._config.get("app.auto_open_browser")))
        self._auto_browser.stateChanged.connect(
            lambda s: self._config.set("app.auto_open_browser", bool(s))
        )
        self._tools = QCheckBox("启动WUI工具")
        self._tools.setToolTip("启用 llama-server 内置 Web 工具界面（--tools）")
        self._tools.setChecked(bool(self._config.get("server.tools")))
        self._tools.stateChanged.connect(
            lambda s: self._config.set("server.tools", bool(s))
        )
        opts_row.addWidget(self._autostart)
        opts_row.addWidget(self._auto_browser)
        opts_row.addWidget(self._tools)
        opts_row.addStretch()
        root.addLayout(opts_row)

        # 启停按钮
        btn_row = QHBoxLayout()
        self._btn_start = QPushButton("启动")
        self._btn_start.setObjectName("btnPrimary")
        self._btn_stop = QPushButton("停止")
        self._btn_stop.setObjectName("btnStop")
        self._btn_start.clicked.connect(self._start)
        self._btn_stop.clicked.connect(self._stop)
        btn_row.addWidget(self._btn_start)
        btn_row.addWidget(self._btn_stop)
        root.addLayout(btn_row)

        self._refresh_presets()

    # ------------------------------------------------------------------
    # 文件浏览
    # ------------------------------------------------------------------

    def _browse_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择模型文件", "", "GGUF Files (*.gguf)")
        if path:
            self._model_path.setText(path)
            self._config.set("model.last_path", path)

    def _browse_mmproj(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 mmproj 文件", "", "GGUF Files (*.gguf)")
        if path:
            self._mmproj_path.setText(path)
            self._config.set("model.mmproj_path", path)

    def _browse_server(self):
        path = QFileDialog.getExistingDirectory(self, "选择 llama.cpp 目录", self._server_path.text())
        if path:
            self._server_path.setText(path)
            self._config.set("app.llama_dir", path)

    def _browse_models_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择模型目录", self._models_dir.text())
        if path:
            self._models_dir.setText(path)
            self._config.set("app.models_dir", path)

    def _toggle_router_mode(self, state):
        enabled = bool(state)
        self._config.set("app.router_mode", enabled)
        # 路由模式下禁用单模型文件和 mmproj 选择
        self._model_path.setEnabled(not enabled)
        self._btn_browse_model.setEnabled(not enabled)
        self._mmproj_path.setEnabled(not enabled)
        self._btn_browse_mmproj.setEnabled(not enabled)
        # 路由模式下启用模型目录选择
        self._models_dir.setEnabled(enabled)
        self._btn_browse_models_dir.setEnabled(enabled)
        # 路由模式下扩展上下文长度选项至 256K
        current = self._ctx.currentText()
        self._ctx.blockSignals(True)
        self._ctx.clear()
        base = ["2048", "4096", "8192", "16384", "32768"]
        if enabled:
            base += self._router_ctx_extra
        self._ctx.addItems(base)
        idx = self._ctx.findText(current)
        self._ctx.setCurrentIndex(idx if idx >= 0 else self._ctx.count() - 1)
        self._ctx.blockSignals(False)

    # ------------------------------------------------------------------
    # 参数收集与回填
    # ------------------------------------------------------------------

    def collect_params(self) -> dict:
        """收集所有参数，键名与 process_manager._build_command 对齐"""
        params = {
            "model_path": self._model_path.text(),
            "mmproj_path": self._mmproj_path.text(),
            "port": self._port.value(),
            "context_size": int(self._ctx.currentText()),
            "n_gpu_layers": self._ngl.value(),
            "parallel": int(self._np.currentText()),
            "host": self._host.currentData(),
            "router_mode": self._router_mode.isChecked(),
            "models_dir": self._models_dir.text(),
            "tools": self._tools.isChecked(),
        }
        for w in [self._kv_params, self._inf_params, self._samp_params,
                  self._rea_params, self._mm_params, self._sec_params, self._spec_params]:
            params.update(w.collect_params())
        # 重命名 param_groups 的键以匹配 process_manager 期望
        for old, new in _REMAP.items():
            if old in params:
                params[new] = params.pop(old)
        # 过滤 None 值，防止可选参数未设置时进入命令行
        params = {k: v for k, v in params.items() if v is not None}
        return params

    def _restore(self):
        """从配置恢复 UI 控件值"""
        self._model_path.setText(self._config.get("model.last_path") or "")
        self._mmproj_path.setText(self._config.get("model.mmproj_path") or "")
        self._server_path.setText(self._config.get("app.llama_dir") or "")
        self._port.setValue(self._config.get("server.port") or 8080)

        # 路由模式
        router = bool(self._config.get("app.router_mode"))
        self._router_mode.setChecked(router)
        self._models_dir.setText(self._config.get("app.models_dir") or "")
        self._models_dir.setEnabled(router)
        self._btn_browse_models_dir.setEnabled(router)
        self._model_path.setEnabled(not router)
        self._btn_browse_model.setEnabled(not router)
        self._mmproj_path.setEnabled(not router)
        self._btn_browse_mmproj.setEnabled(not router)

        # 路由模式下扩展上下文长度选项至 256K
        if router:
            self._ctx.addItems(self._router_ctx_extra)

        ctx = str(self._config.get("server.context_size") or 4096)
        idx = self._ctx.findText(ctx)
        if idx >= 0:
            self._ctx.setCurrentIndex(idx)

        ngl = self._config.get("server.n_gpu_layers")
        self._ngl.setValue(ngl if ngl is not None else -1)

        np_val = str(self._config.get("server.parallel") or 1)
        idx2 = self._np.findText(np_val)
        if idx2 >= 0:
            self._np.setCurrentIndex(idx2)

    def _start(self):
        params = self.collect_params()
        # 路由模式验证
        if params["router_mode"]:
            if not params["models_dir"]:
                QMessageBox.warning(self, "路由模式", "请先选择模型目录")
                return
            if not os.path.isdir(params["models_dir"]):
                QMessageBox.warning(self, "路由模式", f"模型目录不存在:\n{params['models_dir']}")
                return
        else:
            if not params["model_path"]:
                QMessageBox.warning(self, "未选择模型", "请先选择模型文件，或启用路由模式")
                return
        llama_dir = self._server_path.text().strip()
        try:
            from core.model_resolver import ModelResolver
            params["server_path"] = ModelResolver(llama_dir).resolve()
        except FileNotFoundError as e:
            QMessageBox.warning(self, "找不到 llama-server", str(e))
            return
        try:
            self._supervisor.start(params)
            self._config.set("server.port", params["port"])
            self.started.emit(params)
            if self._auto_browser.isChecked():
                import webbrowser
                host = params.get("host", "127.0.0.1")
                port = params.get("port", 8080)
                webbrowser.open(f"http://{host}:{port}")
        except PortInUseError as e:
            QMessageBox.warning(self, "端口冲突", str(e))
        except ProcessError as e:
            QMessageBox.critical(self, "启动失败", str(e))

    def _stop(self):
        self._supervisor.stop()

    # ------------------------------------------------------------------
    # 预设管理
    # ------------------------------------------------------------------

    def _refresh_presets(self):
        self._preset_combo.clear()
        for name in self._config.get_presets():
            self._preset_combo.addItem(name)

    def _save_preset(self):
        name, ok = QInputDialog.getText(self, "保存预设", "预设名称:")
        if not ok or not name.strip():
            return
        name = name.strip()
        if name in self._config.get_presets():
            dlg = ConfirmDialog(f'覆盖预设 "{name}"？', self)
            if not dlg.exec():
                return
        self._config.save_preset(name, self.collect_params())
        self._refresh_presets()

    def _load_preset(self):
        name = self._preset_combo.currentText()
        if not name:
            return
        preset = self._config.get_presets().get(name, {})
        self._restore_from_preset(preset)

    def _restore_from_preset(self, preset: dict):
        """将预设回填到 UI 控件"""
        if "model_path" in preset:
            self._model_path.setText(preset["model_path"])
        if "port" in preset:
            self._port.setValue(preset["port"])
        if "context_size" in preset:
            idx = self._ctx.findText(str(preset["context_size"]))
            if idx >= 0:
                self._ctx.setCurrentIndex(idx)
        if "n_gpu_layers" in preset:
            self._ngl.setValue(preset["n_gpu_layers"])
        if "parallel" in preset:
            idx2 = self._np.findText(str(preset["parallel"]))
            if idx2 >= 0:
                self._np.setCurrentIndex(idx2)
        if "host" in preset:
            for i in range(self._host.count()):
                if self._host.itemData(i) == preset["host"]:
                    self._host.setCurrentIndex(i)
                    break
        # 反向重映射，恢复 param_groups 期望的键名
        pg_preset = {_REMAP_BACK.get(k, k): v for k, v in preset.items()}
        for w in [self._kv_params, self._inf_params, self._samp_params,
                  self._rea_params, self._mm_params, self._sec_params]:
            w.restore_params(pg_preset)

    def _delete_preset(self):
        name = self._preset_combo.currentText()
        if not name:
            return
        dlg = ConfirmDialog(f'删除预设 "{name}"？', self)
        if dlg.exec():
            self._config.delete_preset(name)
            self._refresh_presets()

    def _export_presets(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "导出预设", "presets_export.json", "JSON (*.json)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._config.get_presets(), f, ensure_ascii=False, indent=2)

    def _import_presets(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入预设", "", "JSON (*.json)")
        if not path:
            return
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for name, params in data.items():
            self._config.save_preset(name, params)
        self._refresh_presets()

    # ------------------------------------------------------------------
    # 开机自启
    # ------------------------------------------------------------------

    _REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    _REG_VALUE_NAME = "LLMlauncher"

    def _toggle_autostart(self, state):
        enabled = bool(state)
        self._config.set("app.autostart", enabled)
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, self._REGISTRY_KEY, 0, winreg.KEY_SET_VALUE
            ) as k:
                if enabled:
                    exe = sys.executable
                    script = os.path.abspath(
                        os.path.join(os.path.dirname(__file__), "..", "main.py")
                    )
                    winreg.SetValueEx(k, self._REG_VALUE_NAME, 0, winreg.REG_SZ,
                                      f'"{exe}" "{script}"')
                else:
                    try:
                        winreg.DeleteValue(k, self._REG_VALUE_NAME)
                    except FileNotFoundError:
                        pass
        except Exception as e:
            logger.warning("注册表写入失败: %s", e)

    # ------------------------------------------------------------------
    # 外部信号槽
    # ------------------------------------------------------------------

    def on_switch_model(self, path: str):
        """接收 ModelLibraryPanel.switch_model 信号，切换模型路径"""
        self._model_path.setText(path)
        self._config.set("model.last_path", path)

        # 自动检测同目录 mmproj，找不到则清空（避免残留旧路径导致不匹配）
        from core.model_library import find_mmproj
        mmproj = find_mmproj(path)
        self._mmproj_path.setText(mmproj)
        self._config.set("model.mmproj_path", mmproj)

        self._update_ctx_for_model(path)

    def _update_ctx_for_model(self, path: str):
        """根据模型 GGUF metadata 更新 context 选项和 GPU 层数范围"""
        from core.model_library import _parse_gguf
        try:
            info = _parse_gguf(path)
        except Exception:
            return

        # 更新上下文长度下拉（2 次幂，上限为模型最大 context）
        max_ctx = info.context_length
        if max_ctx > 0:
            options = []
            v = 512
            while v <= max_ctx:
                options.append(str(v))
                v *= 2
            if options:
                current = self._ctx.currentText()
                self._ctx.blockSignals(True)
                self._ctx.clear()
                self._ctx.addItems(options)
                idx = self._ctx.findText(current)
                self._ctx.setCurrentIndex(idx if idx >= 0 else self._ctx.count() - 1)
                self._ctx.blockSignals(False)

        # 更新 GPU 层数范围（-1 ~ block_count）
        block_count = info.block_count
        if block_count > 0:
            current_ngl = self._ngl.value()
            self._ngl.setRange(-1, block_count)
            self._ngl.setToolTip(f"该模型共 {block_count} 层，-1 = 全部卸载到 GPU")
            # 若当前值超出新上限则夹紧
            self._ngl.setValue(min(current_ngl, block_count))       # 尽量恢复原来的选项，否则选最大
        idx = self._ctx.findText(current)
        self._ctx.setCurrentIndex(idx if idx >= 0 else self._ctx.count() - 1)
        self._ctx.blockSignals(False)
