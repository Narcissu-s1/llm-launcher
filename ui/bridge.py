"""EventBus → Qt Signal 桥接层

将后台线程触发的 EventBus 事件转为 Qt Signal，
Qt 会自动以 queued connection 切换到主线程执行 slot。
"""

from PySide6.QtCore import QObject, Signal
from core.events import EventBus, EVENT_STATUS_CHANGED, EVENT_LOG_LINE, EVENT_STATS_UPDATE


class AppBridge(QObject):
    """把 EventBus 事件桥接到 Qt Signal"""

    status_changed = Signal(str)   # ProcessStatus.value
    log_line = Signal(str)
    stats_update = Signal(dict)

    def __init__(self, bus: EventBus):
        super().__init__()
        # EventBus.emit(event, **data) → handler 收到关键字参数
        bus.on(EVENT_STATUS_CHANGED, lambda status, **kw: self.status_changed.emit(status))
        bus.on(EVENT_LOG_LINE, lambda line: self.log_line.emit(line))
        bus.on(EVENT_STATS_UPDATE, lambda **d: self.stats_update.emit(d))
