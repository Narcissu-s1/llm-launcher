import pytest
import threading
from core.events import EventBus


def test_basic_subscribe_and_emit():
    bus = EventBus()
    results = []
    def handler(value, **kw):
        results.append(value)
    bus.on("test_event", handler)
    bus.emit("test_event", value=42)
    bus.flush()
    assert results == [42]


def test_multiple_subscribers_all_called():
    bus = EventBus()
    a_results, b_results = [], []
    bus.on("e", lambda **kw: a_results.append(1))
    bus.on("e", lambda **kw: b_results.append(1))
    bus.emit("e")
    bus.flush()
    assert a_results == [1]
    assert b_results == [1]


def test_subscriber_exception_does_not_break_chain():
    bus = EventBus()
    results = []
    def bad(**kw):
        raise RuntimeError("intentional")
    def good(**kw):
        results.append(1)
    bus.on("e", bad)
    bus.on("e", good)
    bus.emit("e")  # 不应抛出
    bus.flush()
    assert results == [1]


def test_cross_thread_emit():
    bus = EventBus()
    results = []
    def handler(value, **kw):
        results.append(value)
    bus.on("cross", handler)
    t = threading.Thread(target=lambda: bus.emit("cross", value="from_bg"))
    t.start()
    t.join(timeout=2)
    assert "from_bg" in results


def test_unsubscribe():
    bus = EventBus()
    results = []
    def h(**kw): results.append(1)
    bus.on("e", h)
    bus.off("e", h)
    bus.emit("e")
    assert results == []