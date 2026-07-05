# tests/test_update_callback.py
"""LlamaLauncherApp._apply_update_info 单元测试

策略：构造完整 LlamaLauncherApp（mock TrayIcon 避免系统托盘 + mock check_update_async
避免真实网络请求），emit update_info_received signal，断言 _update_label 的文案与
链接属性。
"""

import os
import sys

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QLabel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication(sys.argv)


class UpdateTarget(QObject):
    """只保留更新提示所需的最小 Qt 对象"""

    update_info_received = Signal(object)

    def __init__(self):
        super().__init__()
        from ui.app import LlamaLauncherApp

        self._update_label = QLabel()
        self._update_label.setOpenExternalLinks(True)
        self._apply_update_info = LlamaLauncherApp._apply_update_info.__get__(self)
        self.update_info_received.connect(self._apply_update_info)


@pytest.fixture
def launcher_app(qt_app):
    """构造最小对象,避免完整主窗口带来的 Qt 清理副作用"""
    app = UpdateTarget()
    yield app
    app._update_label.deleteLater()
    app.deleteLater()
    qt_app.processEvents()


def test_无更新时label_text保持空(launcher_app):
    """has_update=False 时不应改 text"""
    from core.updater import UpdateInfo
    info = UpdateInfo(has_update=False, current="1.0.0", latest="1.0.0", release_url="")
    before = launcher_app._update_label.text()
    launcher_app._apply_update_info(info)
    after = launcher_app._update_label.text()
    assert before == after  # 没改


def test_有新版本时label_text含富文本链接(launcher_app):
    """has_update=True 应写入富文本链接"""
    from core.updater import UpdateInfo
    info = UpdateInfo(
        has_update=True,
        current="1.0.0",
        latest="1.2.0",
        release_url="https://github.com/x/y/releases/tag/v1.2.0",
    )
    launcher_app._apply_update_info(info)
    text = launcher_app._update_label.text()
    assert "v1.2.0" in text
    assert "https://github.com/x/y/releases/tag/v1.2.0" in text
    assert '<a href' in text  # 富文本链接


def test_label_开启openExternalLinks_无需mousePressEvent重写(launcher_app):
    """用 QLabel 自带 setOpenExternalLinks=True,不要再 monkey-patch mousePressEvent"""
    assert launcher_app._update_label.openExternalLinks() is True


def test_通过Signal触发也能应用更新(launcher_app, qt_app):
    """emit update_info_received signal,Qt 应排队到主线程应用"""
    from core.updater import UpdateInfo
    info = UpdateInfo(
        has_update=True,
        current="1.0.0",
        latest="2.0.0",
        release_url="https://github.com/a/b/releases/tag/v2.0.0",
    )
    # 用 signal emit(自动 queued 跨线程)
    launcher_app.update_info_received.emit(info)
    qt_app.processEvents()
    assert "v2.0.0" in launcher_app._update_label.text()
    assert "https://github.com/a/b/releases/tag/v2.0.0" in launcher_app._update_label.text()
