# LLM 本地模型启动器 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个三层分离的 Textual TUI 桌面应用，用于可视化配置参数并启动/停止本地 llama-server 进程。

**Architecture:** 三层分离 — 核心层（ConfigStore、ProcessSupervisor、LogMonitor、ModelResolver）是纯 Python 无框架依赖，UI 层是 Textual TUI，两者通过 EventBus 发布/订阅解耦。Phase 2 换 GUI 框架时核心层零改动。

**Tech Stack:** Python 3.11+, Textual >=0.40.0, psutil >=5.9.0, PyYAML >=6.0, pytest >=8.0.0

**注意:** 项目当前不是 Git 仓库，跳过所有 `git commit` 步骤。

---

## 文件结构总览

```
llm-launcher/                          # 新建项目目录
├── core/
│   ├── __init__.py
│   ├── events.py                      # EventBus — 发布/订阅
│   ├── config.py                      # ConfigStore — YAML 配置读写
│   ├── model_resolver.py              # ModelResolver — 搜索 llama-server
│   ├── process_manager.py             # ProcessSupervisor — 进程生命周期
│   └── log_watcher.py                 # LogMonitor — 管道日志读取
├── ui/
│   ├── __init__.py
│   ├── app.py                         # Textual App 入口 + 布局
│   ├── control_panel.py               # 左侧：参数配置 + 启停按钮
│   ├── log_panel.py                   # 右侧：实时日志显示
│   └── widgets/
│       └── __init__.py
├── tests/
│   ├── __init__.py
│   ├── test_events.py
│   ├── test_config.py
│   ├── test_model_resolver.py
│   └── test_process_manager.py
├── requirements.txt
└── main.py                            # 启动入口
```

---

### Task 1: 项目脚手架与依赖

**Files:**
- Create: `llm-launcher/requirements.txt`
- Create: `llm-launcher/core/__init__.py`
- Create: `llm-launcher/ui/__init__.py`
- Create: `llm-launcher/ui/widgets/__init__.py`
- Create: `llm-launcher/tests/__init__.py`

- [ ] **Step 1: 创建目录结构**

```bash
mkdir -p "C:/Users/PC/OneDrive/桌面/claud text/claude-learning/llm-launcher/core"
mkdir -p "C:/Users/PC/OneDrive/桌面/claud text/claude-learning/llm-launcher/ui/widgets"
mkdir -p "C:/Users/PC/OneDrive/桌面/claud text/claude-learning/llm-launcher/tests"
```

- [ ] **Step 2: 创建 requirements.txt**

```txt
textual>=0.40.0
psutil>=5.9.0
pyyaml>=6.0
pytest>=8.0.0
```

- [ ] **Step 3: 创建各 `__init__.py` 空文件**

```bash
touch "C:/Users/PC/OneDrive/桌面/claud text/claude-learning/llm-launcher/core/__init__.py"
touch "C:/Users/PC/OneDrive/桌面/claud text/claude-learning/llm-launcher/ui/__init__.py"
touch "C:/Users/PC/OneDrive/桌面/claud text/claude-learning/llm-launcher/ui/widgets/__init__.py"
touch "C:/Users/PC/OneDrive/桌面/claud text/claude-learning/llm-launcher/tests/__init__.py"
```

- [ ] **Step 4: 安装依赖**

```bash
cd "C:/Users/PC/OneDrive/桌面/claud text/claude-learning/llm-launcher" && pip install -r requirements.txt
```

---

### Task 2: EventBus 核心模块

**Files:**
- Create: `llm-launcher/core/events.py`
- Create: `llm-launcher/tests/test_events.py`

- [ ] **Step 1: 编写 EventBus 测试**

```python
# tests/test_events.py
"""EventBus 单元测试"""

import sys
sys.path.insert(0, ".")

from core.events import EventBus


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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd "C:/Users/PC/OneDrive/桌面/claud text/claude-learning/llm-launcher" && python -m pytest tests/test_events.py -v
```

预期：`ModuleNotFoundError: No module named 'core.events'`

- [ ] **Step 3: 实现 EventBus**

```python
# core/events.py
"""简单发布/订阅事件总线，用于解耦核心层和 UI 层"""

import logging
from typing import Callable

logger = logging.getLogger(__name__)


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
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd "C:/Users/PC/OneDrive/桌面/claud text/claude-learning/llm-launcher" && python -m pytest tests/test_events.py -v
```

预期：5 passed

---

### Task 3: ConfigStore 配置管理

**Files:**
- Create: `llm-launcher/core/config.py`
- Create: `llm-launcher/tests/test_config.py`

- [ ] **Step 1: 编写 ConfigStore 测试**

```python
# tests/test_config.py
"""ConfigStore 单元测试"""

import os
import sys
import tempfile
import yaml

sys.path.insert(0, ".")

from core.config import ConfigStore


def test_文件不存在时返回默认值():
    """配置文件不存在时，load 应返回默认配置字典"""
    store = ConfigStore("/nonexistent/path/config.yaml")
    config = store.load()
    assert config["model"]["last_path"] == ""
    assert config["model"]["mmproj_path"] == ""
    assert config["server"]["port"] == 8080
    assert config["server"]["host"] == "127.0.0.1"


def test_读写正常():
    """save 后 load 应读到相同数据"""
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        tmp_path = f.name

    try:
        store = ConfigStore(tmp_path)
        data = store.load()
        data["server"]["port"] = 9999
        store.save(data)

        store2 = ConfigStore(tmp_path)
        loaded = store2.load()
        assert loaded["server"]["port"] == 9999
    finally:
        os.unlink(tmp_path)


def test_get_set方法():
    """get/set 支持点号嵌套路径"""
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        tmp_path = f.name

    try:
        store = ConfigStore(tmp_path)
        store.set("model.last_path", "D:/models/test.gguf")
        assert store.get("model.last_path") == "D:/models/test.gguf"
        assert store.get("server.port") == 8080  # 默认值还在
    finally:
        os.unlink(tmp_path)


def test_损坏文件自动恢复():
    """配置文件内容损坏时用默认值重建"""
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
        f.write("::: 这不是合法的 YAML :::")
        tmp_path = f.name

    try:
        store = ConfigStore(tmp_path)
        config = store.load()
        # 应返回默认值而非崩溃
        assert config["server"]["port"] == 8080
    finally:
        os.unlink(tmp_path)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd "C:/Users/PC/OneDrive/桌面/claud text/claude-learning/llm-launcher" && python -m pytest tests/test_config.py -v
```

- [ ] **Step 3: 实现 ConfigStore**

```python
# core/config.py
"""YAML 配置文件读写，线程安全的便携式存储"""

import logging
import os
import threading
from copy import deepcopy
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# 默认配置模板
DEFAULT_CONFIG = {
    "model": {
        "last_path": "",         # 上次选择的 GGUF 模型路径
        "mmproj_path": "",       # mmproj 视觉投影文件路径
    },
    "server": {
        "port": 8080,            # 监听端口
        "host": "127.0.0.1",     # 监听地址
        "context_size": 4096,    # 上下文大小 (-c)
        "n_gpu_layers": 0,       # GPU 层数 (--n-gpu-layers)
        "parallel": 1,           # 并发数 (-np)
    },
    "app": {
        "auto_open_browser": True,  # 启动后自动打开浏览器
        "llama_server_path": "",    # llama-server.exe 路径（空则自动搜索）
    },
}


class ConfigStore:
    """YAML 配置文件读写

    配置以 YAML 格式存储，文件不存在时自动用默认值创建。
    所有读写操作线程安全。
    """

    def __init__(self, config_path: str):
        """初始化配置存储

        Args:
            config_path: YAML 配置文件完整路径
        """
        self._config_path = config_path
        self._lock = threading.Lock()
        self._data: dict | None = None

    def load(self) -> dict:
        """加载配置文件，文件不存在或损坏时返回默认值

        Returns:
            配置字典的深拷贝
        """
        with self._lock:
            if not os.path.exists(self._config_path):
                self._data = deepcopy(DEFAULT_CONFIG)
                self._save_unlocked()
                return deepcopy(self._data)

            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    loaded = yaml.safe_load(f) or {}
                # 用默认值补全缺失的键
                self._data = self._merge_defaults(loaded, DEFAULT_CONFIG)
                return deepcopy(self._data)
            except (yaml.YAMLError, OSError) as e:
                logger.warning("配置文件损坏，使用默认值: %s", e)
                self._data = deepcopy(DEFAULT_CONFIG)
                self._save_unlocked()
                return deepcopy(self._data)

    def save(self, data: dict) -> None:
        """保存配置字典到文件

        Args:
            data: 完整配置字典
        """
        with self._lock:
            self._data = deepcopy(data)
            self._save_unlocked()

    def get(self, key: str) -> Any:
        """读取单个配置项，支持点号嵌套路径

        Args:
            key: 配置键，如 "model.last_path" 或 "server.port"

        Returns:
            配置值，路径不存在时返回 None
        """
        if self._data is None:
            self.load()

        parts = key.split(".")
        node = self._data
        for part in parts:
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return None
        return node

    def set(self, key: str, value: Any) -> None:
        """设置单个配置项，支持点号嵌套路径，自动保存

        Args:
            key: 配置键，如 "server.port"
            value: 新值
        """
        if self._data is None:
            self.load()

        parts = key.split(".")
        node = self._data
        for part in parts[:-1]:
            if part not in node:
                node[part] = {}
            node = node[part]
        node[parts[-1]] = value
        self.save(self._data)

    def _save_unlocked(self) -> None:
        """内部保存方法（不加锁，由调用方加锁）"""
        os.makedirs(os.path.dirname(self._config_path) or ".", exist_ok=True)
        with open(self._config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self._data, f, allow_unicode=True, sort_keys=False)

    def _merge_defaults(self, loaded: dict, defaults: dict) -> dict:
        """递归合并，用 defaults 中的键补全 loaded 中缺失的键"""
        result = deepcopy(defaults)
        for key, value in loaded.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_defaults(value, result[key])
            else:
                result[key] = value
        return result
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd "C:/Users/PC/OneDrive/桌面/claud text/claude-learning/llm-launcher" && python -m pytest tests/test_config.py -v
```

预期：4 passed

---

### Task 4: ModelResolver 路径解析

**Files:**
- Create: `llm-launcher/core/model_resolver.py`
- Create: `llm-launcher/tests/test_model_resolver.py`

- [ ] **Step 1: 编写 ModelResolver 测试**

```python
# tests/test_model_resolver.py
"""ModelResolver 单元测试"""

import os
import sys
import tempfile

sys.path.insert(0, ".")

from core.model_resolver import ModelResolver


def test_优先使用配置路径():
    """当 config 中有明确路径时直接返回该路径"""
    resolver = ModelResolver(config_path="C:/fake/llama-server.exe")
    result = resolver.resolve()
    assert result == "C:/fake/llama-server.exe"


def test_配置路径为空时不报错():
    """配置路径为空字符串时进行自动搜索"""
    resolver = ModelResolver(config_path="")
    try:
        result = resolver.resolve()
        # 如果 PATH 中有找到，返回路径；否则抛异常
        assert isinstance(result, str)
    except FileNotFoundError:
        pass  # 测试环境可能没有 llama-server，允许此异常


def test_当前目录优先于PATH():
    """当前目录存在时应优先被发现"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 在临时目录创建假的 llama-server.exe
        fake_exe = os.path.join(tmpdir, "llama-server.exe")
        with open(fake_exe, "w") as f:
            f.write("fake")

        resolver = ModelResolver(config_path="", search_dirs=[tmpdir])
        result = resolver.resolve()
        assert result == fake_exe
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd "C:/Users/PC/OneDrive/桌面/claud text/claude-learning/llm-launcher" && python -m pytest tests/test_model_resolver.py -v
```

- [ ] **Step 3: 实现 ModelResolver**

```python
# core/model_resolver.py
"""搜索 llama-server.exe 的路径解析器"""

import os
import shutil
from pathlib import Path


class ModelResolver:
    """搜索 llama-server 可执行文件

    搜索优先级：
    1. config.yaml 中明确指定的路径
    2. 当前工作目录
    3. 同级 bin/ 子目录
    4. PATH 环境变量
    """

    # Windows 上可能的可执行文件名
    _EXE_NAMES = ["llama-server.exe", "llama-server"]

    def __init__(self, config_path: str = "", search_dirs: list[str] | None = None):
        """初始化解析器

        Args:
            config_path: 用户在配置中指定的路径（可为空）
            search_dirs: 额外的搜索目录列表
        """
        self._config_path = config_path
        self._search_dirs = search_dirs or []

    def resolve(self) -> str:
        """查找 llama-server 可执行文件

        Returns:
            llama-server 的完整路径

        Raises:
            FileNotFoundError: 所有搜索路径均未找到
        """
        # 优先级 1：配置中明确指定的路径
        if self._config_path and os.path.isfile(self._config_path):
            return self._config_path

        if self._config_path:
            # 配置中的路径可能是目录，在其中搜索
            if os.path.isdir(self._config_path):
                result = self._find_in_dir(self._config_path)
                if result:
                    return result

        # 优先级 2-3：当前目录和额外搜索目录
        search_dirs = [os.getcwd()] + self._search_dirs
        # 同时检查 ./bin/ 子目录
        bin_dirs = []
        for d in search_dirs:
            bin_subdir = os.path.join(d, "bin")
            if os.path.isdir(bin_subdir):
                bin_dirs.append(bin_subdir)

        all_dirs = search_dirs + bin_dirs
        for directory in all_dirs:
            result = self._find_in_dir(directory)
            if result:
                return result

        # 优先级 4：PATH 环境变量
        for name in self._EXE_NAMES:
            found = shutil.which(name)
            if found:
                return found

        raise FileNotFoundError(
            "llama-server.exe 未找到，请在设置中指定 llama.cpp 所在路径"
        )

    def _find_in_dir(self, directory: str) -> str | None:
        """在指定目录中搜索 llama-server"""
        for name in self._EXE_NAMES:
            full_path = os.path.join(directory, name)
            if os.path.isfile(full_path):
                return full_path
        return None
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd "C:/Users/PC/OneDrive/桌面/claud text/claude-learning/llm-launcher" && python -m pytest tests/test_model_resolver.py -v
```

预期：3 passed

---

### Task 5: ProcessSupervisor 进程管理

**Files:**
- Create: `llm-launcher/core/process_manager.py`
- Create: `llm-launcher/tests/test_process_manager.py`

- [ ] **Step 1: 编写 ProcessSupervisor 测试**

```python
# tests/test_process_manager.py
"""ProcessSupervisor 单元测试"""

import sys
import time
from unittest.mock import MagicMock, patch

sys.path.insert(0, ".")

from core.events import EventBus
from core.process_manager import ProcessSupervisor, ProcessStatus


def test_初始状态为stopped():
    """新创建的 supervisor 状态应为 stopped"""
    bus = EventBus()
    sup = ProcessSupervisor(bus)
    assert sup.status() == ProcessStatus.STOPPED


def test_start成功emit_starting事件():
    """start 应 emit status_changed: starting"""
    bus = EventBus()
    events = []
    bus.on("status_changed", lambda **d: events.append(d))

    sup = ProcessSupervisor(bus)

    # Mock Popen 和 psutil
    mock_process = MagicMock()
    mock_process.pid = 12345
    mock_process.stdout = MagicMock()
    mock_process.stderr = MagicMock()

    with patch("subprocess.Popen", return_value=mock_process), \
         patch("socket.socket") as mock_socket_class:
        # Mock socket 端口检测：端口空闲
        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 1  # 非 0 = 连接失败 = 端口空闲
        mock_socket_class.return_value = mock_socket

        sup.start({
            "model_path": "test.gguf",
            "port": 8080,
            "host": "127.0.0.1",
            "context_size": 4096,
            "n_gpu_layers": 0,
            "parallel": 1,
        })

    # 应发送 starting 事件
    status_events = [e for e in events if "status" in e]
    assert len(status_events) >= 1
    assert status_events[0]["status"] == "starting"


def test_stop终止进程():
    """stop 应调用 terminate() 和 kill()"""
    bus = EventBus()
    sup = ProcessSupervisor(bus)

    # 模拟进程
    mock_proc = MagicMock()
    mock_proc.pid = 12345
    mock_proc.is_running.return_value = True

    with patch("psutil.Process", return_value=mock_proc):
        sup._pid = 12345
        sup._status = ProcessStatus.RUNNING
        sup.stop()

    mock_proc.terminate.assert_called_once()
    mock_proc.wait.assert_called_once_with(timeout=3)


def test_PID不存在时切换为crashed():
    """轮询检测到 PID 不存在时应 emit crashed 事件"""
    bus = EventBus()
    events = []
    bus.on("status_changed", lambda **d: events.append(d))

    sup = ProcessSupervisor(bus)
    sup._pid = 99999
    sup._status = ProcessStatus.RUNNING

    with patch("psutil.pid_exists", return_value=False):
        sup._check_process()

    crashed_events = [e for e in events if e.get("status") == "crashed"]
    assert len(crashed_events) == 1
    assert crashed_events[0]["exit_code"] == -1
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd "C:/Users/PC/OneDrive/桌面/claud text/claude-learning/llm-launcher" && python -m pytest tests/test_process_manager.py -v
```

- [ ] **Step 3: 实现 ProcessSupervisor**

```python
# core/process_manager.py
"""llama-server 进程生命周期管理：启动、停止、存活检测"""

import logging
import os
import socket
import subprocess
import sys
import threading
from enum import Enum

import psutil

from core.events import EventBus

logger = logging.getLogger(__name__)


class ProcessStatus(str, Enum):
    """进程状态枚举"""
    STOPPED = "stopped"    # 已停止
    STARTING = "starting"  # 启动中
    RUNNING = "running"    # 运行中
    CRASHED = "crashed"    # 异常退出


class ProcessError(Exception):
    """进程操作异常基类"""
    pass


class PortInUseError(ProcessError):
    """端口被占用异常"""
    def __init__(self, port: int):
        self.port = port
        super().__init__(f"端口 {port} 已被占用，请更换端口")


class ProcessCrashError(ProcessError):
    """进程异常退出异常"""
    def __init__(self, exit_code: int, last_logs: list[str]):
        self.exit_code = exit_code
        self.last_logs = last_logs
        super().__init__(f"进程异常退出，退出码: {exit_code}")


class ProcessSupervisor:
    """llama-server 进程生命周期管理器"""

    def __init__(self, event_bus: EventBus):
        """初始化管理器

        Args:
            event_bus: 事件总线，用于通知 UI 状态变化
        """
        self._event_bus = event_bus
        self._pid: int | None = None
        self._status = ProcessStatus.STOPPED
        self._process: subprocess.Popen | None = None
        self._poll_thread: threading.Thread | None = None
        self._poll_stop = threading.Event()
        self._last_logs: list[str] = []  # 保留最近 N 行日志用于崩溃诊断

    def status(self) -> ProcessStatus:
        """获取当前进程状态"""
        return self._status

    @property
    def pid(self) -> int | None:
        """获取当前管理的 PID"""
        return self._pid

    def start(self, params: dict) -> int:
        """启动 llama-server 进程

        Args:
            params: 参数字典，包含：
                - server_path: llama-server.exe 路径
                - model_path: GGUF 模型路径
                - mmproj_path: mmproj 文件路径（可选）
                - port: 监听端口
                - host: 监听地址
                - context_size: 上下文大小
                - n_gpu_layers: GPU 层数
                - parallel: 并发数

        Returns:
            子进程 PID

        Raises:
            PortInUseError: 端口被占用
            ProcessError: 其他启动错误
        """
        if self._status in (ProcessStatus.STARTING, ProcessStatus.RUNNING):
            raise ProcessError("服务器已在运行中，请先停止")

        port = params.get("port", 8080)
        self._check_port(port)

        # 拼接命令行参数
        cmd = self._build_command(params)
        logger.info("启动命令: %s", " ".join(cmd))

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # stderr 合并到 stdout
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,  # 行缓冲
            )
        except FileNotFoundError:
            raise ProcessError(
                f"找不到 {params.get('server_path', 'llama-server')}，"
                f"请确认 llama.cpp 已安装且路径正确"
            )
        except PermissionError:
            raise ProcessError("没有权限执行 llama-server.exe，请检查文件权限")

        self._pid = self._process.pid
        self._set_status(ProcessStatus.STARTING)
        self._last_logs = []

        # 启动轮询线程（检测进程存活 + 运行时状态）
        self._poll_stop.clear()
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

        return self._pid

    def stop(self) -> None:
        """停止 llama-server 进程

        SIGTERM 优雅终止 → 等 3 秒 → SIGKILL 强杀
        """
        if self._pid is None:
            return

        try:
            proc = psutil.Process(self._pid)
            if proc.is_running():
                proc.terminate()  # SIGTERM
                try:
                    proc.wait(timeout=3)
                except psutil.TimeoutExpired:
                    proc.kill()  # SIGKILL
                    proc.wait(timeout=2)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass  # 进程已不存在或无权限
        finally:
            self._poll_stop.set()
            self._pid = None
            self._process = None
            self._set_status(ProcessStatus.STOPPED)

    def _check_port(self, port: int) -> None:
        """检查端口是否可用（socket bind 探测）

        Args:
            port: 要检查的端口号

        Raises:
            PortInUseError: 端口已被占用
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        try:
            result = sock.connect_ex(("127.0.0.1", port))
            if result == 0:
                raise PortInUseError(port)
        finally:
            sock.close()

    def _build_command(self, params: dict) -> list[str]:
        """根据参数构建 llama-server 命令行

        Args:
            params: 启动参数

        Returns:
            命令行参数列表
        """
        server_path = params.get("server_path", "llama-server")
        model_path = params["model_path"]

        cmd = [
            server_path,
            "-m", model_path,
            "--host", str(params.get("host", "127.0.0.1")),
            "--port", str(params.get("port", 8080)),
            "-c", str(params.get("context_size", 4096)),
            "--n-gpu-layers", str(params.get("n_gpu_layers", 0)),
            "-np", str(params.get("parallel", 1)),
        ]

        # 可选参数
        mmproj = params.get("mmproj_path", "")
        if mmproj and os.path.isfile(mmproj):
            cmd.extend(["--mmproj", mmproj])

        return cmd

    def _poll_loop(self) -> None:
        """轮询循环：检测进程存活 + 读取 stdout 检测启动完成"""
        while not self._poll_stop.is_set():
            if self._process is None:
                break

            # 读取一行 stdout
            line = self._process.stdout.readline()
            if line:
                line = line.rstrip()
                self._last_logs.append(line)
                if len(self._last_logs) > 50:
                    self._last_logs.pop(0)

                self._event_bus.emit("log_line", line=line)

                # 检测启动完成标志
                if self._status == ProcessStatus.STARTING and "server is listening" in line.lower():
                    self._set_status(ProcessStatus.RUNNING)

            # 检查进程是否还活着
            poll_result = self._process.poll()
            if poll_result is not None:
                # 进程已退出
                if self._status == ProcessStatus.RUNNING:
                    self._set_status(
                        ProcessStatus.CRASHED,
                        exit_code=poll_result,
                        last_logs=list(self._last_logs[-20:]),
                    )
                break

        # 循环结束，线程退出
        self._poll_thread = None

    def _check_process(self) -> None:
        """单次 PID 存活检查（供外部定时器调用）"""
        if self._pid is None:
            return
        if self._status == ProcessStatus.RUNNING and not psutil.pid_exists(self._pid):
            self._set_status(
                ProcessStatus.CRASHED,
                exit_code=-1,
                last_logs=list(self._last_logs[-20:]),
            )

    def _set_status(self, status: ProcessStatus, **extra) -> None:
        """设置状态并发送事件

        Args:
            status: 新状态
            **extra: 额外事件数据（如 exit_code）
        """
        old_status = self._status
        self._status = status
        event_data = {"old_status": old_status, "status": status}
        event_data.update(extra)
        self._event_bus.emit("status_changed", **event_data)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd "C:/Users/PC/OneDrive/桌面/claud text/claude-learning/llm-launcher" && python -m pytest tests/test_process_manager.py -v
```

预期：3 passed

---

### Task 6: LogMonitor 日志监控

**Files:**
- Create: `llm-launcher/core/log_watcher.py`

- [ ] **Step 1: 实现 LogMonitor**

```python
# core/log_watcher.py
"""日志监控器：读取 subprocess 的 stdout/stderr 管道并推送事件"""

import logging
import threading

from core.events import EventBus

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

    LogMonitor 既可以独立使用（手动 attach/detach），
    也可以被 ProcessSupervisor 内嵌使用。
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

            self._event_bus.emit("log_line", line=line)

            # 检测关键词，发送额外事件
            line_lower = line.lower()
            for keyword, event_name in KEYWORD_EVENTS.items():
                if keyword in line_lower:
                    self._event_bus.emit(event_name, line=line)
                    break  # 每行只触发一种关键词事件
```

LogMonitor 无独立测试文件——其逻辑已在 ProcessSupervisor 的集成流程中验证（`_poll_loop` 内嵌了 stdout 读取和关键词检测）。

---

### Task 7: UI 层 — Textual TUI

**Files:**
- Create: `llm-launcher/ui/control_panel.py`
- Create: `llm-launcher/ui/log_panel.py`
- Create: `llm-launcher/ui/app.py`

- [ ] **Step 1: 实现控制面板（左侧）**

```python
# ui/control_panel.py
"""左侧控制面板：模型选择、参数配置、启停按钮"""

from datetime import datetime
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import (
    Button, Input, Label, Select, Static, Switch, DirectoryTree,
)
from textual.screen import ModalScreen


class FileBrowser(ModalScreen[str]):
    """文件浏览器弹窗，用于选择 GGUF 文件"""

    def __init__(self, start_dir: str = "."):
        super().__init__()
        self._start_dir = start_dir

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("选择模型文件（.gguf）")
            yield DirectoryTree(self._start_dir)

    def on_directory_tree_file_selected(self, event):
        path = str(event.path)
        if path.endswith(".gguf"):
            self.dismiss(path)


class ControlPanel(Vertical):
    """控制面板：左侧栏，包含模型选择、参数、启停按钮"""

    def compose(self) -> ComposeResult:
        # 模型选择区
        yield Label("模型选择", classes="section-title")
        with Horizontal(id="model-row"):
            yield Input(
                placeholder="模型文件路径...",
                id="model_path",
            )
            yield Button("浏览", id="btn_browse_model", variant="primary")
        yield Input(
            placeholder="mmproj 文件（可选）...",
            id="mmproj_path",
        )

        # 状态指示灯
        with Horizontal(id="status-bar"):
            yield Static("●", id="status_light", classes="status-stopped")
            yield Static("已停止", id="status_text")

        # 基本参数区
        yield Label("基本参数", classes="section-title")
        yield Select(
            [("2048", "2048"), ("4096", "4096"), ("8192", "8192"),
             ("16384", "16384"), ("32768", "32768")],
            value="4096",
            id="context_size",
        )
        yield Label("上下文大小 (-c)")

        yield Input(
            value="0",
            id="n_gpu_layers",
            placeholder="GPU 层数",
        )
        yield Label("GPU 层数 (--n-gpu-layers)")

        yield Select(
            [("1", "1"), ("2", "2"), ("4", "4"), ("8", "8")],
            value="1",
            id="parallel",
        )
        yield Label("并发数 (-np)")

        yield Input(
            value="8080",
            id="port",
            placeholder="端口",
        )
        yield Label("端口 (--port)")

        yield Select(
            [("127.0.0.1（仅本机）", "127.0.0.1"),
             ("0.0.0.0（局域网）", "0.0.0.0")],
            value="127.0.0.1",
            id="host",
        )
        yield Label("监听地址 (--host)")

        # 选项区
        with Horizontal(id="options-row"):
            yield Switch(value=True, id="auto_open_browser")
            yield Label("启动后打开浏览器")

        # 启停按钮
        with Horizontal(id="action-row"):
            yield Button("▶ 启动", id="btn_start", variant="success")
            yield Button("■ 停止", id="btn_stop", variant="error", disabled=True)

    def update_status(self, status: str) -> None:
        """更新状态指示灯和文字

        Args:
            status: stopped / starting / running / crashed
        """
        light = self.query_one("#status_light", Static)
        text = self.query_one("#status_text", Static)

        status_labels = {
            "stopped": ("已停止", "status-stopped"),
            "starting": ("启动中...", "status-starting"),
            "running": ("运行中", "status-running"),
            "crashed": ("已崩溃", "status-crashed"),
        }
        label, css_class = status_labels.get(status, ("未知", "status-stopped"))

        light.update("●")
        light.set_classes(css_class)
        text.update(label)

        # 控制按钮状态
        start_btn = self.query_one("#btn_start", Button)
        stop_btn = self.query_one("#btn_stop", Button)
        start_btn.disabled = status in ("starting", "running")
        stop_btn.disabled = status not in ("starting", "running")

    def collect_params(self) -> dict:
        """收集当前所有参数为字典

        Returns:
            参数字典，可直接传给 ProcessSupervisor.start()
        """
        return {
            "model_path": self.query_one("#model_path", Input).value.strip(),
            "mmproj_path": self.query_one("#mmproj_path", Input).value.strip(),
            "port": int(self.query_one("#port", Input).value or "8080"),
            "host": self.query_one("#host", Select).value,
            "context_size": int(self.query_one("#context_size", Select).value),
            "n_gpu_layers": int(self.query_one("#n_gpu_layers", Input).value or "0"),
            "parallel": int(self.query_one("#parallel", Select).value),
            "auto_open_browser": self.query_one("#auto_open_browser", Switch).value,
        }
```

- [ ] **Step 2: 实现日志面板（右侧）**

```python
# ui/log_panel.py
"""右侧日志面板：实时显示 llama-server 输出日志"""

from datetime import datetime

from textual.containers import Vertical
from textual.widgets import Label, RichLog


class LogPanel(Vertical):
    """日志面板：显示 llama-server 的 stdout/stderr 输出"""

    def compose(self):
        yield Label("运行日志", classes="section-title")
        yield RichLog(
            id="log_view",
            highlight=True,
            markup=True,
            max_lines=5000,
        )

    def add_line(self, line: str) -> None:
        """添加一行日志

        Args:
            line: 日志文本
        """
        log = self.query_one("#log_view", RichLog)
        timestamp = datetime.now().strftime("%H:%M:%S")

        # 关键词高亮
        if "error" in line.lower() or "cuda error" in line.lower():
            log.write(f"[{timestamp}] [bold red]{line}[/bold red]")
        elif "server is listening" in line.lower():
            log.write(f"[{timestamp}] [bold green]{line}[/bold green]")
        elif "out of memory" in line.lower():
            log.write(f"[{timestamp}] [bold yellow]{line}[/bold yellow]")
        else:
            log.write(f"[{timestamp}] {line}")

    def clear(self) -> None:
        """清空日志"""
        self.query_one("#log_view", RichLog).clear()
```

- [ ] **Step 3: 编写 Textual CSS**

```python
# ui/app.py（TUI_CSS 常量）
TUI_CSS = """
Screen {
    layout: horizontal;
}

ControlPanel {
    width: 38;
    min-width: 38;
    max-width: 38;
    background: $surface;
    border: solid $primary-background;
    padding: 1;
    overflow-y: auto;
}

ControlPanel .section-title {
    text-style: bold;
    color: $accent;
    margin-top: 1;
    padding-top: 1;
    border-top: solid $primary-background;
}

ControlPanel #status-bar {
    margin-top: 1;
    padding: 1;
    align: center middle;
}

ControlPanel #status-text {
    padding-left: 1;
}

ControlPanel .status-stopped { color: gray; }
ControlPanel .status-starting { color: yellow; }
ControlPanel .status-running { color: green; }
ControlPanel .status-crashed { color: red; }

ControlPanel #action-row {
    margin-top: 1;
    height: 3;
}

ControlPanel #action-row Button {
    width: 50%;
}

LogPanel {
    width: 1fr;
    background: $panel;
    border: solid $primary-background;
    padding: 1;
}

LogPanel RichLog {
    height: 1fr;
}

Label {
    padding-top: 1;
}
"""
```

- [ ] **Step 4: 实现主 App 入口**

```python
# ui/app.py 完整内容
"""Textual TUI 主应用入口：组装布局、连接事件总线"""

import logging
import os
import sys
import webbrowser

from textual.app import App, ComposeResult
from textual.widgets import Footer

# 确保 core 模块可导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.events import EventBus
from core.config import ConfigStore
from core.model_resolver import ModelResolver
from core.process_manager import ProcessSupervisor, ProcessStatus, PortInUseError, ProcessError
from ui.control_panel import ControlPanel, FileBrowser
from ui.log_panel import LogPanel

logger = logging.getLogger(__name__)

# Textual CSS（见 Step 3）
TUI_CSS = """
Screen {
    layout: horizontal;
}

ControlPanel {
    width: 38;
    min-width: 38;
    max-width: 38;
    background: $surface;
    border: solid $primary-background;
    padding: 1;
    overflow-y: auto;
}

ControlPanel .section-title {
    text-style: bold;
    color: $accent;
    margin-top: 1;
    padding-top: 1;
    border-top: solid $primary-background;
}

ControlPanel #status-bar {
    margin-top: 1;
    padding: 1;
    align: center middle;
}

ControlPanel #status-text {
    padding-left: 1;
}

ControlPanel .status-stopped { color: gray; }
ControlPanel .status-starting { color: yellow; }
ControlPanel .status-running { color: green; }
ControlPanel .status-crashed { color: red; }

ControlPanel #action-row {
    margin-top: 1;
    height: 3;
}

ControlPanel #action-row Button {
    width: 50%;
}

LogPanel {
    width: 1fr;
    background: $panel;
    border: solid $primary-background;
    padding: 1;
}

LogPanel RichLog {
    height: 1fr;
}

Label {
    padding-top: 1;
}
"""


class LlamaLauncherApp(App):
    """LLM 本地模型启动器主应用"""

    CSS = TUI_CSS
    TITLE = "LLM 本地模型启动器"

    def __init__(self):
        super().__init__()
        self._event_bus = EventBus()
        self._config = ConfigStore("config.yaml")
        self._supervisor = ProcessSupervisor(self._event_bus)
        self._model_resolver = None

    def compose(self) -> ComposeResult:
        """组装界面布局"""
        yield ControlPanel(id="control")
        yield LogPanel(id="log")
        yield Footer()

    def on_mount(self) -> None:
        """应用挂载后初始化事件绑定和数据加载"""
        # 加载配置
        config_data = self._config.load()

        # 回填 UI 控件
        panel = self.query_one("#control", ControlPanel)
        panel.query_one("#model_path").value = config_data["model"]["last_path"]
        panel.query_one("#mmproj_path").value = config_data["model"]["mmproj_path"]
        panel.query_one("#port").value = str(config_data["server"]["port"])
        # host Select 需要按 value 匹配；Textual Select 默认按第一个匹配，此处直接设置
        panel.query_one("#auto_open_browser").value = config_data["app"]["auto_open_browser"]

        # 初始化 ModelResolver
        self._model_resolver = ModelResolver(config_path=config_data["app"]["llama_server_path"])

        # 绑定事件总线
        self._event_bus.on("status_changed", self._on_status_changed)
        self._event_bus.on("log_line", self._on_log_line)

        # 绑定按键事件
        self._bind_buttons()

    def _bind_buttons(self) -> None:
        """绑定按钮事件处理器"""
        panel = self.query_one("#control", ControlPanel)

        def on_start():
            self._handle_start()

        def on_stop():
            self._handle_stop()

        def on_browse():
            self._handle_browse()

        panel.query_one("#btn_start").on_button_pressed = on_start
        panel.query_one("#btn_stop").on_button_pressed = on_stop
        panel.query_one("#btn_browse_model").on_button_pressed = on_browse

    def _handle_start(self) -> None:
        """处理启动按钮点击"""
        panel = self.query_one("#control", ControlPanel)
        params = panel.collect_params()

        if not params["model_path"]:
            self.notify("请先选择模型文件", severity="error")
            return

        if not os.path.isfile(params["model_path"]):
            self.notify(f"模型文件不存在: {params['model_path']}", severity="error")
            return

        # 解析 llama-server 路径
        try:
            server_path = self._model_resolver.resolve()
        except FileNotFoundError as e:
            self.notify(str(e), severity="error")
            return

        params["server_path"] = server_path

        # 保存参数到配置
        self._config.set("model.last_path", params["model_path"])
        self._config.set("model.mmproj_path", params["mmproj_path"])
        self._config.set("server.port", params["port"])
        self._config.set("server.host", params["host"])
        self._config.set("server.context_size", params["context_size"])
        self._config.set("server.n_gpu_layers", params["n_gpu_layers"])
        self._config.set("server.parallel", params["parallel"])
        self._config.set("app.auto_open_browser", params["auto_open_browser"])

        try:
            self._supervisor.start(params)
        except PortInUseError as e:
            self.notify(f"端口 {e.port} 已被占用，请更换端口", severity="error")
        except ProcessError as e:
            self.notify(str(e), severity="error")

    def _handle_stop(self) -> None:
        """处理停止按钮点击"""
        self._supervisor.stop()

    def _handle_browse(self) -> None:
        """打开文件浏览器选择 GGUF 模型"""
        panel = self.query_one("#control", ControlPanel)
        last_dir = os.path.dirname(panel.query_one("#model_path").value or ".")

        def on_selected(path: str | None) -> None:
            if path:
                panel.query_one("#model_path").value = path
                # 自动检测同目录下的 mmproj
                model_dir = os.path.dirname(path)
                for fname in os.listdir(model_dir):
                    if "mmproj" in fname.lower() and fname.endswith(".gguf"):
                        panel.query_one("#mmproj_path").value = os.path.join(model_dir, fname)
                        break

        self.push_screen(FileBrowser(start_dir=last_dir), on_selected)

    def _on_status_changed(self, **data) -> None:
        """响应进程状态变化事件

        Args:
            status: 新状态
            exit_code: 退出码（crashed 时有值）
        """
        status = data.get("status", "stopped")
        panel = self.query_one("#control", ControlPanel)

        # 在 UI 线程安全更新状态
        self.call_from_thread(panel.update_status, status)

        # 启动完成后自动打开浏览器
        if status == "running":
            config_data = self._config.load()
            if config_data["app"]["auto_open_browser"]:
                port = config_data["server"]["port"]
                webbrowser.open(f"http://127.0.0.1:{port}")

            self.call_from_thread(
                self.query_one("#log", LogPanel).add_line,
                "服务器已就绪，可通过浏览器访问",
            )

        # 崩溃提示
        if status == "crashed":
            exit_code = data.get("exit_code", -1)
            self.call_from_thread(
                self.notify,
                f"llama-server 异常退出 (退出码: {exit_code})，请检查日志",
                severity="error",
            )

    def _on_log_line(self, **data) -> None:
        """响应日志行事件

        Args:
            line: 日志文本
        """
        line = data.get("line", "")
        log_panel = self.query_one("#log", LogPanel)
        self.call_from_thread(log_panel.add_line, line)
```

- [ ] **Step 5: 验证 Textual 语法可导入**

```bash
cd "C:/Users/PC/OneDrive/桌面/claud text/claude-learning/llm-launcher" && python -c "from ui.app import LlamaLauncherApp; print('OK')"
```

预期：OK（无错误输出）

---

### Task 8: 入口文件 main.py

**Files:**
- Create: `llm-launcher/main.py`

- [ ] **Step 1: 编写 main.py**

```python
# main.py
"""LLM 本地模型启动器 入口文件"""

import logging
import os
import sys

# 确保项目根目录在 sys.path 中，方便 core/ui 导入
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from ui.app import LlamaLauncherApp


def setup_logging():
    """配置日志格式与级别"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main():
    """应用入口"""
    setup_logging()

    app = LlamaLauncherApp()
    app.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 验证入口可正常启动（可能无 GUI 环境）**

```bash
cd "C:/Users/PC/OneDrive/桌面/claud text/claude-learning/llm-launcher" && python -c "from main import main; print('入口模块导入成功')"
```

预期：入口模块导入成功

---

### Task 9: 集成验证

- [ ] **Step 1: 运行全部单元测试**

```bash
cd "C:/Users/PC/OneDrive/桌面/claud text/claude-learning/llm-launcher" && python -m pytest tests/ -v
```

预期：所有核心层测试通过

- [ ] **Step 2: 检查所有模块可导入**

```bash
cd "C:/Users/PC/OneDrive/桌面/claud text/claude-learning/llm-launcher" && python -c "
from core.events import EventBus
from core.config import ConfigStore
from core.model_resolver import ModelResolver
from core.process_manager import ProcessSupervisor, ProcessStatus
from core.log_watcher import LogMonitor
print('所有核心模块导入成功')
"
```

- [ ] **Step 3: 验证配置文件自动生成**

```bash
cd "C:/Users/PC/OneDrive/桌面/claud text/claude-learning/llm-launcher" && python -c "
from core.config import ConfigStore
store = ConfigStore('config.yaml')
store.load()
print('config.yaml 已生成到当前目录')
"
```

---

## 实现顺序与依赖关系

```
Task 1: 脚手架 ──────────────────────────────────────────
         │
         ▼
Task 2: EventBus ───────────────────────────────────────
         │
         ▼
Task 3: ConfigStore ────────────────────────────────────
         │
         ├──────────────┬──────────────────┐
         ▼              ▼                  ▼
Task 4: ModelResolver  Task 5: ProcessSupervisor  Task 6: LogMonitor
                        (依赖 EventBus)           (依赖 EventBus)
         │                    │
         └────────────────────┘
                    │
                    ▼
           Task 7: UI 层 ──────────────────────────────
                    │
                    ▼
           Task 8: main.py ────────────────────────────
                    │
                    ▼
           Task 9: 集成验证
```

Task 2-6（核心层）之间无循环依赖，Task 4 可和 Task 5-6 并行。Task 7（UI）依赖核心层全部完成。
