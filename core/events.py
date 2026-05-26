# core/events.py
"""简单发布/订阅事件总线，用于解耦核心层和 UI 层"""

import logging
from typing import Callable

logger = logging.getLogger(__name__)

# 核心事件名称常量，统一引用避免拼写错误
EVENT_STATUS_CHANGED = "status_changed"
EVENT_LOG_LINE = "log_line"
EVENT_ERROR = "error"
EVENT_STATS_UPDATE = "stats_update"


class EventBus:
    """轻量级发布/订阅事件总线"""

    def __init__(self):
        """初始化订阅字典"""
        self._subscribers: dict[str, list[Callable]] = {}

    def on(self, event: str, callback: Callable) -> None:
        """订阅事件

        Args:
            event: 事件名称
            callback: 回调函数，接收 **data 关键字参数
        """
        if event not in self._subscribers:
            self._subscribers[event] = []
        self._subscribers[event].append(callback)

    def off(self, event: str, callback: Callable) -> None:
        """取消订阅事件

        Args:
            event: 事件名称
            callback: 要移除的回调函数
        """
        if event in self._subscribers:
            try:
                self._subscribers[event].remove(callback)
            except ValueError:
                pass  # 回调不存在，忽略

    def emit(self, event: str, **data) -> None:
        """触发事件，向所有订阅者传递数据

        Args:
            event: 事件名称
            **data: 传递给回调的关键字参数
        """
        if event not in self._subscribers:
            return

        for callback in self._subscribers[event]:
            try:
                callback(**data)
            except Exception:
                logger.warning(
                    "EventBus 回调异常: event=%s, callback=%s",
                    event, callback.__name__,
                    exc_info=True
                )
