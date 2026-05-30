---
name: core
description: 项目顶层源代码地图、架构决策、当前阶段状态
metadata:
  type: project
---

# 项目核心

## 概述
llm-launcher 是一个用于启动和管理本地 LLM 模型的桌面 GUI 应用，基于 llama.cpp 后端。
**当前为第四阶段（PySide6 GUI）已完成**，正在迭代细节 bug 修复与功能增补。

## 源代码地图

### core/（业务逻辑，不依赖 ui）
- `events.py` — 事件总线（EventBus），常量：EVENT_STATUS_CHANGED / EVENT_LOG_LINE / EVENT_ERROR / EVENT_STATS_UPDATE
- `config.py` — YAML 配置管理（ConfigStore），含预设 get/save/delete；`get(key)` 不接受 default，用 `or` 兜底；默认 `n_gpu_layers: -1`（全部 GPU）；`get_model_preset` / `save_model_preset` 按模型名存取预设
- `process_manager.py` — llama-server 进程管理（ProcessSupervisor）；`ProcessStatus` enum（STOPPED/STARTING/RUNNING/CRASHED）；`ProcessError` / `PortInUseError` 异常类；atexit 注册强杀；启动时将完整命令逐参数输出到日志（`>>> 启动命令:` + 蓝色缩进行）
- `model_resolver.py` — 用目录查找 llama-server.exe（ModelResolver），优先 config 指定目录，兜底 PATH
- `log_watcher.py` — 监控进程日志输出
- `model_library.py` — 扫描目录 GGUF 文件（scan_directory + 缓存）；`ModelInfo`（path/name/file_size/quant_type/param_count/architecture/context_length/block_count）；`find_mmproj(model_path)` 同目录自动查找 mmproj；`_parse_gguf` 提取 context_length 和 block_count 用于 UI 动态更新；`format_size` / `format_params` 格式化工具函数
- `hf_downloader.py` — 模型下载（HFDownloader），回调式 API；`RemoteFile` / `DownloadTask` 数据类；`_download_file` 检测 HTTP 206（断点续传）并在日志告知用户；支持 HF/HF镜像/ModelScope；`_make_ssl_ctx` 跳过证书验证

### ui/（PySide6 GUI）
- `app.py` — QMainWindow（LlamaLauncherApp），左控制面板 + 右 QSplitter（上 Tab / 下监控 30%）；右侧 Tab 顺序：日志/模型库/下载/聊天/参数指南；tabBar setExpanding(False) 让参数指南落在最右
- `bridge.py` — AppBridge(QObject)：EventBus 事件 → Qt Signal（status_changed/log_line/stats_update）
- `control_panel.py` — 左侧控制面板；signals: `started(dict)`；监听地址用 addItem(显示, data) 存真实 IP，collect_params 用 currentData()；`on_switch_model` 切换时自动清空/检测 mmproj、调用 `_update_ctx_for_model`；`_update_ctx_for_model` 同时更新 ctx 下拉（按 context_length 生成 2 幂次选项）和 ngl SpinBox 范围（-1 ~ block_count）
- `log_panel.py` — QPlainTextEdit 日志，颜色分级（`>>>` 前缀/缩进行蓝色，error 红，warn 黄，loaded/ready 绿），清空/复制
- `confirm_dialog.py` — QDialog 二次确认弹窗
- `widgets/param_groups.py` — 7 组参数（KVCacheParams/InferenceParams/SamplingParams/ReasoningParams/MultimodalParams/SecurityParams/SpeculativeParams）；基类 `_CollapsibleGroup` 默认 `setChecked(False)`（折叠+禁用），勾选后才传参；`collect_params` 未勾选返回 `{}`；`restore_params` 有值时自动展开；`_safe_int` / `_safe_float` 安全转换工具
- `widgets/monitor_panel.py` — QThread 每秒采集 CPU/RAM/GPU（nvidia-smi），4 张 `_StatCard`；进度条 <80% 绿，≥80% 红；副标题显示进程级 CPU% 和进程 RSS
- `widgets/model_library_panel.py` — 扫描本地 GGUF，5 列表格；扫描结果缓存到 `model_cache.json`（按 path|mtime|size 为 key），打开/切换目录时加载缓存，点"扫描"才重新解析；signal: switch_model
- `widgets/download_panel.py` — HF/HF镜像/ModelScope 下载；选中列为真正的 QCheckBox（居中）；所有跨线程回调均通过 Signal（`_sig_scan_done/_sig_progress/_sig_done/_sig_log`）转发到主线程，避免崩溃
- `widgets/chat_panel.py` — 聊天面板，流式输出；`_ChatWorker` 有 `_stopped` 标志位和 `stop()` 方法；发送时"发送"禁用/"停止"启用，完成/出错后恢复；附图按钮选图后 base64 编码发多模态请求；发图前检查 mmproj（先读 config，再 find_mmproj 自动检测，都找不到则弹警告阻止发送）
- `widgets/tray_icon.py` — QSystemTrayIcon，4 种状态图标（绿/灰/黄/红），双击还原，右键退出
- `widgets/guide_panel.py` — 参数指南面板，8 个分组卡片（含"待实现参数"），内容基于项目需求文档；交替行底色，参数名蓝色等宽字体，默认值灰色小字

### 工具脚本
- `gguf_info.py` — 独立 CLI，提取 GGUF 文件所有 metadata，`python gguf_info.py <file|dir>`

### tests/
- pytest 35 个，覆盖 config/events/process_manager/model_library/bridge/monitor

## 关键架构决策
- `core` 不依赖 `ui`，零改动跨 GUI 框架复用
- EventBus → AppBridge → Qt Signal 保证线程安全 UI 更新
- ProcessSupervisor 用 atexit 注册强杀，防孤儿进程占端口
- 控制面板启动成功后 emit `started(params)` 信号，聊天面板据此更新模型信息栏
- config.yaml 中 server.port 在每次启动时同步写入，聊天面板读到正确端口
- 所有后台线程（下载/扫描）回调 UI 必须通过 Qt Signal，不可直接操作 QWidget

## 进度总览
阶段 1-4 已完成，持续迭代细节；阶段 5 待做（首次引导/错误诊断/国际化）
详细进度见 `mem:phase2_progress`；技术细节见 `mem:tech_stack`；规范见 `mem:conventions`
