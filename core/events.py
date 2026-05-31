# core/events.py
"""异步事件总线：将事件放入队列，由单一 dispatch 线程消费并同步调用 subscriber"""

import logging
import threading
from queue import Queue, Empty
from typing import Callable

logger = logging.getLogger(__name__)

# 核心事件名称常量，统一引用避免拼写错误
EVENT_STATUS_CHANGED = "status_changed"
EVENT_LOG_LINE = "log_line"
EVENT_ERROR = "error"
EVENT_STATS_UPDATE = "stats_update"


class EventBus:
    """异步发布/订阅事件总线"""

    _instance: "EventBus | None" = None
    _lock = threading.Lock()

    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = {}
        self._queue: Queue = Queue()
        self._dispatch_thread: threading.Thread | None = None
        self._stop_dispatch = threading.Event()
        self._flush_event = threading.Event()

    @classmethod
    def get_instance(cls) -> "EventBus":
        """单例访问器 — 确保整个应用只有一个事件总线"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def on(self, event: str, callback: Callable) -> None:
        """订阅事件"""
        with self._lock:
            if event not in self._subscribers:
                self._subscribers[event] = []
            self._subscribers[event].append(callback)

    def off(self, event: str, callback: Callable) -> None:
        """取消订阅"""
        with self._lock:
            if event in self._subscribers:
                try:
                    self._subscribers[event].remove(callback)
                except ValueError:
                    pass

    def _dispatch_loop(self) -> None:
        """Dispatch 线程：从队列消费事件，同步调用所有 subscriber"""
        while not self._stop_dispatch.is_set():
            try:
                event, data = self._queue.get(timeout=0.1)
            except Empty:
                continue

            # 哨兵：flush() 发送的空事件，用于同步等待
            if event is None:
                self._flush_event.set()
                continue

            with self._lock:
                callbacks = list(self._subscribers.get(event, []))

            for callback in callbacks:
                try:
                    callback(**data)
                except Exception:
                    logger.warning(
                        "EventBus subscriber exception: event=%s, callback=%s",
                        event, getattr(callback, "__name__", str(callback)),
                        exc_info=True
                    )

    def emit(self, event: str, **data) -> None:
        """将事件放入队列，立即返回（不阻塞当前线程）"""
        self._ensure_dispatch_started()
        self._queue.put((event, data))

    def flush(self) -> None:
        """等待队列中所有事件处理完成（用于测试同步验证）"""
        self._flush_event.clear()
        self._queue.put((None, None))  # 哨兵，强制 dispatch_loop 迭代
        self._flush_event.wait(timeout=5)  # 等待 dispatch 处理完队列

    def _ensure_dispatch_started(self) -> None:
        """启动 dispatch 线程（惰性启动，单例模式）"""
        if self._dispatch_thread is None or not self._dispatch_thread.is_alive():
            self._stop_dispatch.clear()
            self._dispatch_thread = threading.Thread(target=self._dispatch_loop, daemon=True)
            self._dispatch_thread.start()

    def stop(self) -> None:
        """停止 dispatch 线程（用于测试和优雅退出）"""
        self._stop_dispatch.set()
        if self._dispatch_thread is not None:
            self._dispatch_thread.join(timeout=2)
            self._dispatch_thread = None