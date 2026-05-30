---
name: tech_stack
description: 语言、框架、依赖版本、运行环境
metadata:
  type: project
---

# 技术栈

## 语言
- Python 3.14（项目用 `X | Y` 联合类型语法，≥3.10 均可）

## 核心依赖
- **PySide6** >= 6.5 — 桌面 GUI 框架（第四阶段替换 Textual）
- **psutil** >= 5.9.0 — 系统/进程监控
- **pyyaml** >= 6.0 — YAML 配置文件解析
- **pytest** >= 8.0.0 — 测试框架

## 标准库用法
- `urllib.request` — HTTP 下载和聊天 API（不用 requests）
- `ssl` — 跳过证书验证时创建自定义 context（`_make_ssl_ctx`）
- `threading` — HFDownloader 后台线程
- `PySide6.QtCore.QThread` — UI 关联的后台任务（监控、聊天）
- `PySide6.QtGui.QDesktopServices` — 启动后自动打开浏览器
- `winreg` — 开机自启注册表读写
- `atexit` — 程序退出时强杀 llama-server 子进程

## 外部工具
- **llama.cpp** — LLM 推理后端；项目管理 llama-server 进程
- **nvidia-smi** — GPU 利用率 / 显存查询（可选，不可用时静默跳过）
- **GGUF** — 模型文件格式，`model_library.py` 解析 metadata 提取架构/参数量/上下文长度/量化类型
- **Nuitka** >= 4.1 — 编译为原生 exe（`--standalone --zig`），替代 PyInstaller（Python 3.14 不兼容）
  - 编译器：`ziglang` pip 包提供 zig.exe，需手动加入 PATH：`$env:PATH = "C:\Python314\Lib\site-packages\ziglang;$env:PATH"`
  - 打包命令：`python -m nuitka --zig --standalone --windows-console-mode=disable --enable-plugin=pyside6 --include-data-dir=assets=assets --include-data-file=config.yaml=config.yaml --windows-icon-from-ico=assets/icon.ico --output-dir=dist --output-filename=llm-launcher.exe main.py`
  - 产物目录：`dist/main.dist/`，分发整个目录

## 配置格式
- `config.yaml` — YAML，顶级键：model / server / app / presets
- `ConfigStore.get(key)` 返回 None（无 default 参数），调用方用 `or` 兜底
- `get_model_preset` / `save_model_preset` 按模型名存取预设
- `app.auto_open_browser` 控制启动后是否自动打开浏览器

## 运行环境
- Windows 主目标平台（winreg / nvidia-smi / Nuitka）
- 需本地安装 llama.cpp，在 UI 中选择其目录（ModelResolver 自动找 exe）

## QSS 主题
- `assets/theme_light.qss` — 极简白底主题，强调色蓝 #2d7dd2 / 绿 #1a9e6e
- 字体：DM Sans（UI）+ DM Mono（数值/日志/输入框）
