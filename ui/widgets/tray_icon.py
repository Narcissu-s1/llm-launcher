# ui/widgets/tray_icon.py
"""系统托盘图标：状态显示、快捷操作、双击还原窗口"""

import os
import sys
import winreg

from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PySide6.QtGui import QIcon, QColor, QPixmap

from core.events import EventBus, EVENT_STATUS_CHANGED
from core.process_manager import ProcessSupervisor, ProcessStatus

_REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_REG_VALUE_NAME = "LLMlauncher"


def _make_icon(color: str) -> QIcon:
    px = QPixmap(16, 16)
    px.fill(QColor(color))
    return QIcon(px)


class TrayIcon(QSystemTrayIcon):
    def __init__(self, window, supervisor: ProcessSupervisor, bus: EventBus):
        # 延迟创建图标，确保 QApplication 已存在
        self._icons = {
            "running":  _make_icon("#1a9e6e"),
            "stopped":  _make_icon("#718096"),
            "starting": _make_icon("#d69e2e"),
            "error":    _make_icon("#e53e3e"),
        }
        super().__init__(self._icons["stopped"], window)
        self._window = window
        self._supervisor = supervisor

        menu = QMenu()
        self._act_show  = menu.addAction("显示窗口")
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
        self.setToolTip("LLM Launcher — 已停止")
        self.show()

        bus.on(EVENT_STATUS_CHANGED, self._on_status)

    def _on_status(self, status: ProcessStatus, **kw):
        if status == ProcessStatus.RUNNING:
            self.setIcon(self._icons["running"])
            self.setToolTip("LLM Launcher — 运行中")
        elif status == ProcessStatus.STARTING:
            self.setIcon(self._icons["starting"])
            self.setToolTip("LLM Launcher — 启动中...")
        elif status == ProcessStatus.CRASHED:
            self.setIcon(self._icons["error"])
            self.setToolTip("LLM Launcher — 异常退出")
        else:
            self.setIcon(self._icons["stopped"])
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


def set_autostart(enabled: bool) -> None:
    """设置或取消开机自启注册表项"""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _REGISTRY_KEY,
            0,
            winreg.KEY_SET_VALUE,
        )
        if enabled:
            value = f'{sys.executable} "{os.path.abspath("main.py")}"'
            winreg.SetValueEx(key, _REG_VALUE_NAME, 0, winreg.REG_SZ, value)
        else:
            try:
                winreg.DeleteValue(key, _REG_VALUE_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except OSError:
        pass


def get_autostart() -> bool:
    """读取注册表，判断是否已设置开机自启"""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _REGISTRY_KEY,
            0,
            winreg.KEY_READ,
        )
        winreg.QueryValueEx(key, _REG_VALUE_NAME)
        winreg.CloseKey(key)
        return True
    except (FileNotFoundError, OSError):
        return False
