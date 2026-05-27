# 项目核心

## 概述
llm-launcher 是一个用于启动和管理本地 LLM 模型的 TUI 应用，基于 llama.cpp 后端。
当前为 TUI 阶段（Textual），计划第五阶段重构为正式 GUI（PyQt6/PySide6/wxPython）。

## 源代码地图

### core/（业务逻辑，不依赖 ui）
- `config.py` — YAML 配置管理（ConfigStore），含预设 get/save/delete
- `events.py` — 事件总线（EventBus），定义事件常量
- `process_manager.py` — llama-server 进程管理（ProcessSupervisor）
- `model_resolver.py` — 解析 llama-server 可执行文件路径
- `log_watcher.py` — 监控进程日志输出
- `model_library.py` — 扫描目录 GGUF 文件，解析元数据（ModelInfo, scan_directory, format_size）
- `hf_downloader.py` — 模型下载（HFDownloader），支持 HF / HF镜像 / ModelScope，断点续传；`RemoteFile` 表示远程文件，`DownloadTask` 表示下载任务；`scan()` 和 `start()` 分离

### ui/（Textual TUI，依赖 core）
- `app.py` — 主应用类 LlamaLauncherApp，组装布局和事件处理
- `control_panel.py` — 左侧控制面板（模型选择、参数配置、启停按钮、预设管理）；含 `DirPicker`、`PresetNameDialog`、`JsonFileBrowser`
- `log_panel.py` — 右侧日志显示面板
- `confirm_dialog.py` — 通用二次确认弹窗
- `widgets/param_groups.py` — 6 个参数分组 Widget（Collapsible）
- `widgets/monitor_panel.py` — 运行时监控（GPU/RAM/CPU）
- `widgets/model_library_panel.py` — 模型库面板（ModelLibraryPanel），扫描本地 GGUF
- `widgets/download_panel.py` — 远程下载面板（DownloadPanel），两步流程：扫描→勾选→下载
- `widgets/chat_panel.py` — API 测试聊天面板（ChatPanel）

### tests/
- pytest，覆盖 config、process_manager、monitor

## 关键架构决策
- `core` 不依赖 `ui`，GUI 重构时 core 层零改动复用
- EventBus 解耦 UI 和核心逻辑
- ProcessSupervisor 管理 llama-server 子进程生命周期
- 配置持久化到 config.yaml，UI 启动时回填
- 下载器 scan/start 分离，UI 先展示文件列表供用户勾选

## 需求文档
`llm-launcher-需求文档.html`（根目录）— 五个阶段，含进度追踪

技术细节见 `mem:tech_stack`；规范见 `mem:conventions`；阶段二进度见 `mem:phase2_progress`
