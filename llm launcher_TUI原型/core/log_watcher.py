# core/log_watcher.py
"""日志监控器：读取 subprocess 的 stdout/stderr 管道并推送事件"""

import logging
import threading

from core.events import EventBus, EVENT_LOG_LINE

logger = logging.getLogger(__name__)

# 需要高亮的关键词映射
KEYWORD_EVENTS = {
    "error": "log_error",
    "cuda error": "log_error",
    "out of memory": "log_oom",
    "server is listening": "log_ready",
}


class LogMonitor:
    """读取 subprocess stdout/stderr pipe，逐行推送到 EventBus

    LogMonitor 作为独立模块提供，也可以被 ProcessSupervisor 内嵌使用。
    Phase 1 中 ProcessSupervisor 已内嵌了日志读取功能，
    此模块为后续扩展（如多进程日志聚合）预留接口。
    """

    def __init__(self, event_bus: EventBus):
        """初始化日志监控器

        Args:
            event_bus: 事件总线
        """
        self._event_bus = event_bus
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def attach(self, pipe) -> None:
        """启动后台线程读取管道

        管道通常来自 subprocess.Popen 的 stdout 或 stderr。
        由于 ProcessSupervisor 已将 stderr 合并到 stdout，
        只需传入一个 pipe 即可。

        Args:
            pipe: subprocess 的 stdout/stderr 管道（需支持 readline）
        """
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._read_loop,
            args=(pipe,),
            daemon=True,
        )
        self._thread.start()

    def detach(self) -> None:
        """停止后台读取线程"""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _read_loop(self, pipe) -> None:
        """循环读取管道，逐行发送 log_line 事件"""
        while not self._stop_event.is_set():
            line = pipe.readline()
            if not line:
                break  # pipe 已关闭

            line = line.rstrip()
            if not line:
                continue

            self._event_bus.emit(EVENT_LOG_LINE, line=line)

            # 检测关键词，发送额外事件
            line_lower = line.lower()
            for keyword, event_name in KEYWORD_EVENTS.items():
                if keyword in line_lower:
                    self._event_bus.emit(event_name, line=line)
                    break  # 每行只触发一种关键词事件
