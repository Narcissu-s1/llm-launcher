# Phase 2 设计文档：高级参数与运行时监控

> 范围：2.1 高级参数（26 个）+ 2.2 运行时监控
> 方案：模块化组件（方案 B）
> 日期：2026-05-26

---

## 1. 目标

扩展 llama-server 参数支持至 26 个（6 个分组），并提供 GPU/内存/请求的实时监控。

---

## 2. 文件结构

```
ui/
├── widgets/
│   ├── __init__.py
│   ├── param_groups.py      # 6 个参数分组 Widget
│   └── monitor_panel.py     # 运行时监控 Panel
├── control_panel.py          # 修改：组合参数分组 Widget
├── log_panel.py              # 不变
└── app.py                    # 修改：接入 MonitorPanel
core/
├── config.py                 # 修改：DEFAULT_CONFIG 扩展
└── process_manager.py        # 修改：_build_command 扩展
tests/
├── test_process_manager.py   # 扩展：新增参数拼接测试
├── test_config.py            # 扩展：新增参数配置测试
├── test_param_groups.py      # 新增：参数 Widget 收集测试
└── test_monitor.py           # 新增：监控逻辑测试
```

---

## 3. 参数分组 Widget

`ui/widgets/param_groups.py` 中定义 6 个 Widget 类：

| 类名 | 对应分组 | 控件类型 |
|------|----------|----------|
| `KVCacheParams` | KV Cache 与显存 | Select × 1, Switch × 5 |
| `InferenceParams` | 推理速度 | Input × 5, Switch × 1 |
| `SamplingParams` | 采样参数 | Slider × 4, Input × 3 |
| `ReasoningParams` | 思考/推理模式 | Select × 2, Input × 1 |
| `MultimodalParams` | 多模态 | Switch × 1, Input × 2 |
| `SecurityParams` | 安全与访问控制 | Input × 2, Switch × 2 |

每个 Widget 类暴露统一接口：
- `compose()` — 生成控件
- `collect_params() -> dict` — 收集参数值
- `restore_params(dict)` — 从配置回填

使用 Textual 的 `Collapsible` 组件包裹每个分组，默认展开 KV Cache 和采样参数。

---

## 4. 配置扩展

`core/config.py` 的 `DEFAULT_CONFIG` 新增字段：

```python
"server": {
    # Phase 1 已有
    "port": 8080,
    "host": "127.0.0.1",
    "context_size": 4096,
    "n_gpu_layers": 0,
    "parallel": 1,
    # Phase 2 新增 - KV Cache
    "cache_type_k": "f16",
    "cache_type_v": "f16",
    "kv_unified": True,
    "no_kv_offload": False,
    "flash_attn": False,
    "cache_prompt": True,
    "cache_idle_slots": True,
    # Phase 2 新增 - 推理速度
    "threads": -1,
    "threads_batch": -1,
    "batch_size": 2048,
    "ubatch_size": 512,
    "threads_http": -1,
    "no_warmup": False,
    # Phase 2 新增 - 采样参数
    "temp": 0.80,
    "top_k": 40,
    "top_p": 0.95,
    "min_p": 0.05,
    "repeat_penalty": 1.0,
    "seed": -1,
    "n_predict": -1,
    # Phase 2 新增 - 思考模式
    "reasoning": "auto",
    "reasoning_format": "auto",
    "reasoning_budget": -1,
    # Phase 2 新增 - 多模态
    "mmproj_offload": True,
    "image_min_tokens": 0,
    "image_max_tokens": 0,
    # Phase 2 新增 - 安全
    "api_key": "",
    "timeout": 600,
    "metrics": False,
    "slots": True,
}
```

---

## 5. 数据流

1. `ControlPanel.compose()` — 组合 6 个参数 Widget + 原有基本参数
2. `ControlPanel.collect_params()` — 调用各 Widget 的 `collect_params()` 合并为一个 dict
3. `app.py` 的 `_handle_start()` — 将 dict 传给 `ProcessSupervisor.start()`
4. `ProcessSupervisor._build_command()` — 遍历 dict，非默认值拼接到命令行
5. `ConfigStore` — 启动时保存所有参数，`on_mount` 时回填到各 Widget

---

## 6. 命令构建逻辑

`_build_command()` 扩展规则：

- **布尔参数**：默认值为 False 时，True 才拼接；默认值为 True 时，False 才拼 `--no-xxx`
- **数值参数**：非默认值才拼接
- **字符串参数**：非空才拼接
- **浮点参数**：用 epsilon 比较（`abs(val - default) > 0.001`）

示例：

```python
# KV Cache
if params.get("cache_type_k", "f16") != "f16":
    cmd.extend(["-ctk", params["cache_type_k"]])
if params.get("flash_attn", False):
    cmd.append("-fa")

# 采样参数
if abs(params.get("temp", 0.80) - 0.80) > 0.001:
    cmd.extend(["--temp", str(params["temp"])])

# 安全
if params.get("api_key", ""):
    cmd.extend(["--api-key", params["api_key"]])
```

---

## 7. 运行时监控

### 7.1 MonitorPanel Widget

```
┌─ 监控栏 ──────────────────────────────┐
│ GPU: 45%  2.1/8.0 GB   │  RAM: 1.2 GB │
│ Slots: 2/4  活跃请求: 1               │
└────────────────────────────────────────┘
```

放在 `LogPanel` 下方，仅在服务器 `running` 状态时启用。

### 7.2 数据源

| 指标 | 数据源 | 刷新方式 |
|------|--------|----------|
| GPU 利用率 | `nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits` | 2 秒轮询 |
| GPU 显存 | `nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits` | 2 秒轮询 |
| 进程内存 | `psutil.Process(pid).memory_info().rss` | 2 秒轮询 |
| 活跃请求 | `GET http://127.0.0.1:{port}/slots`，统计 `state != 0` | 2 秒轮询 |
| Slot 上下文 | `/slots` 响应中的 `n_ctx` / `n_past` | 2 秒轮询 |

### 7.3 实现逻辑

1. `MonitorPanel` 内部启动后台线程，每 2 秒采集数据
2. 通过 `call_from_thread` 更新 UI
3. GPU 检测：首次运行时尝试调用 `nvidia-smi`，失败则标记 `_gpu_available = False`，隐藏 GPU 行
4. 监控仅在服务器 `running` 状态时启用，`stopped`/`crashed` 时停止轮询
5. `/slots` 请求超时 1 秒，失败时不更新（不报错）

### 7.4 与 app.py 的集成

- `LlamaLauncherApp.compose()` 中在 `LogPanel` 下方 yield `MonitorPanel`
- `_on_status_changed()` 中根据状态启停监控轮询
- `_on_status_changed()` 传递 `pid` 和 `port` 给 `MonitorPanel`

---

## 8. UI 布局

```
┌─ ControlPanel ─────────────┬─ LogPanel ──────────────────┐
│ 模型选择                    │ [20:15:03] 正在启动...       │
│ [模型路径...] [浏览]        │ [20:15:05] 加载完成          │
│ [mmproj...]   [浏览]        │ [20:15:06] 服务器已就绪      │
│ [llama.cpp 目录...] [选择]  │                              │
│ ● 已停止                    │                              │
│ 基本参数                    │                              │
│ [上下文大小] [4096 ▼]       │                              │
│ [GPU 层数]  [0] [全GPU][CPU]│                              │
│ [并发数]    [1 ▼]           │                              │
│ [端口]      [8080]          │                              │
│ [监听地址]  [127.0.0.1 ▼]   │                              │
│ ▼ KV Cache 与显存           ├─ 监控栏 ────────────────────┤
│   [cache_type_k] [f16 ▼]   │ GPU: 45%  2.1/8.0 GB        │
│   [flash_attn]   [开关]     │ RAM: 1.2 GB                 │
│ ▶ 推理速度          [收起]  │ Slots: 2/4  活跃请求: 1     │
│ ▶ 采样参数          [收起]  │                              │
│ ▶ 思考模式          [收起]  │                              │
│ ▶ 多模态            [收起]  │                              │
│ ▶ 安全              [收起]  │                              │
│ [启动] [停止]               │                              │
└─────────────────────────────┴──────────────────────────────┘
```

---

## 9. 错误处理

| 场景 | 处理方式 |
|------|----------|
| nvidia-smi 不存在 | 首次调用失败后标记 `_gpu_available = False`，隐藏 GPU 行，不报错 |
| nvidia-smi 超时 | 单次采集超时 2 秒，跳过本次更新，不报错 |
| /slots 请求失败 | 超时 1 秒，跳过本次更新，不报错 |
| /slots 返回非 JSON | 捕获异常，跳过本次更新 |
| psutil 进程不存在 | 进程已退出时停止轮询 |
| 参数值非法（如端口 > 65535） | `collect_params()` 中校验，弹窗提示，阻止启动 |

---

## 10. 测试策略

| 测试类型 | 覆盖内容 |
|----------|----------|
| 单元测试 | `_build_command()` 的参数拼接逻辑（每个参数分组一组测试用例） |
| 单元测试 | `collect_params()` 的参数收集和默认值处理 |
| 单元测试 | 配置读写（新增参数的序列化/反序列化） |
| 集成测试 | `MonitorPanel` 的 GPU 检测逻辑（mock nvidia-smi） |
| 手动测试 | UI 折叠展开、参数回填、监控刷新 |

---

## 11. 实现顺序

1. 扩展 `DEFAULT_CONFIG`（`core/config.py`）
2. 实现 6 个参数 Widget（`ui/widgets/param_groups.py`）
3. 修改 `ControlPanel` 组合 Widget（`ui/control_panel.py`）
4. 扩展 `_build_command()`（`core/process_manager.py`）
5. 实现 `MonitorPanel`（`ui/widgets/monitor_panel.py`）
6. 集成到 `app.py`
7. 编写测试
8. 手动验证
