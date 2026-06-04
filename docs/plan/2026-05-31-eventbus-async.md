# EventBus 异步化改进计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 EventBus 从同步阻塞改造为异步安全的消息中枢，解决跨线程调用风险、链式断裂和错误静默丢失问题。

**Architecture:** 引入 `queue.Queue` 作为事件缓冲，单个 dispatch 线程从队列消费事件并同步调用所有 subscriber。任何 subscriber 的异常不会中断其他 subscriber，也不会在后台线程直接操作 UI。所有跨线程通知通过 Qt Signal 的 queued connection 自动切换到主线程执行。

**Tech Stack:** Python 标准库 `queue.Queue` / `threading` / `weakref`，现有 PySide6 Signal 无需改变。

---

## 文件结构

```
core/
  events.py              # 重写为异步事件总线
  events_old.py         # 备份原实现（供回滚）

tests/
  core/
    test_events.py      # 新增 EventBus 单元测试
```

**现有文件修改（仅接口兼容，无破坏性变更）：**
- `ui/bridge.py` — 无需修改（接口不变）
- `ui/widgets/chat_panel.py` — 无需修改
- `ui/widgets/monitor_panel.py` — 无需修改
- `core/process_manager.py` — 无需修改
- `core/hf_downloader.py` — 无需修改

---

## Task 1: 备份原实现

**Files:**
- Read: `core/events.py`（已读入上下文）
- Backup: `core/events_old.py`

- [ ] **Step 1: 创建备份文件**

```python
# core/events_old.py
"""原始 EventBus 实现 — 备份供回滚"""
# 完整复制当前 events.py 内容
```

---

## Task 2: 编写 EventBus 单元测试

**Files:**
- Create: `tests/core/test_events.py`

- [ ] **Step 1: 写测试 — 基础订阅/发布**

```python
import pytest
from core.events import EventBus

def test_basic_subscribe_and_emit():
    bus = EventBus()
    results = []

    def handler(value, **kw):
        results.append(value)

    bus.on("test_event", handler)
    bus.emit("test_event", value=42)
    assert results == [42]
```

- [ ] **Step 2: 写测试 — 多个 subscriber 均被调用（原有行为回归）**

```python
def test_multiple_subscribers_all_called():
    bus = EventBus()
    a_results, b_results = [], []

    bus.on("e", lambda **kw: a_results.append(1))
    bus.on("e", lambda **kw: b_results.append(1))
    bus.emit("e")
    assert a_results == [1]
    assert b_results == [1]
```

- [ ] **Step 3: 写测试 — subscriber 异常不阻断其他 subscriber**

```python
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
    assert results == [1]
```

- [ ] **Step 4: 写测试 — emit 在后台线程触发，subscriber 在主线程执行**

```python
def test_cross_thread_emit():
    import threading
    bus = EventBus()
    results = []

    def handler(value, **kw):
        results.append(value)

    bus.on("cross", handler)
    t = threading.Thread(target=lambda: bus.emit("cross", value="from_bg"))
    t.start()
    t.join(timeout=2)
    assert "from_bg" in results
```

- [ ] **Step 5: 写测试 — off 正确移除 subscriber**

```python
def test_unsubscribe():
    bus = EventBus()
    results = []

    def h(**kw): results.append(1)
    bus.on("e", h)
    bus.off("e", h)
    bus.emit("e")
    assert results == []
```

- [ ] **Step 6: 验证测试失败（EventBus 尚未重写）**

```bash
pytest tests/core/test_events.py -v
```
Expected: FAIL — 多个测试用例不通过（因为现有实现是同步的，异常会阻断）

---

## Task 3: 重写 EventBus

**Files:**
- Modify: `core/events.py`

- [ ] **Step 1: 写异步 EventBus 实现**

```python
# core/events.py
"""异步事件总线：将事件放入队列，由单一 dispatch 线程消费并同步调用 subscriber"""

import logging
import threading
import weakref
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
        self._dispatch_thread_weakref: weakref.ref | None = None

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

    def emit(self, event: str, **data) -> None:
        """将事件放入队列，立即返回（不阻塞当前线程）"""
        self._ensure_dispatch_started()
        self._queue.put((event, data))

    def _ensure_dispatch_started(self) -> None:
        """启动 dispatch 线程（惰性启动，单例模式）"""
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
```

- [ ] **Step 2: 运行测试验证实现**

```bash
pytest tests/core/test_events.py -v
```
Expected: ALL PASS

- [ ] **Step 3: 提交**

```bash
git add core/events.py core/events_old.py tests/core/test_events.py
git commit -m "feat(events): 异步化 EventBus，解决跨线程调用和链式断裂问题"
```

---

## Task 4: 验证现有功能完整性

**Files:**
- Modify: 无（仅运行验证）

- [ ] **Step 1: 运行全部单元测试**

```bash
pytest tests/ -v
```
Expected: 全部 PASS（35+ 测试）

- [ ] **Step 2: 手动启动应用验证 UI**

```bash
python main.py
```
验证：状态变化/日志输出/监控更新均正常

- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "test: 验证 EventBus 异步化后全部测试通过"
```

---

## Task 5: 删除备份文件

**Files:**
- Delete: `core/events_old.py`

- [ ] **Step 1: 确认新实现稳定后删除备份**

```bash
rm core/events_old.py
git add -A
git commit -m "chore: 删除 EventBus 回滚备份"
```

---

## 验证清单

| 检查项 | 状态 |
|--------|------|
| 所有 subscriber 回调均被调用（不因异常中断） | ☐ |
| 后台线程 emit 不阻塞，不直接操作 UI | ☐ |
| 现有代码无需修改（接口兼容） | ☐ |
| 全部 pytest 测试通过 | ☐ |
| 手动启动应用功能正常 | ☐ |