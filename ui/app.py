import logging
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter,
    QTabWidget, QFrame, QLabel, QSizePolicy
)
from PySide6.QtCore import Qt, QByteArray

from core.config import ConfigStore
from core.events import EventBus
from core.process_manager import ProcessSupervisor, ProcessStatus
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

        # 左侧状态线 (3px)
        self._status_line = QFrame()
        self._status_line.setFixedWidth(3)
        self._status_line.setStyleSheet("background:#cbd5e0;")
        root.addWidget(self._status_line)

        # 左侧面板 (tabs)
        left = QTabWidget()
        left.setFixedWidth(400)
        self._control = ControlPanel(self._config, self._supervisor)
        self._library = ModelLibraryPanel(self._config)
        self._download = DownloadPanel(self._config)
        self._chat = ChatPanel(self._config)
        left.addTab(self._control, "控制")
        left.addTab(self._library, "模型库")
        left.addTab(self._download, "下载")
        left.addTab(self._chat, "聊天")
        root.addWidget(left)

        # 右侧：日志(70%) / 监控(30%) 上下分栏
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
        self._library.switch_model.connect(self._control.on_switch_model)

    def _on_status_changed(self, status_value: str):
        try:
            status = ProcessStatus(status_value)
        except ValueError:
            return
        colors = {
            ProcessStatus.RUNNING: "#1a9e6e",
            ProcessStatus.STOPPED: "#cbd5e0",
            ProcessStatus.STARTING: "#d69e2e",
            ProcessStatus.CRASHED: "#e53e3e",
        }
        color = colors.get(status, "#cbd5e0")
        self._status_line.setStyleSheet(f"background:{color};")
        labels = {
            ProcessStatus.RUNNING: "运行中",
            ProcessStatus.STOPPED: "已停止",
            ProcessStatus.STARTING: "启动中...",
            ProcessStatus.CRASHED: "异常退出",
        }
        self._status_label.setText(labels.get(status, ""))
        port = self._config.get("server.port") or 8080
        self._port_label.setText(f":{port}" if status == ProcessStatus.RUNNING else "")

    def _restore_geometry(self):
        geo = self._config.get("app.window_geometry") or ""
        if geo:
            self.restoreGeometry(QByteArray.fromBase64(geo.encode()))

    def closeEvent(self, event):
        geo_b64 = bytes(self.saveGeometry().toBase64()).decode()
        self._config.set("app.window_geometry", geo_b64)
        if self._tray.isVisible():
            self.hide()
            event.ignore()
        else:
            self._supervisor.stop()
            event.accept()
