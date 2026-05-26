# tests/test_events.py
"""EventBus 单元测试"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.events import EventBus, EVENT_STATUS_CHANGED


def test_注册并触发事件():
    """测试基本发布/订阅流程"""
    bus = EventBus()
    received = []

    bus.on("test_event", lambda **data: received.append(data))
    bus.emit("test_event", msg="hello")

    assert len(received) == 1
    assert received[0]["msg"] == "hello"


def test_取消订阅():
    """测试取消注册后不再收到事件"""
    bus = EventBus()
    received = []

    def handler(**data):
        received.append(data)

    bus.on("test", handler)
    bus.off("test", handler)
    bus.emit("test", x=1)

    assert len(received) == 0


def test_多个订阅者():
    """测试同一事件有多个订阅者"""
    bus = EventBus()
    results = []

    bus.on("multi", lambda **d: results.append("a"))
    bus.on("multi", lambda **d: results.append("b"))
    bus.emit("multi")

    assert results == ["a", "b"]


def test_回调异常不影响其他订阅者():
    """测试一个订阅者抛异常不影响其他订阅者"""
    bus = EventBus()
    results = []

    def bad_handler(**data):
        raise RuntimeError("我挂了")

    bus.on("test", bad_handler)
    bus.on("test", lambda **d: results.append("ok"))
    bus.emit("test")

    assert results == ["ok"]


def test_不存在的事件不会报错():
    """emit 未注册的事件不应报错"""
    bus = EventBus()
    bus.emit("nobody_listens")  # 不应抛异常


def test_使用事件常量():
    """测试使用命名事件常量进行发布/订阅"""
    bus = EventBus()
    received = []

    bus.on(EVENT_STATUS_CHANGED, lambda **d: received.append(d))
    bus.emit(EVENT_STATUS_CHANGED, status="running")

    assert len(received) == 1
    assert received[0]["status"] == "running"
