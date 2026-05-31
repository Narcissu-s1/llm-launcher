# core/events.py
"""异步事件总线：将事件放入队列，由单一 dispatch 线程消费并同步调用 subscriber"""

import logging
import threading
from queue import Queue, Empty
from typing import Callable

logger = logging.getLogger(__name__)

# 核心事件名称常量
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
        self._started = False

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
        if event not in self._subscribers:
            self._subscribers[event] = []
        self._subscribers[event].append(callback)

    def off(self, event: str, callback: Callable) -> None:
        """取消订阅"""
        if event in self._subscribers:
            try:
                self._subscribers[event].remove(callback)
            except ValueError:
                pass

    def _process_event(self, event: str, data: dict) -> None:
        """处理单个事件，同步调用所有 subscriber"""
        callbacks = self._subscribers.get(event, [])
        for callback in callbacks:
            try:
                callback(**data)
            except Exception:
                logger.warning(
                    "EventBus subscriber exception: event=%s, callback=%s",
                    event, getattr(callback, "__name__", str(callback)),
                    exc_info=True
                )

    def _dispatch_loop(self) -> None:
        """Dispatch 线程：从队列消费事件，同步调用所有 subscriber"""
        while not self._stop_dispatch.is_set():
            try:
                event, data = self._queue.get(timeout=0.1)
            except Empty:
                continue

            callbacks = self._subscribers.get(event, [])
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
        # 首次 emit 在调用线程同步处理，避免异步导致的时序问题
        if self._dispatch_thread is None:
            self._process_event(event, data)
            return
        self._ensure_dispatch_started()
        self._queue.put((event, data))

    def _ensure_dispatch_started(self) -> None:
        """启动 dispatch 线程（惰性启动）"""
        if self._dispatch_thread is None or not self._dispatch_thread.is_alive():
            self._stop_dispatch.clear()
            self._dispatch_thread = threading.Thread(target=self._dispatch_loop, daemon=True)
            self._dispatch_thread.start()

    def _dispatch_loop(self) -> None:
        """Dispatch 线程：从队列消费事件，同步调用所有 subscriber"""
        while not self._stop_dispatch.is_set():
            try:
                event, data = self._queue.get(timeout=0.1)
            except Empty:
                continue

            callbacks = self._subscribers.get(event, [])
            for callback in callbacks:
                try:
                    callback(**data)
                except Exception:
                    logger.warning(
                        "EventBus subscriber exception: event=%s, callback=%s",
                        event, getattr(callback, "__name__", str(callback)),
                        exc_info=True
                    )

    def stop(self) -> None:
        """停止 dispatch 线程（用于测试和优雅退出）"""
        self._stop_dispatch.set()
        if self._dispatch_thread is not None:
            self._dispatch_thread.join(timeout=2)
            self._dispatch_thread = None