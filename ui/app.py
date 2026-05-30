import logging
import os
import sys
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
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
from ui.widgets.guide_panel import GuidePanel
from ui.widgets.usage_guide_panel import UsageGuidePanel
from ui.widgets.bench_panel import BenchPanel
from ui.widgets.tray_icon import TrayIcon

logger = logging.getLogger(__name__)


class LlamaLauncherApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LLM Launcher")
        self.resize(1200, 800)

        _base = os.path.dirname(os.path.abspath(sys.argv[0]))
        self._config = ConfigStore(os.path.join(_base, "config.yaml"))
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

        # 左侧面板：只有控制面板
        self._control = ControlPanel(self._config, self._supervisor)
        self._control.setFixedWidth(400)
        root.addWidget(self._control)

        # 右侧：上方 Tab（日志/模型库/下载/聊天） + 下方监控(30%)
        right_splitter = QSplitter(Qt.Orientation.Vertical)

        self._right_tabs = QTabWidget()
        self._log_panel = LogPanel()
        self._library = ModelLibraryPanel(self._config)
        self._download = DownloadPanel(self._config)
        self._chat = ChatPanel(self._config)
        self._usage_guide = UsageGuidePanel()
        self._guide = GuidePanel()
        self._bench = BenchPanel(self._config, self._library)
        self._right_tabs.addTab(self._log_panel, "日志")
        self._right_tabs.addTab(self._library, "模型库")
        self._right_tabs.addTab(self._download, "下载")
        self._right_tabs.addTab(self._chat, "聊天")
        self._right_tabs.addTab(self._bench, "Bench")
        self._right_tabs.tabBar().setExpanding(False)

        # 使用指南 + 参数指南 作为右上角 cornerWidget，视觉上在最右侧
        from PySide6.QtWidgets import QTabBar, QPushButton, QWidget as CornerWidget
        from PySide6.QtWidgets import QHBoxLayout as CornerHBox
        _corner = CornerWidget()
        _cl = CornerHBox(_corner)
        _cl.setContentsMargins(0, 0, 4, 0)
        _cl.setSpacing(2)
        _btn_usage = QPushButton("使用指南")
        _btn_guide = QPushButton("参数指南")
        for btn in (_btn_usage, _btn_guide):
            btn.setCheckable(True)
            btn.setStyleSheet(
                "QPushButton{font-size:12px;padding:4px 10px;border:1px solid #cbd5e0;"
                "border-radius:4px;background:#f7fafc;color:#4a5568;}"
                "QPushButton:checked{background:#ebf8ff;color:#2b6cb0;border-color:#90cdf4;}"
                "QPushButton:hover{background:#edf2f7;}"
            )
            _cl.addWidget(btn)
        self._right_tabs.setCornerWidget(_corner, Qt.Corner.TopRightCorner)

        # 指南页不作为常规 Tab，而是通过 corner 按钮切换 overlay
        self._usage_guide.setVisible(False)
        self._guide.setVisible(False)
        self._guide_overlay = QFrame()
        self._guide_overlay.setStyleSheet("QFrame{background:#f7fafc;}")
        _overlay_layout = QVBoxLayout(self._guide_overlay)
        _overlay_layout.setContentsMargins(0, 0, 0, 0)
        _overlay_layout.addWidget(self._usage_guide)
        _overlay_layout.addWidget(self._guide)

        # 切换逻辑
        def _show_guide(which: str):
            is_usage = (which == "usage")
            self._usage_guide.setVisible(is_usage)
            self._guide.setVisible(not is_usage)
            _btn_usage.setChecked(is_usage)
            _btn_guide.setChecked(not is_usage)
            # 在日志 Tab 位置显示 overlay
            idx = self._right_tabs.indexOf(self._log_panel)
            if self._right_tabs.count() > 5:
                self._right_tabs.removeTab(self._right_tabs.indexOf(self._guide_overlay))
            self._right_tabs.insertTab(0, self._guide_overlay, "📋 " + ("使用指南" if is_usage else "参数指南"))
            self._right_tabs.setCurrentWidget(self._guide_overlay)

        def _toggle_guide(which: str):
            btn = _btn_usage if which == "usage" else _btn_guide
            other_btn = _btn_guide if which == "usage" else _btn_usage
            if btn.isChecked():
                _show_guide(which)
            else:
                other_btn.setChecked(False)
                if self._right_tabs.indexOf(self._guide_overlay) >= 0:
                    self._right_tabs.removeTab(self._right_tabs.indexOf(self._guide_overlay))
                self._right_tabs.setCurrentWidget(self._log_panel)

        _btn_usage.clicked.connect(lambda: _toggle_guide("usage"))
        _btn_guide.clicked.connect(lambda: _toggle_guide("guide"))

        self._monitor = MonitorPanel(self._supervisor)
        right_splitter.addWidget(self._right_tabs)
        right_splitter.addWidget(self._monitor)
        right_splitter.setStretchFactor(0, 7)
        right_splitter.setStretchFactor(1, 3)
        root.addWidget(right_splitter, stretch=1)

        # 状态栏
        self._status_label = QLabel("已停止")
        self._status_label.setStyleSheet("color:#718096; font-weight:bold;")
        self.statusBar().addWidget(self._status_label)
        self._port_label = QLabel("")
        self.statusBar().addPermanentWidget(self._port_label)

    def _connect_signals(self):
        self._bridge.status_changed.connect(self._on_status_changed)
        self._bridge.log_line.connect(self._log_panel.add_line)
        self._library.switch_model.connect(self._control.on_switch_model)
        self._control.started.connect(self._chat.update_model_info)

    def _on_status_changed(self, status_value: str):
        try:
            status = ProcessStatus(status_value)
        except ValueError:
            return
        colors = {
            ProcessStatus.RUNNING:  "#1a9e6e",
            ProcessStatus.STOPPED:  "#718096",
            ProcessStatus.STARTING: "#d69e2e",
            ProcessStatus.CRASHED:  "#e53e3e",
        }
        color = colors.get(status, "#718096")
        self._status_line.setStyleSheet(f"background:{color};")
        labels = {
            ProcessStatus.RUNNING:  "运行中",
            ProcessStatus.STOPPED:  "已停止",
            ProcessStatus.STARTING: "启动中...",
            ProcessStatus.CRASHED:  "异常退出",
        }
        self._status_label.setText(labels.get(status, ""))
        self._status_label.setStyleSheet(f"color:{color}; font-weight:bold;")
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
            # 等待进程释放端口（最多 5 秒），避免重启时端口冲突
            import time
            for _ in range(50):
                if self._supervisor.pid is None:
                    break
                time.sleep(0.1)
            event.accept()
