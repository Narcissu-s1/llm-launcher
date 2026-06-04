# Phase 4 GUI 重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有 Textual TUI 全量替换为 PySide6 桌面 GUI，保留 core/ 层零改动，新增托盘、开机自启、PyInstaller 打包支持。

**Architecture:** `core/` 层（EventBus、ProcessSupervisor、ConfigStore 等）零改动复用。UI 层全量重写为 PySide6 QWidget 体系，后台线程改用 QThread + Signal。左右分栏布局，右侧上下分栏（日志 70% / 监控 30%）。

**Tech Stack:** PySide6 >= 6.5, psutil, pyyaml, PyInstaller >= 6.0（打包用）

---

## 文件结构

### 新建
- `ui/app.py` — QMainWindow 主窗口，替换 LlamaLauncherApp
- `ui/control_panel.py` — 左侧控制面板 QWidget
- `ui/log_panel.py` — 右侧日志面板 QWidget
- `ui/confirm_dialog.py` — QDialog 二次确认弹窗
- `ui/widgets/param_groups.py` — 6 个参数分组（QGroupBox + QFormLayout）
- `ui/widgets/monitor_panel.py` — 运行时监控（CPU/RAM/GPU）
- `ui/widgets/model_library_panel.py` — 模型库面板
- `ui/widgets/download_panel.py` — 远程下载面板
- `ui/widgets/chat_panel.py` — API 测试聊天面板
- `ui/widgets/tray_icon.py` — 系统托盘（新增）
- `ui/bridge.py` — EventBus → Qt Signal 桥接层（新增）
- `assets/theme_light.qss` — 浅色主题样式表
- `main.py` — 入口，切换为 QApplication

### 保持不变
- `core/` 全部文件
- `config.yaml`
- `requirements.txt`（追加 PySide6）

---

## Task 1: 安装依赖 + 骨架入口

**Files:**
- Modify: `requirements.txt`
- Modify: `main.py`

- [ ] **Step 1: 添加 PySide6 依赖**

```
# requirements.txt 追加
PySide6>=6.5.0
```

运行：`pip install PySide6`

- [ ] **Step 2: 替换 main.py 入口**

```python
import sys
import logging
from PySide6.QtWidgets import QApplication
from ui.app import LlamaLauncherApp

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("LLM Launcher")
    window = LlamaLauncherApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 创建占位 ui/app.py 确认能启动**

```python
from PySide6.QtWidgets import QMainWindow, QLabel

class LlamaLauncherApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LLM Launcher")
        self.resize(1200, 800)
        self.setCentralWidget(QLabel("占位"))
```

- [ ] **Step 4: 验证启动**

运行：`python main.py`
预期：弹出空白窗口，无报错

- [ ] **Step 5: Commit**

```bash
git add requirements.txt main.py ui/app.py
git commit -m "feat: PySide6 骨架入口"
```

---

## Task 2: EventBus → Qt Signal 桥接层

**Files:**
- Create: `ui/bridge.py`

后台线程（日志、监控）需要安全地更新 UI。PySide6 要求 UI 操作必须在主线程，桥接层把 EventBus 事件转为 Qt Signal。

- [ ] **Step 1: 创建 ui/bridge.py**

```python
from PySide6.QtCore import QObject, Signal
from core.events import EventBus, EVENT_STATUS_CHANGED, EVENT_LOG_LINE, EVENT_STATS_UPDATE

class AppBridge(QObject):
    status_changed = Signal(str)   # ProcessStatus.value
    log_line = Signal(str)
    stats_update = Signal(dict)

    def __init__(self, bus: EventBus):
        super().__init__()
        bus.on(EVENT_STATUS_CHANGED, lambda s: self.status_changed.emit(s.value))
        bus.on(EVENT_LOG_LINE, lambda line: self.log_line.emit(line))
        bus.on(EVENT_STATS_UPDATE, lambda d: self.stats_update.emit(d))
```

- [ ] **Step 2: 写单元测试**

新建 `tests/test_bridge.py`：

```python
import pytest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication
import sys

@pytest.fixture(scope="session")
def qt_app():
    app = QApplication.instance() or QApplication(sys.argv)
    return app

def test_bridge_emits_log_line(qt_app):
    from core.events import EventBus, EVENT_LOG_LINE
    from ui.bridge import AppBridge
    bus = EventBus()
    bridge = AppBridge(bus)
    received = []
    bridge.log_line.connect(received.append)
    bus.emit(EVENT_LOG_LINE, "hello")
    assert received == ["hello"]
```

- [ ] **Step 3: 运行测试**

```bash
pytest tests/test_bridge.py -v
```
预期：PASS

- [ ] **Step 4: Commit**

```bash
git add ui/bridge.py tests/test_bridge.py
git commit -m "feat: EventBus→Qt Signal 桥接层"
```

---

## Task 3: QSS 主题样式表

**Files:**
- Create: `assets/theme_light.qss`

- [ ] **Step 1: 创建 assets/ 目录并写 theme_light.qss**

```css
/* assets/theme_light.qss */
QWidget {
    background-color: #f8fafb;
    color: #1a202c;
    font-family: "DM Sans", "Segoe UI", sans-serif;
    font-size: 13px;
}
QMainWindow, QDialog {
    background-color: #f8fafb;
}
/* 面板 */
QFrame#leftPanel, QFrame#rightPanel {
    background-color: #ffffff;
    border: none;
}
/* 输入框 */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #ffffff;
    border: 1px solid #e8eef2;
    border-radius: 4px;
    padding: 5px 8px;
    font-family: "DM Mono", "Consolas", monospace;
    font-size: 12px;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #2d7dd2;
}
/* 按钮 */
QPushButton {
    border: 1px solid #e8eef2;
    border-radius: 4px;
    padding: 6px 14px;
    background-color: #ffffff;
    font-weight: 500;
}
QPushButton:hover { border-color: #2d7dd2; color: #2d7dd2; }
QPushButton#btnStart  { background-color: #1a9e6e; color: #fff; border-color: #1a9e6e; }
QPushButton#btnStart:hover  { background-color: #158a5e; }
QPushButton#btnStop   { background-color: #e53e3e; color: #fff; border-color: #e53e3e; }
QPushButton#btnStop:hover   { background-color: #c53030; }
QPushButton#btnPrimary { background-color: #2d7dd2; color: #fff; border-color: #2d7dd2; }
QPushButton#btnPrimary:hover { background-color: #2268b8; }
/* Tab */
QTabBar::tab {
    padding: 8px 14px;
    color: #718096;
    border: none;
    border-bottom: 2px solid transparent;
    font-weight: 500;
    font-size: 12px;
}
QTabBar::tab:selected { color: #2d7dd2; border-bottom-color: #2d7dd2; }
QTabBar::tab:hover:!selected { color: #1a202c; }
QTabWidget::pane { border: none; border-top: 1px solid #e8eef2; }
/* GroupBox（参数分组） */
QGroupBox {
    border: 1px solid #e8eef2;
    border-radius: 4px;
    margin-top: 6px;
    font-size: 11px;
    font-weight: 600;
    color: #718096;
    text-transform: uppercase;
}
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 6px; }
/* 表格 */
QTableWidget { border: none; gridline-color: #e8eef2; }
QTableWidget::item:selected { background: #e8f4fd; color: #1a202c; }
QHeaderView::section {
    background: #f8fafb;
    border: none;
    border-bottom: 1px solid #e8eef2;
    font-size: 11px;
    font-weight: 600;
    color: #718096;
    padding: 6px 8px;
}
/* 滚动条 */
QScrollBar:vertical { width: 6px; background: transparent; }
QScrollBar::handle:vertical { background: #e8eef2; border-radius: 3px; min-height: 20px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
/* 分割线 */
QSplitter::handle { background: #e8eef2; }
QSplitter::handle:vertical { height: 1px; }
```

- [ ] **Step 2: 在 main.py 加载 QSS**

```python
# main.py — 在 window.show() 前插入
import os
qss_path = os.path.join(os.path.dirname(__file__), "assets", "theme_light.qss")
if os.path.exists(qss_path):
    with open(qss_path, encoding="utf-8") as f:
        app.setStyleSheet(f.read())
```

- [ ] **Step 3: Commit**

```bash
git add assets/theme_light.qss main.py
git commit -m "feat: QSS 浅色主题样式表"
```

---

## Task 4: 主窗口布局框架（app.py）

**Files:**
- Modify: `ui/app.py`

- [ ] **Step 1: 实现 LlamaLauncherApp**

```python
import os, winreg, logging
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter,
    QTabWidget, QFrame, QLabel, QSizePolicy
)
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtGui import QPalette, QColor

from core.config import ConfigStore
from core.events import EventBus
from core.process_manager import ProcessSupervisor, ProcessStatus
from core.model_resolver import ModelResolver
from ui.bridge import AppBridge
from ui.control_panel import ControlPanel
from ui.log_panel import LogPanel
from ui.widgets.monitor_panel import MonitorPanel
from ui.widgets.model_library_panel import ModelLibraryPanel
from ui.widgets.download_panel import DownloadPanel
from ui.widgets.chat_panel import ChatPanel
from ui.widgets.tray_icon import TrayIcon

logger = logging.getLogger(__name__)

class LlamaLauncherApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LLM Launcher")
        self.resize(1200, 800)

        self._config = ConfigStore("config.yaml")
        self._bus = EventBus()
        self._supervisor = ProcessSupervisor(self._bus)
        self._bridge = AppBridge(self._bus)

        self._build_ui()
        self._connect_signals()
        self._restore_geometry()
        self._tray = TrayIcon(self, self._supervisor, self._bus)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 左侧状态线
        self._status_line = QFrame()
        self._status_line.setFixedWidth(3)
        self._status_line.setStyleSheet("background:#1a9e6e;")
        root.addWidget(self._status_line)

        # 左侧面板 (tabs)
        left = QTabWidget()
        left.setFixedWidth(400)
        left.setObjectName("leftTabs")
        self._control = ControlPanel(self._config, self._supervisor)
        left.addTab(self._control, "控制")
        self._library = ModelLibraryPanel(self._config)
        left.addTab(self._library, "模型库")
        self._download = DownloadPanel(self._config)
        left.addTab(self._download, "下载")
        self._chat = ChatPanel(self._config)
        left.addTab(self._chat, "聊天")
        root.addWidget(left)

        # 右侧分栏（日志 70% / 监控 30%）
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        self._log_panel = LogPanel()
        self._monitor = MonitorPanel(self._supervisor)
        right_splitter.addWidget(self._log_panel)
        right_splitter.addWidget(self._monitor)
        right_splitter.setStretchFactor(0, 7)
        right_splitter.setStretchFactor(1, 3)
        root.addWidget(right_splitter, stretch=1)

        # 状态栏
        self._status_label = QLabel("已停止")
        self.statusBar().addWidget(self._status_label)
        self._port_label = QLabel("")
        self.statusBar().addPermanentWidget(self._port_label)

    def _connect_signals(self):
        self._bridge.status_changed.connect(self._on_status_changed)
        self._bridge.log_line.connect(self._log_panel.add_line)
        self._library.switch_model.connect(self._control.set_model_path)

    def _on_status_changed(self, status_value: str):
        status = ProcessStatus(status_value)
        colors = {
            ProcessStatus.RUNNING: "#1a9e6e",
            ProcessStatus.STOPPED: "#e8eef2",
            ProcessStatus.STARTING: "#d69e2e",
            ProcessStatus.ERROR: "#e53e3e",
        }
        color = colors.get(status, "#e8eef2")
        self._status_line.setStyleSheet(f"background:{color};")
        labels = {
            ProcessStatus.RUNNING: "运行中",
            ProcessStatus.STOPPED: "已停止",
            ProcessStatus.STARTING: "启动中",
            ProcessStatus.ERROR: "异常退出",
        }
        self._status_label.setText(labels.get(status, ""))
        port = self._config.get("server.port", 8080)
        self._port_label.setText(f":{port}" if status == ProcessStatus.RUNNING else "")

    def _restore_geometry(self):
        geo = self._config.get("app.window_geometry", "")
        if geo:
            self.restoreGeometry(QByteArray.fromBase64(geo.encode()))

    def closeEvent(self, event):
        geo_b64 = bytes(self.geometry().toRect().__repr__().encode())  # placeholder
        geo_b64 = bytes(self.saveGeometry().toBase64()).decode()
        self._config.set("app.window_geometry", geo_b64)
        self._config.save()
        if self._tray.isVisible():
            self.hide()
            event.ignore()
        else:
            self._supervisor.stop()
            event.accept()
```

- [ ] **Step 2: 运行验证布局**

```bash
python main.py
```
预期：主窗口出现，左侧 Tab（控制/模型库/下载/聊天），右侧上下分栏。各子面板为占位实现（下面各 Task 实现）。

- [ ] **Step 3: Commit**

```bash
git add ui/app.py
git commit -m "feat: 主窗口布局框架"
```

---

## Task 5: 控制面板（control_panel.py）

**Files:**
- Modify: `ui/control_panel.py`

控制面板包含：模型路径选择、llama-server 路径、基础参数（端口/上下文/GPU层数/并发/Host）、高级参数分组（折叠）、预设管理、启动/停止按钮。

- [ ] **Step 1: 实现 ControlPanel**

```python
import os, json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
    QGroupBox, QFormLayout, QFileDialog, QScrollArea,
    QSizePolicy, QCheckBox, QMessageBox
)
from PySide6.QtCore import Signal, Qt
from core.config import ConfigStore
from core.process_manager import ProcessSupervisor, ProcessStatus, PortInUseError, ProcessError
from ui.confirm_dialog import ConfirmDialog
from ui.widgets.param_groups import (
    KVCacheParams, InferenceParams, SamplingParams,
    ReasoningParams, MultimodalParams, SecurityParams
)

class ControlPanel(QWidget):
    set_model_path = Signal(str)

    def __init__(self, config: ConfigStore, supervisor: ProcessSupervisor):
        super().__init__()
        self._config = config
        self._supervisor = supervisor
        self._build_ui()
        self._restore()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)

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

        # llama-server 路径
        root.addWidget(QLabel("llama-server"))
        row3 = QHBoxLayout()
        self._server_path = QLineEdit()
        self._server_path.setReadOnly(True)
        self._btn_browse_server = QPushButton("浏览")
        self._btn_browse_server.clicked.connect(self._browse_server)
        row3.addWidget(self._server_path)
        row3.addWidget(self._btn_browse_server)
        root.addLayout(row3)

        # 基础参数
        basic = QGroupBox("基础参数")
        form = QFormLayout(basic)
        self._port = QSpinBox(); self._port.setRange(1024, 65535); self._port.setValue(8080)
        self._ctx = QComboBox(); self._ctx.addItems(["2048","4096","8192","16384","32768"])
        self._ngl = QSpinBox(); self._ngl.setRange(0, 9999); self._ngl.setValue(35)
        self._np = QComboBox(); self._np.addItems(["1","2","4","8"])
        self._host = QComboBox(); self._host.addItems(["127.0.0.1","0.0.0.0"])
        form.addRow("端口", self._port)
        form.addRow("上下文长度", self._ctx)
        form.addRow("GPU 层数", self._ngl)
        form.addRow("并发数", self._np)
        form.addRow("监听地址", self._host)
        root.addWidget(basic)

        # 高级参数（滚动区内各折叠分组）
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        adv_widget = QWidget()
        adv_layout = QVBoxLayout(adv_widget)
        adv_layout.setContentsMargins(0, 0, 0, 0)
        self._kv_params = KVCacheParams()
        self._inf_params = InferenceParams()
        self._samp_params = SamplingParams()
        self._rea_params = ReasoningParams()
        self._mm_params = MultimodalParams()
        self._sec_params = SecurityParams()
        for w in [self._kv_params, self._inf_params, self._samp_params,
                  self._rea_params, self._mm_params, self._sec_params]:
            adv_layout.addWidget(w)
        adv_layout.addStretch()
        scroll.setWidget(adv_widget)
        root.addWidget(scroll, stretch=1)

        # 预设管理
        preset_box = QGroupBox("预设")
        pl = QHBoxLayout(preset_box)
        self._preset_combo = QComboBox(); self._preset_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._btn_preset_save = QPushButton("保存")
        self._btn_preset_load = QPushButton("载入")
        self._btn_preset_delete = QPushButton("删除")
        self._btn_preset_export = QPushButton("导出")
        self._btn_preset_import = QPushButton("导入")
        for b in [self._preset_combo, self._btn_preset_save, self._btn_preset_load,
                  self._btn_preset_delete, self._btn_preset_export, self._btn_preset_import]:
            pl.addWidget(b)
        self._btn_preset_save.clicked.connect(self._save_preset)
        self._btn_preset_load.clicked.connect(self._load_preset)
        self._btn_preset_delete.clicked.connect(self._delete_preset)
        self._btn_preset_export.clicked.connect(self._export_presets)
        self._btn_preset_import.clicked.connect(self._import_presets)
        root.addWidget(preset_box)

        # 启停按钮
        btn_row = QHBoxLayout()
        self._btn_start = QPushButton("启动"); self._btn_start.setObjectName("btnStart")
        self._btn_stop = QPushButton("停止"); self._btn_stop.setObjectName("btnStop")
        self._btn_start.clicked.connect(self._start)
        self._btn_stop.clicked.connect(self._stop)
        btn_row.addWidget(self._btn_start)
        btn_row.addWidget(self._btn_stop)
        root.addLayout(btn_row)

        self._refresh_presets()

    def _browse_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择模型文件", "", "GGUF Files (*.gguf)")
        if path:
            self._model_path.setText(path)
            self._config.set("model.path", path)
            self._config.save()

    def _browse_mmproj(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 mmproj 文件", "", "GGUF Files (*.gguf)")
        if path:
            self._mmproj_path.setText(path)
            self._config.set("model.mmproj", path)
            self._config.save()

    def _browse_server(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 llama-server", "", "Executable (*.exe);;All Files (*)")
        if path:
            self._server_path.setText(path)
            self._config.set("app.llama_server_path", path)
            self._config.save()

    def collect_params(self) -> dict:
        params = {
            "model": self._model_path.text(),
            "mmproj": self._mmproj_path.text(),
            "server_path": self._server_path.text(),
            "port": self._port.value(),
            "ctx_size": int(self._ctx.currentText()),
            "n_gpu_layers": self._ngl.value(),
            "parallel": int(self._np.currentText()),
            "host": self._host.currentText(),
        }
        for w in [self._kv_params, self._inf_params, self._samp_params,
                  self._rea_params, self._mm_params, self._sec_params]:
            params.update(w.collect_params())
        return params

    def _restore(self):
        self._model_path.setText(self._config.get("model.path", ""))
        self._mmproj_path.setText(self._config.get("model.mmproj", ""))
        self._server_path.setText(self._config.get("app.llama_server_path", ""))
        self._port.setValue(self._config.get("server.port", 8080))
        ctx = str(self._config.get("server.ctx_size", 4096))
        idx = self._ctx.findText(ctx)
        if idx >= 0: self._ctx.setCurrentIndex(idx)
        self._ngl.setValue(self._config.get("server.n_gpu_layers", 35))
        np_val = str(self._config.get("server.parallel", 1))
        idx2 = self._np.findText(np_val)
        if idx2 >= 0: self._np.setCurrentIndex(idx2)
        host = self._config.get("server.host", "127.0.0.1")
        idx3 = self._host.findText(host)
        if idx3 >= 0: self._host.setCurrentIndex(idx3)

    def _start(self):
        params = self.collect_params()
        try:
            self._supervisor.start(params)
        except PortInUseError as e:
            QMessageBox.warning(self, "端口冲突", str(e))
        except ProcessError as e:
            QMessageBox.critical(self, "启动失败", str(e))

    def _stop(self):
        self._supervisor.stop()

    def _refresh_presets(self):
        self._preset_combo.clear()
        for name in self._config.get_presets():
            self._preset_combo.addItem(name)

    def _save_preset(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "保存预设", "预设名称:")
        if not ok or not name.strip():
            return
        if name in self._config.get_presets():
            dlg = ConfirmDialog(f"覆盖预设 "{name}"？", self)
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
        if "model" in preset: self._model_path.setText(preset["model"])
        if "port" in preset: self._port.setValue(preset["port"])
        if "ctx_size" in preset:
            idx = self._ctx.findText(str(preset["ctx_size"]))
            if idx >= 0: self._ctx.setCurrentIndex(idx)
        if "n_gpu_layers" in preset: self._ngl.setValue(preset["n_gpu_layers"])
        for w in [self._kv_params, self._inf_params, self._samp_params,
                  self._rea_params, self._mm_params, self._sec_params]:
            w.restore_params(preset)

    def _delete_preset(self):
        name = self._preset_combo.currentText()
        if not name:
            return
        dlg = ConfirmDialog(f"删除预设 "{name}"？", self)
        if dlg.exec():
            self._config.delete_preset(name)
            self._refresh_presets()

    def _export_presets(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出预设", "presets_export.json", "JSON (*.json)")
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
```

- [ ] **Step 2: 运行手动验证**

```bash
python main.py
```
预期：控制面板显示，浏览按钮弹出原生文件对话框，启动/停止按钮可点击。

- [ ] **Step 3: Commit**

```bash
git add ui/control_panel.py
git commit -m "feat: 控制面板（模型选择/参数/预设/启停）"
```

---

## Task 6: 参数分组（param_groups.py）

**Files:**
- Modify: `ui/widgets/param_groups.py`

每个分组实现为可折叠 QGroupBox，接口统一为 `collect_params() -> dict` 和 `restore_params(d: dict)`。

- [ ] **Step 1: 实现 param_groups.py**

```python
from PySide6.QtWidgets import (
    QGroupBox, QFormLayout, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QLineEdit, QWidget, QVBoxLayout, QPushButton
)

def _safe_int(v, default=0):
    try: return int(v)
    except: return default

def _safe_float(v, default=0.0):
    try: return float(v)
    except: return default


class _CollapsibleGroup(QGroupBox):
    def __init__(self, title: str):
        super().__init__(title)
        self.setCheckable(True)
        self.setChecked(True)  # 默认展开

    def collect_params(self) -> dict:
        raise NotImplementedError

    def restore_params(self, d: dict):
        raise NotImplementedError


class KVCacheParams(_CollapsibleGroup):
    def __init__(self):
        super().__init__("KV Cache 与显存")
        form = QFormLayout(self)
        self._ctk = QComboBox(); self._ctk.addItems(["f16","q8_0","q4_0"])
        self._ctv = QComboBox(); self._ctv.addItems(["f16","q8_0","q4_0"])
        self._kvu = QCheckBox("统一 KV 池")
        self._no_kv_offload = QCheckBox("KV 不放 GPU")
        self._fa = QCheckBox("Flash Attention")
        self._cache_prompt = QCheckBox("Prompt Cache")
        self._cache_idle = QCheckBox("空闲 Slot 复活")
        self._cache_ram = QSpinBox(); self._cache_ram.setRange(0, 999999); self._cache_ram.setValue(8192)
        form.addRow("KV-K 量化 (-ctk)", self._ctk)
        form.addRow("KV-V 量化 (-ctv)", self._ctv)
        form.addRow("", self._kvu)
        form.addRow("", self._no_kv_offload)
        form.addRow("", self._fa)
        form.addRow("", self._cache_prompt)
        form.addRow("", self._cache_idle)
        form.addRow("Cache RAM (MiB)", self._cache_ram)

    def collect_params(self):
        return {
            "ctk": self._ctk.currentText(),
            "ctv": self._ctv.currentText(),
            "kvu": self._kvu.isChecked(),
            "no_kv_offload": self._no_kv_offload.isChecked(),
            "flash_attn": self._fa.isChecked(),
            "cache_prompt": self._cache_prompt.isChecked(),
            "cache_idle_slots": self._cache_idle.isChecked(),
            "cache_ram": self._cache_ram.value() if self._cache_ram.value() != 8192 else None,
        }

    def restore_params(self, d: dict):
        if "ctk" in d: self._ctk.setCurrentText(d["ctk"])
        if "ctv" in d: self._ctv.setCurrentText(d["ctv"])
        if "kvu" in d: self._kvu.setChecked(d["kvu"])
        if "no_kv_offload" in d: self._no_kv_offload.setChecked(d["no_kv_offload"])
        if "flash_attn" in d: self._fa.setChecked(d["flash_attn"])
        if "cache_prompt" in d: self._cache_prompt.setChecked(d["cache_prompt"])
        if "cache_idle_slots" in d: self._cache_idle.setChecked(d["cache_idle_slots"])
        if "cache_ram" in d and d["cache_ram"]: self._cache_ram.setValue(d["cache_ram"])


class InferenceParams(_CollapsibleGroup):
    def __init__(self):
        super().__init__("推理速度")
        form = QFormLayout(self)
        self._threads = QSpinBox(); self._threads.setRange(-1, 256); self._threads.setValue(-1)
        self._threads_batch = QSpinBox(); self._threads_batch.setRange(-1, 256); self._threads_batch.setValue(-1)
        self._batch = QSpinBox(); self._batch.setRange(1, 65536); self._batch.setValue(2048)
        self._ubatch = QSpinBox(); self._ubatch.setRange(1, 65536); self._ubatch.setValue(512)
        self._threads_http = QSpinBox(); self._threads_http.setRange(-1, 256); self._threads_http.setValue(-1)
        self._no_warmup = QCheckBox("跳过预热")
        form.addRow("线程数 (-t)", self._threads)
        form.addRow("Prompt 线程 (-tb)", self._threads_batch)
        form.addRow("逻辑批大小 (-b)", self._batch)
        form.addRow("物理批大小 (-ub)", self._ubatch)
        form.addRow("HTTP 线程数", self._threads_http)
        form.addRow("", self._no_warmup)

    def collect_params(self):
        return {
            "threads": self._threads.value() if self._threads.value() != -1 else None,
            "threads_batch": self._threads_batch.value() if self._threads_batch.value() != -1 else None,
            "batch_size": self._batch.value(),
            "ubatch_size": self._ubatch.value(),
            "threads_http": self._threads_http.value() if self._threads_http.value() != -1 else None,
            "no_warmup": self._no_warmup.isChecked(),
        }

    def restore_params(self, d: dict):
        if "threads" in d and d["threads"]: self._threads.setValue(d["threads"])
        if "threads_batch" in d and d["threads_batch"]: self._threads_batch.setValue(d["threads_batch"])
        if "batch_size" in d: self._batch.setValue(d["batch_size"])
        if "ubatch_size" in d: self._ubatch.setValue(d["ubatch_size"])
        if "threads_http" in d and d["threads_http"]: self._threads_http.setValue(d["threads_http"])
        if "no_warmup" in d: self._no_warmup.setChecked(d["no_warmup"])


class SamplingParams(_CollapsibleGroup):
    def __init__(self):
        super().__init__("采样参数")
        form = QFormLayout(self)
        self._temp = QDoubleSpinBox(); self._temp.setRange(0.0, 2.0); self._temp.setValue(0.8); self._temp.setSingleStep(0.05)
        self._top_k = QSpinBox(); self._top_k.setRange(0, 1000); self._top_k.setValue(40)
        self._top_p = QDoubleSpinBox(); self._top_p.setRange(0.0, 1.0); self._top_p.setValue(0.95); self._top_p.setSingleStep(0.05)
        self._min_p = QDoubleSpinBox(); self._min_p.setRange(0.0, 1.0); self._min_p.setValue(0.05); self._min_p.setSingleStep(0.01)
        self._repeat_penalty = QDoubleSpinBox(); self._repeat_penalty.setRange(0.5, 2.0); self._repeat_penalty.setValue(1.0); self._repeat_penalty.setSingleStep(0.05)
        self._seed = QSpinBox(); self._seed.setRange(-1, 2**31-1); self._seed.setValue(-1)
        self._n_predict = QSpinBox(); self._n_predict.setRange(-1, 100000); self._n_predict.setValue(-1)
        self._ignore_eos = QCheckBox("忽略 EOS")
        form.addRow("Temperature", self._temp)
        form.addRow("Top-K", self._top_k)
        form.addRow("Top-P", self._top_p)
        form.addRow("Min-P", self._min_p)
        form.addRow("重复惩罚", self._repeat_penalty)
        form.addRow("随机种子", self._seed)
        form.addRow("最大生成长度", self._n_predict)
        form.addRow("", self._ignore_eos)

    def collect_params(self):
        return {
            "temperature": self._temp.value(),
            "top_k": self._top_k.value(),
            "top_p": self._top_p.value(),
            "min_p": self._min_p.value(),
            "repeat_penalty": self._repeat_penalty.value(),
            "seed": self._seed.value(),
            "n_predict": self._n_predict.value(),
            "ignore_eos": self._ignore_eos.isChecked(),
        }

    def restore_params(self, d: dict):
        if "temperature" in d: self._temp.setValue(d["temperature"])
        if "top_k" in d: self._top_k.setValue(d["top_k"])
        if "top_p" in d: self._top_p.setValue(d["top_p"])
        if "min_p" in d: self._min_p.setValue(d["min_p"])
        if "repeat_penalty" in d: self._repeat_penalty.setValue(d["repeat_penalty"])
        if "seed" in d: self._seed.setValue(d["seed"])
        if "n_predict" in d: self._n_predict.setValue(d["n_predict"])
        if "ignore_eos" in d: self._ignore_eos.setChecked(d["ignore_eos"])


class ReasoningParams(_CollapsibleGroup):
    def __init__(self):
        super().__init__("思考/推理模式")
        form = QFormLayout(self)
        self._rea = QComboBox(); self._rea.addItems(["auto","on","off"])
        self._rea_format = QComboBox(); self._rea_format.addItems(["none","deepseek","deepseek-legacy"])
        self._rea_budget = QSpinBox(); self._rea_budget.setRange(-1, 100000); self._rea_budget.setValue(-1)
        form.addRow("思考模式 (-rea)", self._rea)
        form.addRow("思考格式", self._rea_format)
        form.addRow("思考预算", self._rea_budget)

    def collect_params(self):
        return {
            "reasoning": self._rea.currentText(),
            "reasoning_format": self._rea_format.currentText() if self._rea_format.currentText() != "none" else None,
            "reasoning_budget": self._rea_budget.value(),
        }

    def restore_params(self, d: dict):
        if "reasoning" in d: self._rea.setCurrentText(d["reasoning"])
        if "reasoning_format" in d and d["reasoning_format"]: self._rea_format.setCurrentText(d["reasoning_format"])
        if "reasoning_budget" in d: self._rea_budget.setValue(d["reasoning_budget"])


class MultimodalParams(_CollapsibleGroup):
    def __init__(self):
        super().__init__("多模态")
        form = QFormLayout(self)
        self._mmproj_offload = QCheckBox("视觉编码器放 GPU")
        self._img_min = QSpinBox(); self._img_min.setRange(0, 10000); self._img_min.setValue(0)
        self._img_max = QSpinBox(); self._img_max.setRange(0, 10000); self._img_max.setValue(0)
        form.addRow("", self._mmproj_offload)
        form.addRow("最小视觉 Token", self._img_min)
        form.addRow("最大视觉 Token", self._img_max)

    def collect_params(self):
        return {
            "mmproj_offload": self._mmproj_offload.isChecked(),
            "image_min_tokens": self._img_min.value() if self._img_min.value() > 0 else None,
            "image_max_tokens": self._img_max.value() if self._img_max.value() > 0 else None,
        }

    def restore_params(self, d: dict):
        if "mmproj_offload" in d: self._mmproj_offload.setChecked(d["mmproj_offload"])
        if "image_min_tokens" in d and d["image_min_tokens"]: self._img_min.setValue(d["image_min_tokens"])
        if "image_max_tokens" in d and d["image_max_tokens"]: self._img_max.setValue(d["image_max_tokens"])


class SecurityParams(_CollapsibleGroup):
    def __init__(self):
        super().__init__("安全与访问控制")
        form = QFormLayout(self)
        self._api_key = QLineEdit(); self._api_key.setPlaceholderText("留空不传参")
        self._timeout = QSpinBox(); self._timeout.setRange(0, 86400); self._timeout.setValue(600)
        self._metrics = QCheckBox("Prometheus 监控 (--metrics)")
        self._slots = QCheckBox("Slots 端点 (--slots)")
        form.addRow("API Key", self._api_key)
        form.addRow("超时秒数", self._timeout)
        form.addRow("", self._metrics)
        form.addRow("", self._slots)

    def collect_params(self):
        return {
            "api_key": self._api_key.text() or None,
            "timeout": self._timeout.value(),
            "metrics": self._metrics.isChecked(),
            "slots": self._slots.isChecked(),
        }

    def restore_params(self, d: dict):
        if "api_key" in d and d["api_key"]: self._api_key.setText(d["api_key"])
        if "timeout" in d: self._timeout.setValue(d["timeout"])
        if "metrics" in d: self._metrics.setChecked(d["metrics"])
        if "slots" in d: self._slots.setChecked(d["slots"])
```

- [ ] **Step 2: Commit**

```bash
git add ui/widgets/param_groups.py
git commit -m "feat: 参数分组 Widget（6 组）"
```

---

## Task 7: 日志面板（log_panel.py）

**Files:**
- Modify: `ui/log_panel.py`

- [ ] **Step 1: 实现 LogPanel**

```python
from datetime import datetime
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QPlainTextEdit, QLabel
from PySide6.QtGui import QTextCharFormat, QColor, QFont
from PySide6.QtCore import Qt

class LogPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(12, 6, 12, 6)
        header.addWidget(QLabel("日志"))
        header.addStretch()
        btn_clear = QPushButton("清空")
        btn_copy = QPushButton("复制")
        btn_clear.clicked.connect(self.clear)
        btn_copy.clicked.connect(self.copy_all)
        header.addWidget(btn_clear)
        header.addWidget(btn_copy)
        layout.addLayout(header)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("DM Mono, Consolas, Courier New", 11))
        self._log.setMaximumBlockCount(5000)
        layout.addWidget(self._log)

    def add_line(self, line: str):
        ts = datetime.now().strftime("%H:%M:%S")
        # 颜色分级
        lower = line.lower()
        if any(k in lower for k in ["error", "failed", "oom", "killed"]):
            color = "#e53e3e"
        elif any(k in lower for k in ["warn", "warning"]):
            color = "#d69e2e"
        elif any(k in lower for k in ["loaded", "listening", "success", "ready"]):
            color = "#1a9e6e"
        else:
            color = "#718096"
        html = f'<span style="color:#a0aec0">{ts}</span> <span style="color:{color}">{line}</span>'
        self._log.appendHtml(html)

    def clear(self):
        self._log.clear()

    def copy_all(self):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._log.toPlainText())
```

- [ ] **Step 2: Commit**

```bash
git add ui/log_panel.py
git commit -m "feat: 日志面板（颜色分级/清空/复制）"
```

---

## Task 8: 监控面板（monitor_panel.py）

**Files:**
- Modify: `ui/widgets/monitor_panel.py`

监控改用 QThread 替代 Textual 的后台线程。

- [ ] **Step 1: 实现 MonitorPanel**

```python
import subprocess, logging
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame, QProgressBar
from PySide6.QtCore import QThread, Signal, QTimer
import psutil

logger = logging.getLogger(__name__)

class _MonitorWorker(QThread):
    stats_ready = Signal(dict)

    def __init__(self, pid_getter):
        super().__init__()
        self._pid_getter = pid_getter
        self._running = False

    def run(self):
        self._running = True
        while self._running:
            self.stats_ready.emit(self._collect())
            self.msleep(1000)

    def stop(self):
        self._running = False
        self.wait(2000)

    def _collect(self) -> dict:
        stats = {}
        # CPU
        stats["cpu_sys"] = psutil.cpu_percent(interval=None)
        pid = self._pid_getter()
        if pid:
            try:
                proc = psutil.Process(pid)
                stats["cpu_proc"] = proc.cpu_percent(interval=None) / psutil.cpu_count()
                stats["mem_proc_mb"] = proc.memory_info().rss / 1024 / 1024
            except psutil.NoSuchProcess:
                pass
        # RAM
        vm = psutil.virtual_memory()
        stats["mem_used_gb"] = vm.used / 1024**3
        stats["mem_total_gb"] = vm.total / 1024**3
        stats["mem_pct"] = vm.percent
        # GPU
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                timeout=2, stderr=subprocess.DEVNULL
            ).decode().strip()
            parts = out.split(",")
            stats["gpu_util"] = int(parts[0].strip())
            stats["vram_used_mb"] = int(parts[1].strip())
            stats["vram_total_mb"] = int(parts[2].strip())
        except Exception:
            pass
        return stats


class _StatCard(QFrame):
    def __init__(self, label: str, unit: str = ""):
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        self._lbl = QLabel(label.upper())
        self._lbl.setStyleSheet("font-size:10px;font-weight:600;color:#718096;")
        self._val = QLabel("—")
        self._val.setStyleSheet("font-family:'DM Mono',Consolas;font-size:20px;font-weight:500;")
        self._unit = unit
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(3)
        layout.addWidget(self._lbl)
        layout.addWidget(self._val)
        layout.addWidget(self._bar)

    def update(self, value_str: str, pct: int):
        self._val.setText(value_str)
        self._bar.setValue(max(0, min(100, pct)))


class MonitorPanel(QWidget):
    def __init__(self, supervisor):
        super().__init__()
        self._supervisor = supervisor
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        self._cpu_card = _StatCard("CPU", "%")
        self._ram_card = _StatCard("RAM", "GB")
        self._gpu_card = _StatCard("GPU", "%")
        self._vram_card = _StatCard("VRAM", "GB")
        for c in [self._cpu_card, self._ram_card, self._gpu_card, self._vram_card]:
            layout.addWidget(c)

        self._worker = _MonitorWorker(lambda: self._supervisor.pid)
        self._worker.stats_ready.connect(self._update)
        self._worker.start()

    def _update(self, stats: dict):
        self._cpu_card.update(f"{stats.get('cpu_sys', 0):.0f}%", int(stats.get('cpu_sys', 0)))
        mem_used = stats.get('mem_used_gb', 0)
        mem_total = stats.get('mem_total_gb', 1)
        self._ram_card.update(f"{mem_used:.1f}GB", int(stats.get('mem_pct', 0)))
        gpu_util = stats.get('gpu_util', 0)
        self._gpu_card.update(f"{gpu_util}%", gpu_util)
        vram_used = stats.get('vram_used_mb', 0) / 1024
        vram_total = stats.get('vram_total_mb', 1) / 1024
        vram_pct = int(vram_used / vram_total * 100) if vram_total > 0 else 0
        self._vram_card.update(f"{vram_used:.1f}GB", vram_pct)

    def closeEvent(self, event):
        self._worker.stop()
        super().closeEvent(event)
```

- [ ] **Step 2: Commit**

```bash
git add ui/widgets/monitor_panel.py
git commit -m "feat: 监控面板（QThread，CPU/RAM/GPU）"
```

---

## Task 9: 确认弹窗（confirm_dialog.py）

**Files:**
- Modify: `ui/confirm_dialog.py`

- [ ] **Step 1: 实现 ConfirmDialog**

```python
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout, QPushButton

class ConfirmDialog(QDialog):
    def __init__(self, message: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("确认")
        self.setFixedWidth(300)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(message))
        btns = QHBoxLayout()
        ok = QPushButton("确认"); ok.setObjectName("btnStop")
        cancel = QPushButton("取消")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        layout.addLayout(btns)
```

- [ ] **Step 2: Commit**

```bash
git add ui/confirm_dialog.py
git commit -m "feat: 确认弹窗 QDialog"
```

---

## Task 10: 模型库面板（model_library_panel.py）

**Files:**
- Modify: `ui/widgets/model_library_panel.py`

- [ ] **Step 1: 实现 ModelLibraryPanel**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add ui/widgets/model_library_panel.py
git commit -m "feat: 模型库面板（扫描/切换）"
```

---

## Task 11: 下载面板（download_panel.py）

**Files:**
- Modify: `ui/widgets/download_panel.py`

- [ ] **Step 1: 实现 DownloadPanel**

```python
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QProgressBar, QPlainTextEdit, QFileDialog
)
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import QCheckBox
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
    done = Signal(str)
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
                on_done=lambda fn: self.done.emit(fn),
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
        self._dest = QLineEdit(); self._dest.setText(config.get("app.model_dir", ""))
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
        self._dl_worker.done.connect(lambda fn: self._log.appendPlainText(f"完成: {fn}"))
        self._dl_worker.error.connect(lambda e: self._log.appendPlainText(f"错误: {e}"))
        self._progress_bar.setVisible(True)
        self._dl_worker.start()

    def _on_progress(self, filename: str, downloaded: int, total: int):
        pct = int(downloaded / total * 100) if total > 0 else 0
        self._progress_label.setText(f"{filename}  {format_size(downloaded)} / {format_size(total)}")
        self._progress_bar.setValue(pct)
```

- [ ] **Step 2: Commit**

```bash
git add ui/widgets/download_panel.py
git commit -m "feat: 下载面板（QThread 扫描/下载）"
```

---

## Task 12: 聊天面板（chat_panel.py）

**Files:**
- Modify: `ui/widgets/chat_panel.py`

- [ ] **Step 1: 实现 ChatPanel**

```python
import json, urllib.request
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QPlainTextEdit, QLabel
)
from PySide6.QtCore import QThread, Signal
from core.config import ConfigStore

class _ChatWorker(QThread):
    token = Signal(str)
    done = Signal()
    error = Signal(str)

    def __init__(self, port: int, messages: list, api_key: str = ""):
        super().__init__()
        self._port = port
        self._messages = messages
        self._api_key = api_key

    def run(self):
        try:
            url = f"http://127.0.0.1:{self._port}/v1/chat/completions"
            payload = json.dumps({"model": "local", "messages": self._messages, "stream": True}).encode()
            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            req = urllib.request.Request(url, data=payload, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                for raw in resp:
                    line = raw.decode().strip()
                    if line.startswith("data: ") and line != "data: [DONE]":
                        chunk = json.loads(line[6:])
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            self.token.emit(delta)
            self.done.emit()
        except Exception as e:
            self.error.emit(str(e))


class ChatPanel(QWidget):
    def __init__(self, config: ConfigStore):
        super().__init__()
        self._config = config
        self._messages = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        self._display = QPlainTextEdit()
        self._display.setReadOnly(True)
        layout.addWidget(self._display, stretch=1)

        row = QHBoxLayout()
        self._input = QLineEdit(); self._input.setPlaceholderText("输入消息…")
        self._input.returnPressed.connect(self._send)
        self._btn_send = QPushButton("发送"); self._btn_send.setObjectName("btnPrimary")
        self._btn_send.clicked.connect(self._send)
        self._btn_clear = QPushButton("清空历史")
        self._btn_clear.clicked.connect(self._clear)
        row.addWidget(self._input)
        row.addWidget(self._btn_send)
        row.addWidget(self._btn_clear)
        layout.addLayout(row)

    def _send(self):
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self._messages.append({"role": "user", "content": text})
        self._display.appendPlainText(f"\nUser: {text}\nAssistant: ")
        port = self._config.get("server.port", 8080)
        api_key = self._config.get("server.api_key", "")
        worker = _ChatWorker(port, list(self._messages), api_key)
        worker.token.connect(lambda t: self._display.insertPlainText(t))
        worker.done.connect(lambda: self._messages.append(
            {"role": "assistant", "content": self._display.toPlainText().split("Assistant: ")[-1]}
        ))
        worker.error.connect(lambda e: self._display.appendPlainText(f"\n[错误] {e}"))
        worker.start()

    def _clear(self):
        self._messages.clear()
        self._display.clear()
```

- [ ] **Step 2: Commit**

```bash
git add ui/widgets/chat_panel.py
git commit -m "feat: 聊天面板（流式输出）"
```

---

## Task 13: 系统托盘（tray_icon.py）

**Files:**
- Create: `ui/widgets/tray_icon.py`

- [ ] **Step 1: 实现 TrayIcon**

```python
import winreg
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PySide6.QtGui import QIcon, QColor, QPixmap
from PySide6.QtCore import QSize
from core.events import EventBus, EVENT_STATUS_CHANGED
from core.process_manager import ProcessSupervisor, ProcessStatus

def _make_icon(color: str) -> QIcon:
    px = QPixmap(16, 16)
    px.fill(QColor(color))
    return QIcon(px)

_ICONS = {
    "running": _make_icon("#1a9e6e"),
    "stopped": _make_icon("#718096"),
    "error":   _make_icon("#e53e3e"),
}

class TrayIcon(QSystemTrayIcon):
    def __init__(self, window, supervisor: ProcessSupervisor, bus: EventBus):
        super().__init__(_ICONS["stopped"], window)
        self._window = window
        self._supervisor = supervisor

        menu = QMenu()
        self._act_show = menu.addAction("显示窗口")
        menu.addSeparator()
        self._act_start = menu.addAction("启动服务")
        self._act_stop  = menu.addAction("停止服务")
        menu.addSeparator()
        act_quit = menu.addAction("退出")

        self._act_show.triggered.connect(self._show_window)
        self._act_start.triggered.connect(lambda: supervisor.start({}))
        self._act_stop.triggered.connect(supervisor.stop)
        act_quit.triggered.connect(self._quit)
        self.activated.connect(self._on_activated)

        self.setContextMenu(menu)
        self.show()

        bus.on(EVENT_STATUS_CHANGED, self._on_status)

    def _on_status(self, status: ProcessStatus):
        if status == ProcessStatus.RUNNING:
            self.setIcon(_ICONS["running"])
            self.setToolTip("LLM Launcher — 运行中")
        elif status == ProcessStatus.ERROR:
            self.setIcon(_ICONS["error"])
            self.setToolTip("LLM Launcher — 异常退出")
        else:
            self.setIcon(_ICONS["stopped"])
            self.setToolTip("LLM Launcher — 已停止")

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _show_window(self):
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def _quit(self):
        self._supervisor.stop()
        QApplication.quit()
```

- [ ] **Step 2: 开机自启开关（加入 control_panel.py 的安全组底部）**

在 `SecurityParams.collect_params` 和 `restore_params` 不涉及此项；开机自启在 `ControlPanel._build_ui` 尾部另加一行：

```python
# 在 ControlPanel._build_ui 的 action-bar 前插入
self._autostart = QCheckBox("开机自启")
self._autostart.setChecked(self._config.get("app.autostart", False))
self._autostart.stateChanged.connect(self._toggle_autostart)
root.addWidget(self._autostart)
```

```python
def _toggle_autostart(self, state):
    enabled = bool(state)
    self._config.set("app.autostart", enabled)
    self._config.save()
    key = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as k:
            if enabled:
                import sys
                winreg.SetValueEx(k, "LLMlauncher", 0, winreg.REG_SZ, sys.executable + ' "' + __file__ + '"')
            else:
                try: winreg.DeleteValue(k, "LLMlauncher")
                except FileNotFoundError: pass
    except Exception as e:
        import logging; logging.getLogger(__name__).warning("注册表写入失败: %s", e)
```

- [ ] **Step 3: Commit**

```bash
git add ui/widgets/tray_icon.py ui/control_panel.py
git commit -m "feat: 系统托盘 + 开机自启"
```

---

## Task 14: PyInstaller 打包脚本

**Files:**
- Create: `build.bat`
- Create: `llm_launcher.spec`（由 build.bat 生成后手动调整）

- [ ] **Step 1: 创建 build.bat**

```bat
@echo off
pip install pyinstaller
pyinstaller --noconfirm --onedir --windowed ^
  --name "llm-launcher" ^
  --add-data "assets;assets" ^
  --add-data "config.yaml;." ^
  --hidden-import "PySide6.QtSvg" ^
  --hidden-import "PySide6.QtXml" ^
  main.py
echo.
echo 打包完成，输出目录：dist\llm-launcher\
pause
```

- [ ] **Step 2: 运行打包**

```bat
build.bat
```
预期：`dist\llm-launcher\llm-launcher.exe` 生成，双击可运行。

- [ ] **Step 3: Commit**

```bash
git add build.bat
git commit -m "feat: PyInstaller 打包脚本"
```

---

## Task 15: 端到端冒烟测试

- [ ] **Step 1: 完整功能验收**

按顺序验证：
1. 启动 `python main.py`，窗口正常显示
2. 浏览选择模型文件，路径回填
3. 修改端口、GPU 层数，保存预设
4. 点击启动，日志面板输出 llama-server 日志
5. 监控面板显示 CPU/RAM/GPU 数值
6. 聊天面板发一条消息，收到流式回复
7. 关闭窗口 → 最小化到托盘；双击托盘图标 → 窗口恢复
8. 托盘右键 → 退出，应用退出
9. 重新启动，窗口大小与上次一致

- [ ] **Step 2: 运行现有测试套件**

```bash
pytest tests/ -v
```
预期：全部 PASS（bridge、config、process_manager 等）

- [ ] **Step 3: 最终 Commit**

```bash
git add -A
git commit -m "feat: Phase 4 GUI 重构完成"
```
