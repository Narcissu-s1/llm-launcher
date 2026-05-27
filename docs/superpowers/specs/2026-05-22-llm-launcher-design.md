# LLM 本地模型启动器 — 设计文档

> 状态：已确认  
> 基于需求文档：[llm-launcher-需求文档.md](../llm-launcher-需求文档.md)  
> 日期：2026-05-22

---

## 1. 架构概览

采用**三层分离架构**，核心层与 UI 层通过 EventBus 解耦。Phase 1 使用 Textual TUI，后续可替换 UI 层为 PySide6/PyWebView 而核心层零改动。

```
┌─────────────────────────┐
│   UI 层 (Textual/后续GUI) │  ← 可替换
├─────────────────────────┤
│   EventBus (发布/订阅)     │  ← 解耦桥梁
├─────────────────────────┤
│   核心领域层               │  ← 纯 Python，无框架依赖，可独立单测
│   ConfigStore            │
│   ProcessSupervisor      │
│   LogMonitor             │
│   ModelResolver          │
└─────────────────────────┘
```

## 2. 目录结构

```
llm-launcher/
├── core/
│   ├── __init__.py
│   ├── config.py            # ConfigStore — YAML 读写
│   ├── process_manager.py   # ProcessSupervisor — 启动/停止/检测
│   ├── log_watcher.py       # LogMonitor — 管道读取 stdout/stderr
│   ├── model_resolver.py    # ModelResolver — 搜索 llama-server 路径
│   └── events.py            # EventBus — 简单发布/订阅
├── ui/
│   ├── __init__.py
│   ├── app.py               # LlamaLauncherApp — Textual App 入口
│   ├── control_panel.py     # 左侧：参数配置 + 启停按钮
│   ├── log_panel.py         # 右侧：实时日志
│   └── widgets/             # 可复用小组件（文件选择器、滑块等）
│       └── __init__.py
├── tests/
│   ├── test_config.py
│   ├── test_process_manager.py
│   ├── test_model_resolver.py
│   └── test_events.py
├── config.yaml              # 运行时生成，便携式存储
├── requirements.txt
└── main.py                  # 入口
```

## 3. 核心层模块设计

### 3.1 ConfigStore

```python
class ConfigStore:
    """YAML 配置文件读写，线程安全"""
    def load() -> dict          # 文件不存在时返回默认值
    def save(data: dict) -> None
    def get(key: str) -> Any    # 支持点号嵌套路径，如 "model.last_path"
    def set(key: str, value) -> None
```

- 配置文件损坏时：用默认值重建，写日志告警
- 默认路径：应用同目录 `./config.yaml`

### 3.2 ProcessSupervisor

```python
class ProcessSupervisor:
    """llama-server 进程生命周期管理"""
    def __init__(self, event_bus: EventBus)

    def start(params: dict) -> int          # 返回 PID，失败抛异常
    def stop() -> None                      # SIGTERM → 等3s → SIGKILL
    def status() -> ProcessStatus           # stopped / starting / running / crashed

    def _poll_loop() -> None                # 后台轮询，1s 间隔，检测 PID 存活
```

- 启动前检查端口是否可用（socket bind 探测）
- `starting` 状态 → 检测到 stdout 输出 `"server is listening"` 后切换为 `running`
- 轮询发现 PID 不存在但状态为 `running` → 切换为 `crashed`，收集退出码和最后 N 行日志

### 3.3 LogMonitor

```python
class LogMonitor:
    """读取 subprocess stdout/stderr pipe，逐行推送"""
    def __init__(self, event_bus: EventBus)
    def attach(process: Popen) -> None      # 启动后台线程读 pipe
    def detach() -> None
```

- 逐行调用 `event_bus.emit("log_line", line)`
- 检测关键词（如 `"server is listening"`、`"error"`、`"CUDA error"`）时额外发事件

### 3.4 ModelResolver

```python
class ModelResolver:
    """搜索 llama-server.exe 路径"""
    def resolve() -> str
    # 优先级：config.yaml 中的路径 > 当前目录 > 同级 ./bin/ > PATH 环境变量
```

- 找不到抛出 `NotFoundError("llama-server.exe 未找到，请在设置中指定路径")`

### 3.5 EventBus

```python
class EventBus:
    """简单发布/订阅，解耦核心层和 UI 层"""
    def on(event: str, callback: Callable) -> None
    def off(event: str, callback: Callable) -> None
    def emit(event: str, **data) -> None
```

- 核心事件：`status_changed`、`log_line`、`error`、`stats_update`
- 回调异常自动捕获，避免一个订阅者挂了影响其他

## 4. 数据流

### 4.1 启动流程

```
用户点击「启动」
  → control_panel 收集参数
  → ProcessSupervisor.start(params)
      → 端口可用性检查
      → Popen 启动子进程
      → emit "status_changed" → "starting"
  → UI 状态灯变黄
  → LogMonitor 检测到 "server is listening"
      → emit "status_changed" → "running"
  → UI 灯变绿，自动打开浏览器（如启用）
```

### 4.2 停止流程

```
用户点击「停止」
  → ProcessSupervisor.stop()
      → psutil.Process(pid).terminate()
      → 等 3 秒，未退出则 .kill()
      → emit "status_changed" → "stopped"
  → UI 灯变灰
```

### 4.3 异常退出检测

```
ProcessSupervisor 轮询（1s 间隔）
  → pid_exists() 返回 False 但状态仍为 running
  → emit "status_changed" → "crashed" + 退出码 + 最后 N 行日志
  → UI 弹错误通知，灯变红
```

## 5. 错误处理

| 错误类型 | 核心层行为 | UI 层行为 |
|----------|-----------|----------|
| 端口被占用 | 启动前 socket 探测，抛 `PortInUseError(port)` | 提示用户换端口 |
| llama-server 找不到 | `ModelResolver.resolve()` 抛 `NotFoundError` | 提示用户在设置中指定路径 |
| 进程异常退出 | 轮询检测，抛 `ProcessCrashedError(exit_code, last_logs)` | 弹错误摘要通知 |
| 配置文件损坏 | `ConfigStore.load()` 用默认值重建 | 无感恢复，日志记录 |
| 子进程启动失败 | `Popen` 异常直传（文件权限等） | 中文提示具体原因 |

**原则**：核心层只抛结构化异常对象，不做 UI 格式化。UI 层负责将异常翻译为中文用户提示。

## 6. TUI 布局（Phase 1）

```
┌──────────┬──────────────────────────────────┐
│          │                                  │
│  控制面板  │           日志面板                │
│  (左侧)   │           (右侧)                 │
│          │                                  │
│  [模型选择]│   [2026-05-22 12:00:01] 启动...  │
│  [mmproj] │   [12:00:03] 加载模型中...       │
│  ──────── │   [12:00:15] 模型加载完成         │
│  -c 4096  │   [12:00:15] server is listening│
│  --ngl 99 │                                  │
│  -np 4    │                                  │
│  --port   │                                  │
│  --host   │                                  │
│  ──────── │                                  │
│  ● 运行中  │                                  │
│  [启动][停止]│                                 │
│          │                                  │
└──────────┴──────────────────────────────────┘
```

- 控制面板宽度固定（~35%），日志面板自动填充剩余空间
- 状态指示灯：● 绿色(运行中) / ● 灰色(已停止) / ● 黄色(启动中) / ● 红色(崩溃)

## 7. 测试策略

### 核心层自动化测试（pytest）

| 测试文件 | 覆盖内容 |
|----------|---------|
| `test_config.py` | YAML 读写、文件不存在造默认值、损坏文件恢复 |
| `test_process_manager.py` | mock psutil 验证启停逻辑、命令行拼装、超时强杀 |
| `test_model_resolver.py` | 路径优先级、搜索逻辑、未找到异常 |
| `test_events.py` | 订阅/发布/取消订阅、回调异常隔离 |

### UI 层

- Phase 1：Textual 手动走查验证
- Phase 2：换 GUI 后补 Playwright 或 pytest-qt

## 8. 依赖

```
textual>=0.40.0    # TUI 框架（Phase 1）
psutil>=5.9.0      # 进程管理
pyyaml>=6.0        # 配置文件解析
pytest>=8.0.0      # 测试（开发依赖）
```

## 9. 设计决定汇总

| 维度 | 决定 |
|------|------|
| 架构 | 三层分离（核心层 → EventBus → UI 层） |
| llama.cpp 来源 | 用户自备，启动器负责定位 |
| 配置文件 | YAML，便携式（应用同目录） |
| 进程检测 | PID 跟踪（psutil） |
| TUI 布局 | 左右分栏 |
| 模型浏览 | 默认打开上次使用目录 |
| 错误处理 | 核心层抛异常 → EventBus → UI 翻译中文 |
| 测试 | pytest 测核心层，UI 手动验证 |
| 语言 | 代码注释用中文 |
