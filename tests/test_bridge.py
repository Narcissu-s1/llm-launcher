"""tests/test_bridge.py — AppBridge 单元测试"""

import sys
import pytest
from PySide6.QtWidgets import QApplication


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
    bus.emit(EVENT_LOG_LINE, line="hello")
    assert received == ["hello"]


def test_bridge_emits_status_changed(qt_app):
    from core.events import EventBus, EVENT_STATUS_CHANGED
    from ui.bridge import AppBridge

    bus = EventBus()
    bridge = AppBridge(bus)
    received = []
    bridge.status_changed.connect(received.append)
    bus.emit(EVENT_STATUS_CHANGED, status="running", old_status="stopped")
    assert received == ["running"]


def test_bridge_emits_stats_update(qt_app):
    from core.events import EventBus, EVENT_STATS_UPDATE
    from ui.bridge import AppBridge

    bus = EventBus()
    bridge = AppBridge(bus)
    received = []
    bridge.stats_update.connect(received.append)
    bus.emit(EVENT_STATS_UPDATE, cpu=12.5, memory=1024)
    assert len(received) == 1
    assert received[0]["cpu"] == 12.5
    assert received[0]["memory"] == 1024
