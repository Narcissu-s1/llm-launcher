# Phase 2 高级参数与运行时监控 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 扩展 llama-server 参数支持至 26 个（6 个分组），并提供 GPU/内存/请求的实时监控。

**Architecture:** 模块化组件方案，每个参数分组为独立 Widget，监控为独立 Panel。配置扩展到 DEFAULT_CONFIG，命令构建按"非默认值才拼接"规则扩展。

**Tech Stack:** Python 3.10+, Textual (TUI), psutil, pyyaml, pytest

---

## 文件结构

```
ui/widgets/__init__.py          # 新建：包初始化
ui/widgets/param_groups.py      # 新建：6 个参数分组 Widget
ui/widgets/monitor_panel.py     # 新建：运行时监控 Panel
ui/control_panel.py             # 修改：组合参数分组 Widget
ui/app.py                       # 修改：接入 MonitorPanel
core/config.py                  # 修改：DEFAULT_CONFIG 扩展
core/process_manager.py         # 修改：_build_command 扩展
tests/test_config.py            # 修改：新增参数配置测试
tests/test_process_manager.py   # 修改：新增参数拼接测试
tests/test_param_groups.py      # 新建：参数 Widget 收集测试
tests/test_monitor.py           # 新建：监控逻辑测试
```

---

### Task 1: 扩展 DEFAULT_CONFIG

**Files:**
- Modify: `core/config.py:14-31`
- Test: `tests/test_config.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_config.py 末尾追加

def test_新增参数默认值():
    """Phase 2 新增参数应有正确的默认值"""
    from core.config import DEFAULT_CONFIG

    server = DEFAULT_CONFIG["server"]

    # KV Cache
    assert server["cache_type_k"] == "f16"
    assert server["cache_type_v"] == "f16"
    assert server["kv_unified"] is True
    assert server["no_kv_offload"] is False
    assert server["flash_attn"] is False
    assert server["cache_prompt"] is True
    assert server["cache_idle_slots"] is True

    # 推理速度
    assert server["threads"] == -1
    assert server["threads_batch"] == -1
    assert server["batch_size"] == 2048
    assert server["ubatch_size"] == 512
    assert server["threads_http"] == -1
    assert server["no_warmup"] is False

    # 采样参数
    assert server["temp"] == 0.80
    assert server["top_k"] == 40
    assert server["top_p"] == 0.95
    assert server["min_p"] == 0.05
    assert server["repeat_penalty"] == 1.0
    assert server["seed"] == -1
    assert server["n_predict"] == -1

    # 思考模式
    assert server["reasoning"] == "auto"
    assert server["reasoning_format"] == "auto"
    assert server["reasoning_budget"] == -1

    # 多模态
    assert server["mmproj_offload"] is True
    assert server["image_min_tokens"] == 0
    assert server["image_max_tokens"] == 0

    # 安全
    assert server["api_key"] == ""
    assert server["timeout"] == 600
    assert server["metrics"] is False
    assert server["slots"] is True
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_config.py::test_新增参数默认值 -v`
Expected: FAIL（KeyError）

- [ ] **Step 3: 编写最小实现**

```python
# core/config.py - 修改 DEFAULT_CONFIG

DEFAULT_CONFIG = {
    "model": {
        "last_path": "",
        "mmproj_path": "",
    },
    "server": {
        # Phase 1
        "port": 8080,
        "host": "127.0.0.1",
        "context_size": 4096,
        "n_gpu_layers": 0,
        "parallel": 1,
        # Phase 2 - KV Cache
        "cache_type_k": "f16",
        "cache_type_v": "f16",
        "kv_unified": True,
        "no_kv_offload": False,
        "flash_attn": False,
        "cache_prompt": True,
        "cache_idle_slots": True,
        # Phase 2 - 推理速度
        "threads": -1,
        "threads_batch": -1,
        "batch_size": 2048,
        "ubatch_size": 512,
        "threads_http": -1,
        "no_warmup": False,
        # Phase 2 - 采样参数
        "temp": 0.80,
        "top_k": 40,
        "top_p": 0.95,
        "min_p": 0.05,
        "repeat_penalty": 1.0,
        "seed": -1,
        "n_predict": -1,
        # Phase 2 - 思考模式
        "reasoning": "auto",
        "reasoning_format": "auto",
        "reasoning_budget": -1,
        # Phase 2 - 多模态
        "mmproj_offload": True,
        "image_min_tokens": 0,
        "image_max_tokens": 0,
        # Phase 2 - 安全
        "api_key": "",
        "timeout": 600,
        "metrics": False,
        "slots": True,
    },
    "app": {
        "auto_open_browser": True,
        "llama_cpp_dir": "",
    },
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_config.py::test_新增参数默认值 -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add core/config.py tests/test_config.py
git commit -m "feat(config): 添加 Phase 2 高级参数默认值"
```

---

### Task 2: 创建 param_groups.py 基础结构

**Files:**
- Create: `ui/widgets/__init__.py`
- Create: `ui/widgets/param_groups.py`

- [ ] **Step 1: 创建 widgets 包**

```python
# ui/widgets/__init__.py
"""自定义 Widget 包"""
```

- [ ] **Step 2: 创建 KVCacheParams Widget**

```python
# ui/widgets/param_groups.py
"""高级参数分组 Widget"""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, Label, Select, Switch


class KVCacheParams(Horizontal):
    """KV Cache 与显存参数组"""

    def compose(self) -> ComposeResult:
        yield Label("KV Cache 与显存", classes="section-title")
        with Horizontal(classes="param-row"):
            yield Label("K Cache 量化", classes="param-label")
            yield Select(
                [("f16", "f16"), ("q8_0", "q8_0"), ("q4_0", "q4_0")],
                value="f16",
                id="cache_type_k",
            )
        with Horizontal(classes="param-row"):
            yield Label("V Cache 量化", classes="param-label")
            yield Select(
                [("f16", "f16"), ("q8_0", "q8_0"), ("q4_0", "q4_0")],
                value="f16",
                id="cache_type_v",
            )
        with Horizontal(classes="param-row"):
            yield Label("统一 KV 池", classes="param-label")
            yield Switch(value=True, id="kv_unified")
        with Horizontal(classes="param-row"):
            yield Label("KV 不放 GPU", classes="param-label")
            yield Switch(value=False, id="no_kv_offload")
        with Horizontal(classes="param-row"):
            yield Label("Flash Attention", classes="param-label")
            yield Switch(value=False, id="flash_attn")
        with Horizontal(classes="param-row"):
            yield Label("Prompt Cache", classes="param-label")
            yield Switch(value=True, id="cache_prompt")
        with Horizontal(classes="param-row"):
            yield Label("空闲 Slot 复活", classes="param-label")
            yield Switch(value=True, id="cache_idle_slots")

    def collect_params(self) -> dict:
        """收集 KV Cache 参数"""
        return {
            "cache_type_k": self.query_one("#cache_type_k", Select).value,
            "cache_type_v": self.query_one("#cache_type_v", Select).value,
            "kv_unified": self.query_one("#kv_unified", Switch).value,
            "no_kv_offload": self.query_one("#no_kv_offload", Switch).value,
            "flash_attn": self.query_one("#flash_attn", Switch).value,
            "cache_prompt": self.query_one("#cache_prompt", Switch).value,
            "cache_idle_slots": self.query_one("#cache_idle_slots", Switch).value,
        }

    def restore_params(self, params: dict) -> None:
        """从配置回填 KV Cache 参数"""
        self.query_one("#cache_type_k", Select).value = params.get("cache_type_k", "f16")
        self.query_one("#cache_type_v", Select).value = params.get("cache_type_v", "f16")
        self.query_one("#kv_unified", Switch).value = params.get("kv_unified", True)
        self.query_one("#no_kv_offload", Switch).value = params.get("no_kv_offload", False)
        self.query_one("#flash_attn", Switch).value = params.get("flash_attn", False)
        self.query_one("#cache_prompt", Switch).value = params.get("cache_prompt", True)
        self.query_one("#cache_idle_slots", Switch).value = params.get("cache_idle_slots", True)
```

- [ ] **Step 3: 提交**

```bash
git add ui/widgets/__init__.py ui/widgets/param_groups.py
git commit -m "feat(ui): 创建 KVCacheParams 参数分组 Widget"
```

---

### Task 3: 实现剩余 5 个参数 Widget

**Files:**
- Modify: `ui/widgets/param_groups.py`

- [ ] **Step 1: 添加 InferenceParams**

```python
# ui/widgets/param_groups.py 追加

class InferenceParams(Horizontal):
    """推理速度参数组"""

    def compose(self) -> ComposeResult:
        yield Label("推理速度", classes="section-title")
        with Horizontal(classes="param-row"):
            yield Label("线程数", classes="param-label")
            yield Input(value="-1", id="threads", placeholder="-1=自动")
        with Horizontal(classes="param-row"):
            yield Label("Prompt 线程", classes="param-label")
            yield Input(value="-1", id="threads_batch", placeholder="-1=等于线程数")
        with Horizontal(classes="param-row"):
            yield Label("逻辑批大小", classes="param-label")
            yield Input(value="2048", id="batch_size")
        with Horizontal(classes="param-row"):
            yield Label("物理批大小", classes="param-label")
            yield Input(value="512", id="ubatch_size")
        with Horizontal(classes="param-row"):
            yield Label("HTTP 线程", classes="param-label")
            yield Input(value="-1", id="threads_http", placeholder="-1=自动")
        with Horizontal(classes="param-row"):
            yield Label("跳过预热", classes="param-label")
            yield Switch(value=False, id="no_warmup")

    def collect_params(self) -> dict:
        return {
            "threads": int(self.query_one("#threads", Input).value or "-1"),
            "threads_batch": int(self.query_one("#threads_batch", Input).value or "-1"),
            "batch_size": int(self.query_one("#batch_size", Input).value or "2048"),
            "ubatch_size": int(self.query_one("#ubatch_size", Input).value or "512"),
            "threads_http": int(self.query_one("#threads_http", Input).value or "-1"),
            "no_warmup": self.query_one("#no_warmup", Switch).value,
        }

    def restore_params(self, params: dict) -> None:
        self.query_one("#threads", Input).value = str(params.get("threads", -1))
        self.query_one("#threads_batch", Input).value = str(params.get("threads_batch", -1))
        self.query_one("#batch_size", Input).value = str(params.get("batch_size", 2048))
        self.query_one("#ubatch_size", Input).value = str(params.get("ubatch_size", 512))
        self.query_one("#threads_http", Input).value = str(params.get("threads_http", -1))
        self.query_one("#no_warmup", Switch).value = params.get("no_warmup", False)
```

- [ ] **Step 2: 添加 SamplingParams**

```python
# ui/widgets/param_groups.py 追加

from textual.widgets import Slider

class SamplingParams(Horizontal):
    """采样参数组"""

    def compose(self) -> ComposeResult:
        yield Label("采样参数", classes="section-title")
        with Horizontal(classes="param-row"):
            yield Label("温度", classes="param-label")
            yield Slider(0, 200, value=80, id="temp")
        with Horizontal(classes="param-row"):
            yield Label("Top-K", classes="param-label")
            yield Input(value="40", id="top_k")
        with Horizontal(classes="param-row"):
            yield Label("Top-P", classes="param-label")
            yield Slider(0, 100, value=95, id="top_p")
        with Horizontal(classes="param-row"):
            yield Label("Min-P", classes="param-label")
            yield Slider(0, 100, value=5, id="min_p")
        with Horizontal(classes="param-row"):
            yield Label("重复惩罚", classes="param-label")
            yield Slider(50, 200, value=100, id="repeat_penalty")
        with Horizontal(classes="param-row"):
            yield Label("随机种子", classes="param-label")
            yield Input(value="-1", id="seed", placeholder="-1=随机")
        with Horizontal(classes="param-row"):
            yield Label("最大生成", classes="param-label")
            yield Input(value="-1", id="n_predict", placeholder="-1=无限")

    def collect_params(self) -> dict:
        return {
            "temp": self.query_one("#temp", Slider).value / 100.0,
            "top_k": int(self.query_one("#top_k", Input).value or "40"),
            "top_p": self.query_one("#top_p", Slider).value / 100.0,
            "min_p": self.query_one("#min_p", Slider).value / 100.0,
            "repeat_penalty": self.query_one("#repeat_penalty", Slider).value / 100.0,
            "seed": int(self.query_one("#seed", Input).value or "-1"),
            "n_predict": int(self.query_one("#n_predict", Input).value or "-1"),
        }

    def restore_params(self, params: dict) -> None:
        self.query_one("#temp", Slider).value = int(params.get("temp", 0.80) * 100)
        self.query_one("#top_k", Input).value = str(params.get("top_k", 40))
        self.query_one("#top_p", Slider).value = int(params.get("top_p", 0.95) * 100)
        self.query_one("#min_p", Slider).value = int(params.get("min_p", 0.05) * 100)
        self.query_one("#repeat_penalty", Slider).value = int(params.get("repeat_penalty", 1.0) * 100)
        self.query_one("#seed", Input).value = str(params.get("seed", -1))
        self.query_one("#n_predict", Input).value = str(params.get("n_predict", -1))
```

- [ ] **Step 3: 添加 ReasoningParams**

```python
# ui/widgets/param_groups.py 追加

class ReasoningParams(Horizontal):
    """思考/推理模式参数组"""

    def compose(self) -> ComposeResult:
        yield Label("思考模式", classes="section-title")
        with Horizontal(classes="param-row"):
            yield Label("思考模式", classes="param-label")
            yield Select(
                [("auto", "auto"), ("on", "on"), ("off", "off")],
                value="auto",
                id="reasoning",
            )
        with Horizontal(classes="param-row"):
            yield Label("思考格式", classes="param-label")
            yield Select(
                [("auto", "auto"), ("none", "none"), ("deepseek", "deepseek"), ("deepseek-legacy", "deepseek-legacy")],
                value="auto",
                id="reasoning_format",
            )
        with Horizontal(classes="param-row"):
            yield Label("思考预算", classes="param-label")
            yield Input(value="-1", id="reasoning_budget", placeholder="-1=不限")

    def collect_params(self) -> dict:
        return {
            "reasoning": self.query_one("#reasoning", Select).value,
            "reasoning_format": self.query_one("#reasoning_format", Select).value,
            "reasoning_budget": int(self.query_one("#reasoning_budget", Input).value or "-1"),
        }

    def restore_params(self, params: dict) -> None:
        self.query_one("#reasoning", Select).value = params.get("reasoning", "auto")
        self.query_one("#reasoning_format", Select).value = params.get("reasoning_format", "auto")
        self.query_one("#reasoning_budget", Input).value = str(params.get("reasoning_budget", -1))
```

- [ ] **Step 4: 添加 MultimodalParams**

```python
# ui/widgets/param_groups.py 追加

class MultimodalParams(Horizontal):
    """多模态参数组"""

    def compose(self) -> ComposeResult:
        yield Label("多模态", classes="section-title")
        with Horizontal(classes="param-row"):
            yield Label("视觉放 GPU", classes="param-label")
            yield Switch(value=True, id="mmproj_offload")
        with Horizontal(classes="param-row"):
            yield Label("最小视觉 Token", classes="param-label")
            yield Input(value="0", id="image_min_tokens", placeholder="0=默认")
        with Horizontal(classes="param-row"):
            yield Label("最大视觉 Token", classes="param-label")
            yield Input(value="0", id="image_max_tokens", placeholder="0=默认")

    def collect_params(self) -> dict:
        return {
            "mmproj_offload": self.query_one("#mmproj_offload", Switch).value,
            "image_min_tokens": int(self.query_one("#image_min_tokens", Input).value or "0"),
            "image_max_tokens": int(self.query_one("#image_max_tokens", Input).value or "0"),
        }

    def restore_params(self, params: dict) -> None:
        self.query_one("#mmproj_offload", Switch).value = params.get("mmproj_offload", True)
        self.query_one("#image_min_tokens", Input).value = str(params.get("image_min_tokens", 0))
        self.query_one("#image_max_tokens", Input).value = str(params.get("image_max_tokens", 0))
```

- [ ] **Step 5: 添加 SecurityParams**

```python
# ui/widgets/param_groups.py 追加

class SecurityParams(Horizontal):
    """安全与访问控制参数组"""

    def compose(self) -> ComposeResult:
        yield Label("安全", classes="section-title")
        with Horizontal(classes="param-row"):
            yield Label("API Key", classes="param-label")
            yield Input(value="", id="api_key", placeholder="留空不校验")
        with Horizontal(classes="param-row"):
            yield Label("超时秒数", classes="param-label")
            yield Input(value="600", id="timeout")
        with Horizontal(classes="param-row"):
            yield Label("Prometheus", classes="param-label")
            yield Switch(value=False, id="metrics")
        with Horizontal(classes="param-row"):
            yield Label("Slots 端点", classes="param-label")
            yield Switch(value=True, id="slots")

    def collect_params(self) -> dict:
        return {
            "api_key": self.query_one("#api_key", Input).value.strip(),
            "timeout": int(self.query_one("#timeout", Input).value or "600"),
            "metrics": self.query_one("#metrics", Switch).value,
            "slots": self.query_one("#slots", Switch).value,
        }

    def restore_params(self, params: dict) -> None:
        self.query_one("#api_key", Input).value = params.get("api_key", "")
        self.query_one("#timeout", Input).value = str(params.get("timeout", 600))
        self.query_one("#metrics", Switch).value = params.get("metrics", False)
        self.query_one("#slots", Switch).value = params.get("slots", True)
```

- [ ] **Step 6: 提交**

```bash
git add ui/widgets/param_groups.py
git commit -m "feat(ui): 实现全部 6 个参数分组 Widget"
```

---

### Task 4: 修改 ControlPanel 集成参数 Widget

**Files:**
- Modify: `ui/control_panel.py:226-304` (compose 方法)
- Modify: `ui/control_panel.py:329-340` (collect_params 方法)

- [ ] **Step 1: 修改 imports**

```python
# ui/control_panel.py 顶部 imports 追加

from textual.widgets import Collapsible
from ui.widgets.param_groups import (
    KVCacheParams, InferenceParams, SamplingParams,
    ReasoningParams, MultimodalParams, SecurityParams,
)
```

- [ ] **Step 2: 修改 compose 方法**

在 `action-row` 之前插入折叠面板：

```python
# ControlPanel.compose() 中，在 options-row 之后、action-row 之前插入

        # 高级参数折叠区
        with Collapsible(title="KV Cache 与显存", collapsed=False, id="coll_kvcache"):
            yield KVCacheParams()
        with Collapsible(title="推理速度", collapsed=True, id="coll_inference"):
            yield InferenceParams()
        with Collapsible(title="采样参数", collapsed=False, id="coll_sampling"):
            yield SamplingParams()
        with Collapsible(title="思考模式", collapsed=True, id="coll_reasoning"):
            yield ReasoningParams()
        with Collapsible(title="多模态", collapsed=True, id="coll_multimodal"):
            yield MultimodalParams()
        with Collapsible(title="安全", collapsed=True, id="coll_security"):
            yield SecurityParams()
```

- [ ] **Step 3: 修改 collect_params 方法**

```python
# ControlPanel.collect_params() 替换为

    def collect_params(self) -> dict:
        """收集当前所有参数为字典"""
        params = {
            "model_path": self.query_one("#model_path", Input).value.strip(),
            "mmproj_path": self.query_one("#mmproj_path", Input).value.strip(),
            "port": int(self.query_one("#port", Input).value or "8080"),
            "host": self.query_one("#host", Select).value,
            "context_size": int(self.query_one("#context_size", Select).value),
            "n_gpu_layers": int(self.query_one("#n_gpu_layers", Input).value or "0"),
            "parallel": int(self.query_one("#parallel", Select).value),
            "auto_open_browser": self.query_one("#auto_open_browser", Switch).value,
        }

        # 合并各分组参数
        for widget_cls in [KVCacheParams, InferenceParams, SamplingParams,
                           ReasoningParams, MultimodalParams, SecurityParams]:
            widget = self.query_one(widget_cls)
            params.update(widget.collect_params())

        return params
```

- [ ] **Step 4: 添加 restore_params 方法**

```python
# ControlPanel 类中新增方法

    def restore_advanced_params(self, config_data: dict) -> None:
        """从配置回填高级参数"""
        server = config_data.get("server", {})
        for widget_cls in [KVCacheParams, InferenceParams, SamplingParams,
                           ReasoningParams, MultimodalParams, SecurityParams]:
            widget = self.query_one(widget_cls)
            widget.restore_params(server)
```

- [ ] **Step 5: 提交**

```bash
git add ui/control_panel.py
git commit -m "feat(ui): ControlPanel 集成 6 个参数分组 Widget"
```

---

### Task 5: 扩展 _build_command

**Files:**
- Modify: `core/process_manager.py:166-197`
- Test: `tests/test_process_manager.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_process_manager.py 追加

def test_高级参数_KVCache():
    """KV Cache 参数应正确拼接到命令行"""
    bus = EventBus()
    sup = ProcessSupervisor(bus)

    params = {
        "model_path": "test.gguf",
        "server_path": "llama-server",
        "port": 8080,
        "host": "127.0.0.1",
        "context_size": 4096,
        "n_gpu_layers": 0,
        "parallel": 1,
        "cache_type_k": "q8_0",
        "flash_attn": True,
    }

    cmd = sup._build_command(params)
    assert "-ctk" in cmd
    assert cmd[cmd.index("-ctk") + 1] == "q8_0"
    assert "-fa" in cmd


def test_高级参数_采样():
    """采样参数非默认值时应拼接到命令行"""
    bus = EventBus()
    sup = ProcessSupervisor(bus)

    params = {
        "model_path": "test.gguf",
        "server_path": "llama-server",
        "port": 8080,
        "host": "127.0.0.1",
        "context_size": 4096,
        "n_gpu_layers": 0,
        "parallel": 1,
        "temp": 0.7,
        "top_k": 20,
    }

    cmd = sup._build_command(params)
    assert "--temp" in cmd
    assert cmd[cmd.index("--temp") + 1] == "0.7"
    assert "--top-k" in cmd
    assert cmd[cmd.index("--top-k") + 1] == "20"


def test_高级参数_默认值不拼接():
    """默认值参数不应出现在命令行中"""
    bus = EventBus()
    sup = ProcessSupervisor(bus)

    params = {
        "model_path": "test.gguf",
        "server_path": "llama-server",
        "port": 8080,
        "host": "127.0.0.1",
        "context_size": 4096,
        "n_gpu_layers": 0,
        "parallel": 1,
        # 所有高级参数都是默认值
    }

    cmd = sup._build_command(params)
    assert "-ctk" not in cmd
    assert "-fa" not in cmd
    assert "--temp" not in cmd
    assert "--api-key" not in cmd


def test_高级参数_安全():
    """API Key 非空时应拼接"""
    bus = EventBus()
    sup = ProcessSupervisor(bus)

    params = {
        "model_path": "test.gguf",
        "server_path": "llama-server",
        "port": 8080,
        "host": "127.0.0.1",
        "context_size": 4096,
        "n_gpu_layers": 0,
        "parallel": 1,
        "api_key": "my-secret-key",
    }

    cmd = sup._build_command(params)
    assert "--api-key" in cmd
    assert cmd[cmd.index("--api-key") + 1] == "my-secret-key"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_process_manager.py::test_高级参数_KVCache -v`
Expected: FAIL（-ctk 不在命令行中）

- [ ] **Step 3: 扩展 _build_command**

```python
# core/process_manager.py - _build_command 方法末尾追加

        # Phase 2 - KV Cache 与显存
        if params.get("cache_type_k", "f16") != "f16":
            cmd.extend(["-ctk", params["cache_type_k"]])
        if params.get("cache_type_v", "f16") != "f16":
            cmd.extend(["-ctv", params["cache_type_v"]])
        if not params.get("kv_unified", True):
            cmd.append("--no-kv-unified")
        if params.get("no_kv_offload", False):
            cmd.append("--no-kv-offload")
        if params.get("flash_attn", False):
            cmd.append("-fa")
        if not params.get("cache_prompt", True):
            cmd.append("--no-cache-prompt")
        if not params.get("cache_idle_slots", True):
            cmd.append("--no-cache-idle-slots")

        # Phase 2 - 推理速度
        if params.get("threads", -1) != -1:
            cmd.extend(["-t", str(params["threads"])])
        if params.get("threads_batch", -1) != -1:
            cmd.extend(["-tb", str(params["threads_batch"])])
        if params.get("batch_size", 2048) != 2048:
            cmd.extend(["-b", str(params["batch_size"])])
        if params.get("ubatch_size", 512) != 512:
            cmd.extend(["-ub", str(params["ubatch_size"])])
        if params.get("threads_http", -1) != -1:
            cmd.extend(["--threads-http", str(params["threads_http"])])
        if params.get("no_warmup", False):
            cmd.append("--no-warmup")

        # Phase 2 - 采样参数
        if abs(params.get("temp", 0.80) - 0.80) > 0.001:
            cmd.extend(["--temp", str(params["temp"])])
        if params.get("top_k", 40) != 40:
            cmd.extend(["--top-k", str(params["top_k"])])
        if abs(params.get("top_p", 0.95) - 0.95) > 0.001:
            cmd.extend(["--top-p", str(params["top_p"])])
        if abs(params.get("min_p", 0.05) - 0.05) > 0.001:
            cmd.extend(["--min-p", str(params["min_p"])])
        if abs(params.get("repeat_penalty", 1.0) - 1.0) > 0.001:
            cmd.extend(["--repeat-penalty", str(params["repeat_penalty"])])
        if params.get("seed", -1) != -1:
            cmd.extend(["-s", str(params["seed"])])
        if params.get("n_predict", -1) != -1:
            cmd.extend(["-n", str(params["n_predict"])])

        # Phase 2 - 思考模式
        if params.get("reasoning", "auto") != "auto":
            cmd.extend(["-rea", params["reasoning"]])
        if params.get("reasoning_format", "auto") != "auto":
            cmd.extend(["--reasoning-format", params["reasoning_format"]])
        if params.get("reasoning_budget", -1) != -1:
            cmd.extend(["--reasoning-budget", str(params["reasoning_budget"])])

        # Phase 2 - 多模态
        if not params.get("mmproj_offload", True):
            cmd.append("--no-mmproj-offload")
        if params.get("image_min_tokens", 0) > 0:
            cmd.extend(["--image-min-tokens", str(params["image_min_tokens"])])
        if params.get("image_max_tokens", 0) > 0:
            cmd.extend(["--image-max-tokens", str(params["image_max_tokens"])])

        # Phase 2 - 安全与访问控制
        if params.get("api_key", ""):
            cmd.extend(["--api-key", params["api_key"]])
        if params.get("timeout", 600) != 600:
            cmd.extend(["--timeout", str(params["timeout"])])
        if params.get("metrics", False):
            cmd.append("--metrics")
        if not params.get("slots", True):
            cmd.append("--no-slots")

        return cmd
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_process_manager.py -v`
Expected: ALL PASS

- [ ] **Step 5: 提交**

```bash
git add core/process_manager.py tests/test_process_manager.py
git commit -m "feat(process): _build_command 支持全部 26 个高级参数"
```

---

### Task 6: 创建 MonitorPanel

**Files:**
- Create: `ui/widgets/monitor_panel.py`
- Test: `tests/test_monitor.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_monitor.py

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock


def test_GPU检测失败时隐藏():
    """nvidia-smi 不可用时应标记 _gpu_available = False"""
    from ui.widgets.monitor_panel import MonitorPanel

    panel = MonitorPanel()
    # 模拟 nvidia-smi 不存在
    with patch("subprocess.run", side_effect=FileNotFoundError):
        panel._detect_gpu()
    assert panel._gpu_available is False


def test_格式化内存():
    """_format_bytes 应正确格式化"""
    from ui.widgets.monitor_panel import MonitorPanel

    assert MonitorPanel._format_bytes(1024) == "1.0 KB"
    assert MonitorPanel._format_bytes(1024 * 1024) == "1.0 MB"
    assert MonitorPanel._format_bytes(1024 * 1024 * 1024) == "1.0 GB"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_monitor.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 MonitorPanel**

```python
# ui/widgets/monitor_panel.py
"""运行时监控面板：GPU/内存/请求状态"""

import logging
import subprocess
import threading
from typing import Any

import psutil
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

logger = logging.getLogger(__name__)


class MonitorPanel(Horizontal):
    """运行时监控面板"""

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self._gpu_available: bool | None = None  # None = 未检测
        self._running = False
        self._thread: threading.Thread | None = None
        self._pid: int | None = None
        self._port: int = 8080

    def compose(self) -> ComposeResult:
        yield Static("GPU: --", id="mon_gpu")
        yield Static("RAM: --", id="mon_ram")
        yield Static("Slots: --/--  请求: --", id="mon_slots")

    def _detect_gpu(self) -> None:
        """检测 nvidia-smi 是否可用"""
        try:
            subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, timeout=2, check=True,
            )
            self._gpu_available = True
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
            self._gpu_available = False

    def start_monitoring(self, pid: int, port: int) -> None:
        """启动监控轮询"""
        self._pid = pid
        self._port = port

        if self._gpu_available is None:
            self._detect_gpu()
            if not self._gpu_available:
                self.query_one("#mon_gpu", Static).display = False

        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._poll_loop, daemon=True)
            self._thread.start()

    def stop_monitoring(self) -> None:
        """停止监控轮询"""
        self._running = False

    def _poll_loop(self) -> None:
        """后台轮询线程"""
        while self._running:
            try:
                self._collect_and_update()
            except Exception:
                logger.debug("监控采集异常", exc_info=True)
            threading.Event().wait(2.0)

    def _collect_and_update(self) -> None:
        """采集数据并更新 UI"""
        gpu_text = self._collect_gpu()
        ram_text = self._collect_ram()
        slots_text = self._collect_slots()

        def update():
            if gpu_text:
                self.query_one("#mon_gpu", Static).update(gpu_text)
            self.query_one("#mon_ram", Static).update(ram_text)
            self.query_one("#mon_slots", Static).update(slots_text)

        self.app.call_from_thread(update)

    def _collect_gpu(self) -> str:
        """采集 GPU 信息"""
        if not self._gpu_available:
            return ""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2,
            )
            parts = result.stdout.strip().split(", ")
            util = parts[0].strip()
            used = self._format_bytes(int(parts[1].strip()) * 1024 * 1024)
            total = self._format_bytes(int(parts[2].strip()) * 1024 * 1024)
            return f"GPU: {util}%  {used}/{total}"
        except Exception:
            return "GPU: --"

    def _collect_ram(self) -> str:
        """采集进程内存"""
        if not self._pid:
            return "RAM: --"
        try:
            proc = psutil.Process(self._pid)
            rss = proc.memory_info().rss
            return f"RAM: {self._format_bytes(rss)}"
        except psutil.NoSuchProcess:
            return "RAM: --"

    def _collect_slots(self) -> str:
        """采集 Slots 信息"""
        import urllib.request
        import json

        try:
            url = f"http://127.0.0.1:{self._port}/slots"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=1) as resp:
                data = json.loads(resp.read())
                active = sum(1 for s in data if s.get("state", 0) != 0)
                total = len(data)
                return f"Slots: {active}/{total}  请求: {active}"
        except Exception:
            return "Slots: --/--  请求: --"

    @staticmethod
    def _format_bytes(n: int) -> str:
        """格式化字节数"""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} PB"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_monitor.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add ui/widgets/monitor_panel.py tests/test_monitor.py
git commit -m "feat(ui): 创建 MonitorPanel 运行时监控组件"
```

---

### Task 7: 集成 MonitorPanel 到 app.py

**Files:**
- Modify: `ui/app.py`

- [ ] **Step 1: 修改 imports**

```python
# ui/app.py 顶部追加

from ui.widgets.monitor_panel import MonitorPanel
```

- [ ] **Step 2: 修改 compose 方法**

```python
# LlamaLauncherApp.compose() 修改为

    def compose(self) -> ComposeResult:
        """组装界面布局"""
        yield ControlPanel(id="control")
        with Vertical(id="right-pane"):
            yield LogPanel(id="log")
            yield MonitorPanel(id="monitor")
        yield Footer()
```

- [ ] **Step 3: 修改 CSS**

```python
# TUI_CSS 中追加

#right-pane {
    width: 1fr;
    layout: vertical;
}

#monitor {
    height: auto;
    max-height: 3;
    background: $panel;
    border: solid $primary-background;
    padding: 0 1;
}
```

- [ ] **Step 4: 修改 _on_status_changed**

```python
# LlamaLauncherApp._on_status_changed() 修改

    def _on_status_changed(self, **data) -> None:
        """响应进程状态变化事件"""
        status = data.get("status", "stopped")
        panel = self.query_one("#control", ControlPanel)
        monitor = self.query_one("#monitor", MonitorPanel)

        self._safe_update(panel.update_status, status)

        log_panel = self.query_one("#log", LogPanel)

        if status == "starting":
            self._safe_update(log_panel.add_line, "正在启动 llama-server...")

        if status == "running":
            config_data = self._config.load()
            if config_data["app"]["auto_open_browser"]:
                port = config_data["server"]["port"]
                webbrowser.open(f"http://127.0.0.1:{port}")

            self._safe_update(log_panel.add_line, "服务器已就绪，可通过浏览器访问")

            # 启动监控
            pid = data.get("pid")
            port = config_data["server"]["port"]
            self._safe_update(monitor.start_monitoring, pid, port)

        if status == "stopped":
            self._safe_update(log_panel.add_line, "服务器已停止")
            self._safe_update(monitor.stop_monitoring)

        if status == "crashed":
            exit_code = data.get("exit_code", -1)
            self._safe_update(
                log_panel.add_line,
                f"llama-server 异常退出 (退出码: {exit_code})，请检查日志",
            )
            self._safe_update(
                self.notify,
                f"llama-server 异常退出 (退出码: {exit_code})，请检查日志",
                severity="error",
            )
            self._safe_update(monitor.stop_monitoring)
```

- [ ] **Step 5: 修改 on_mount 回填高级参数**

```python
# LlamaLauncherApp.on_mount() 末尾追加

        # 回填高级参数
        panel.restore_advanced_params(config_data)
```

- [ ] **Step 6: 提交**

```bash
git add ui/app.py
git commit -m "feat(app): 集成 MonitorPanel 到主界面"
```

---

### Task 8: 手动验证与集成测试

- [ ] **Step 1: 运行全部测试**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: 启动应用手动验证**

Run: `python main.py`

验证项：
- [ ] 折叠面板展开/收起正常
- [ ] 高级参数默认值显示正确
- [ ] 修改参数后启动服务器，命令行参数正确
- [ ] 监控面板在服务器启动后显示 GPU/RAM/Slots 信息
- [ ] 服务器停止后监控停止更新
- [ ] 参数保存到 config.yaml 后重启能回填

- [ ] **Step 3: 最终提交**

```bash
git add -A
git commit -m "feat: Phase 2 高级参数与运行时监控完成"
```
