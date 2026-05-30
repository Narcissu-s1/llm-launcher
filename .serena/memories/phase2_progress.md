---
name: phase2_progress
description: 各阶段实现进度与关键实现细节（已更新至第四阶段后续迭代）
metadata:
  type: project
---

# 实现进度

## 总体状态

| 阶段 | 状态 |
|------|------|
| 1 — 核心启动控制 MVP | ✅ 完成 |
| 2 — 高级参数与运行时监控 | ✅ 完成 |
| 3 — 多模型管理与下载 | ✅ 完成（托盘已做，崩溃重启未做） |
| 4 — PySide6 GUI 重构 | ✅ 完成 |
| 5 — 用户体验优化 | ❌ 未开始（细节迭代中） |

## 第四阶段后续迭代（已完成）

### 启动面板改进
- 上下文长度选项：切换模型时从 GGUF metadata `{arch}.context_length` 读取上限，动态生成 2 幂次下拉选项
- GPU 层数：范围改为 `-1 ~ block_count`（从 `{arch}.block_count` 读取），`-1` 为默认值（全部 GPU），SpinBox 显示 "全部（-1）"，tooltip 显示实际层数
- 监听地址：下拉改为 `addItem(显示文字, 真实IP)`，collect_params 用 `currentData()` 取值
- 状态指示：`_status_label` 随 `_on_status_changed` 同步变色（绿/灰/黄/红）+ font-weight:bold
- 切换模型时自动清空/检测 mmproj（`find_mmproj`），避免残留旧路径导致不匹配错误

### 模型库缓存
- 扫描结果缓存到 `model_cache.json`（与 config.yaml 同目录）
- 缓存 key：`path|mtime|size`，命中则跳过 `_parse_gguf`，只解析有变化的文件
- 打开面板/切换目录时加载缓存（`_load_from_cache`），点"扫描"才更新

### 运行时监控改进
- `_StatCard` 加副标题行（`_sub`）：CPU 显示进程级 CPU%，RAM 显示进程 RSS
- 进度条高度 5px，<80% 绿色，≥80% 红色，带圆角

### 聊天面板
- 附图按钮：选择图片→base64 编码→拼多模态 content 数组发送
- 发图前检查 mmproj：读 config → find_mmproj 自动检测 → 都失败则弹 QMessageBox 阻止发送
- 停止按钮：`_ChatWorker._stopped` 标志位，`stop()` 方法；发送时"发送"禁用，完成/出错后恢复
- 附图标签显示已选文件名，发送后清空

### 日志改进
- 启动时 `process_manager.start()` 将完整命令逐参数输出（`>>> 启动命令:` + 缩进行）
- `log_panel.add_line`：`>>>` 前缀/缩进行蓝色 `#4a9eff`，补充 `llm loaded`/`model loaded` 绿色关键词

### 模型下载重构
- 选中列改为居中 QCheckBox（`QWidget` 包裹），移除文字 ☐/☑
- 所有跨线程回调通过 4 个 Signal 转发：`_sig_scan_done/_sig_progress/_sig_done/_sig_log`
- `scan()` 的 `on_done` 也走 `_sig_scan_done`（原来直接调用 `_on_scan_done` 会在后台线程创建 QWidget 导致崩溃）
- `_download_file` 检测 HTTP 206 vs 200 并在日志告知用户断点续传支持情况

### 高级参数默认行为
- `_CollapsibleGroup` 默认 `setChecked(False)`：折叠且 Qt 自动 disable 所有子控件，防误操作
- `collect_params` 未勾选返回 `{}`，不注入命令行，走 llama.cpp 内置默认值
- `restore_params` 检测 dict 非空时自动 `setChecked(True)` 展开（预设载入时生效）

### 托盘图标
- 新增 `starting` 黄色图标（`#d69e2e`），`_on_status` 覆盖全部 4 种状态

### 参数指南面板
- `widgets/guide_panel.py`：8 个分组卡片，内容基于需求文档（命令行参数名/默认值/说明均来自文档）
- 最后一个 tab，`tabBar().setExpanding(False)` 紧凑排列，QSS `::tab:last` 灰色系视觉区分

## 关键实现细节

### 布局（ui/app.py）
- 左：ControlPanel 固定 400px
- 右：QSplitter 垂直，上 QTabWidget（日志/模型库/下载/聊天/参数指南）占 70%，下 MonitorPanel 占 30%
- 左侧 3px 状态线颜色跟随服务状态（绿/灰/黄/红）

### 线程安全原则
- EventBus handler 可能在后台线程触发 → AppBridge 用 Qt Signal 自动切换主线程
- `_ChatWorker`、`_MonitorWorker` 均为 QThread 子类，不可在其中直接操作 UI
- 下载/扫描回调必须通过 Signal，不可直接调用槽方法（否则报 QObject::setParent 跨线程错误）

### 进程管理（core/process_manager.py）
- ProcessSupervisor.stop() 是同步的（SIGTERM → wait → SIGKILL）
- closeEvent 等待 pid=None 最多 5s，确保端口释放再退出
- atexit 注册 _force_kill_on_exit，防止任何退出方式留下孤儿进程

### 参数量与模型元数据（core/model_library.py）
- 优先读 `general.size_label`（如 "7.6B"）解析为整数
- 兜底读 `{arch}.parameter_count` / `general.parameter_count` metadata key
- `context_length`：读 `{arch}.context_length`，兜底 `llama.context_length`
- `block_count`：读 `{arch}.block_count`

### collect_params（ui/control_panel.py）
- 过滤所有 None 值，防止 str(None) 进入命令行导致崩溃
- 键名映射：_REMAP 将 param_groups 键名转换为 process_manager 期望键名
- host 用 `currentData()` 取真实 IP（显示文字含中文说明）
- 启动成功后 emit `started(params)`，同步写 server.port 到 config

### 聊天面板（ui/widgets/chat_panel.py）
- `_ChatWorker` 从流式响应末尾 chunk 的 `timings` 字段提取统计
- 统计栏显示：首字延迟 / Prompt tokens+速度 / 生成 tokens+速度
- 顶部模型信息栏：启动时由 app.py 连接 control.started → chat.update_model_info
- `_stopped` 标志位在流式循环每次迭代检查，stop() 设置后当前 chunk 处理完即退出

### 下载器（core/hf_downloader.py）
- 回调式 API（非阻塞），scan/start 均自启线程
- on_progress 接收 DownloadTask 对象（含 filename/downloaded/total/status）
- cancel() 设置 _cancel Event，下载线程自行检测退出
- 断点续传：发 Range 头后检查响应码，206 = 支持（追加写），200 = 不支持（重头写）

## 打包（Nuitka）
- PyInstaller 不兼容 Python 3.14，改用 Nuitka 4.1 + ziglang（zig 编译器）
- `subprocess.Popen` / `check_output` 均需加 `creationflags=CREATE_NO_WINDOW`，否则 Windows GUI 下每次调用弹 cmd 窗口
  - 已修：`core/process_manager.py`（llama-server 启动）、`ui/widgets/monitor_panel.py`（nvidia-smi 每秒调用）
- 路径定位：用 `os.path.dirname(os.path.abspath(sys.argv[0]))` 获取 exe/脚本所在目录（Nuitka 不设 `sys.frozen`，PyInstaller 的判断无效）
  - 已修：`main.py`（QSS 路径）、`ui/app.py`（config.yaml 路径）
- `crash.log` 写到 exe 同目录，启动崩溃时可查看
- 打包命令见 `mem:tech_stack`

## 最新迭代（2025-05-30）

### 启动后自动打开浏览器
- `main.py` 中 `_start_server` 成功后调用 `QDesktopServices.openUrl(url)`
- 需在 config.yaml 中配置 `app.auto_open_browser: true`（默认开启）

### 模型参数显示
- 控制面板启动后在 `_on_status_changed(RUNNING)` 时读取当前模型的 GGUF metadata
- 显示：架构、参数量、上下文长度、量化类型等信息
- 通过 `model_library._parse_gguf` 提取元数据

### 聊天统计信息
- `_ChatWorker` 从流式响应末尾 chunk 的 `timings` 字段提取统计数据
- 统计栏显示：首字延迟（tokens_per_second 的倒数）、Prompt tokens + 速度、生成 tokens + 速度
- `_on_timings` 方法格式化并显示在聊天面板底部

### config.yaml 精简
- 移除了冗余的默认值配置，只保留用户实际需要修改的项
- 新增 `app.auto_open_browser` 配置项

### SpeculativeParams 新增
- `param_groups.py` 新增第 7 组参数：SpeculativeParams（推测解码）
- 包含：`--draft`（draft 模型路径）、`--draft-max`（最大 draft token 数）、`--draft-p-min`（最小概率阈值）

### 异常类完善
- `process_manager.py` 新增 `ProcessError` 基类和 `PortInUseError` 子类
- 端口占用时抛出专门异常，UI 层可捕获并显示中文提示

### EventBus 新增 EVENT_ERROR
- `events.py` 新增 `EVENT_ERROR` 事件常量
- 用于全局错误通知，UI 层可订阅并显示错误弹窗

## 下一步（阶段 5）
- 5.1 首次使用引导（检测 llama.cpp、3 步引导）
- 5.2 错误诊断（常见错误中文提示、一键复制诊断）
- 5.3 国际化（中英切换、字体大小可调）
