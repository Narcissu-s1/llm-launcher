"""LogMonitor 就绪日志兼容性测试。"""

from io import StringIO

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from core.events import EventBus
from core.log_watcher import LogMonitor


@pytest.mark.parametrize("line", [
    "main: server is listening on http://127.0.0.1:8080\n",
    "0.00.102 I srv llama_server: listening on http://127.0.0.1:8080\n",
])
def test_旧版与新版监听日志均触发就绪事件(line):
    """日志监控器应与进程管理器使用相同的就绪判断。"""
    bus = EventBus()
    ready_events = []
    bus.on("log_ready", lambda **d: ready_events.append(d))
    monitor = LogMonitor(bus)

    monitor._read_loop(StringIO(line))
    bus.flush()

    assert len(ready_events) == 1
    assert ready_events[0]["line"] == line.rstrip()
