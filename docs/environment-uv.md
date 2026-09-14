# uv 环境管理与迁移记录

## 日常使用

安装用户级 uv 后，在项目根目录执行 `uv sync --locked`。uv 根据
`.python-version` 下载托管 Python，在 `.venv` 中安装依赖；不使用系统 Python。
`pyproject.toml` 是依赖声明的唯一来源，`uv.lock` 记录解析结果。

- 启动：`uv run --locked main.py` 或双击 `start.cmd`。
- 测试：`uv run --locked python -m pytest`。
- 构建：`uv run --locked --group build python scripts/build.py` 或双击 `C编译.bat`。
- 独立构建验证：`uv run --locked --group build python scripts/build.py --output-dir dist/uv-verify`。
- 依赖检查：`uv lock --check` 和 `uv pip check`。
- 重建：关闭本项目程序后删除项目 `.venv`，再运行 `uv sync --locked`，不用复制环境目录。
- 导出：`uv export --locked --no-dev --format requirements.txt --output-file requirements.txt`。

运行和测试使用默认依赖组；Nuitka、Zig 在 `build` 组，按需安装。
双击脚本优先使用 PATH 中的 uv，再检查用户默认目录 `.local/bin/uv.exe`。
缺失 uv 或锁文件不一致时显示错误，不调用全局 Python。

Python 最低兼容声明仍为 3.10；本次开发与构建验收仅针对 Windows x64、固定的
Python 3.14.7，不代表对全部声明版本做过测试。

## 2026-09-14 迁移记录

- 从全局 Python + pip 改为 uv 托管解释器、项目虚拟环境和锁文件。
- 保留应用版本 1.3.0 以及现有运行依赖的最低版本要求。
- 首次解析优先沿用原环境的 psutil 7.2.2、PyYAML 6.0.3、PySide6 6.11.1、
  pytest 9.0.3、Nuitka 4.1.1、ziglang 0.16.0；其他依赖按约束解析。
- 原全局环境未检测到 requests、huggingface-hub 的安装元数据。
- 编译器位置由项目环境中的 ziglang 确定，构建以同一解释器调用 Nuitka。
- 删除手工维护的 requirements.txt，保留按需导出命令。
- 不改动业务功能，不清理全局包，不发布、不提交 Git。

## 人工验收

自动验证完成后，请双击 `start.cmd`，确认窗口、配置和模型列表显示正常；
使用现有模型启动 llama-server，验证停止/重启和聊天收发；再启动独立构建目录中的
`llm-launcher.exe` 验证主要功能。人工确认后再决定是否提交。

## 自动验证结果

- uv：0.12.13，用户工具目录为 `C:\Users\PC\.local\bin`，已加入用户 PATH；已打开的终端需要重新打开才会继承更新。
- Python：3.14.7；项目解释器为 `.venv\Scripts\python.exe`，基础解释器为
  `C:\Users\PC\AppData\Roaming\uv\python\cpython-3.14.7-windows-x86_64-none`。
- `site.ENABLE_USER_SITE=False`；运行依赖均来自项目 `.venv`，隔离断言全部通过。
- `uv lock --check`、项目环境和重建环境的 `uv pip check` 均通过。
- 完整测试：`uv run --locked python -m pytest -q`，**119 passed in 12.75s**。
  最初系统临时目录 `pytest-of-PC` 权限异常，已在项目 pytest 配置中指定
  `.pytest_cache/tmp`，不修改系统临时目录权限。
- 干净重建：在 `%TEMP%\llm-launcher-uv-repro-3147-20260914` 中执行
  `uv sync --locked --group build`，安装 30 个包，逐项比较版本与项目环境完全一致。
  重建使用了本次下载生成的 uv 缓存；不等同于第二次全网下载。
- GUI：临时配置、离屏平台初始化主窗口，截图 `dist/uv-source-smoke.png`；
  显式加载系统中文字体并在验证脚本退出前关闭监控线程，退出码为 0。
  这是初始化和渲染检查，不替代真实模型、聊天和桌面交互验收。
- 构建：Nuitka 4.1.1 / 项目内 Zig 0.16.0 成功生成
  `dist/uv-verify/main.dist/llm-launcher.exe`；没有升级这两个既有工具版本。
  Nuitka 对 Python 3.14 仍输出实验性支持提示，本次成功不代表覆盖所有构建场景。
- EXE：隐藏启动后 GUI 消息循环就绪，继续观察 12 秒未退出，崩溃日志为空。
  隐藏启动未返回可见主窗口句柄，因此没有将其记为桌面视觉验收；验证进程已结束。
- 产物：70 个构建文件，约 87.2 MB；运行冒烟后额外生成空的 `crash.log`。
  构建前检查没有携带开发用 `config.yaml`。
- EXE SHA-256：`E9E0C332D822C2B588ED1A7A5588BE09A2EAB17A099856C70A732C89765C9AC6`。
- pip 导出命令验证通过，导出文件写入临时目录，未恢复第二份手工依赖清单。

## 本机迁移排查

已有 uv 较旧且未在当前 PATH 中，通过官方 PyPI wheel 更新用户级 uv/uvx；
被占用的旧可执行文件保留为同目录 `.llm-launcher-backup-20260914` 备份，没有停止其他用户进程。
下载期间正常 PowerShell 会话自动注入代理；按实际源分别检查直连和代理后完成安装。
未把本机代理写入项目配置。最终 Addons 包由 uv 正常同步完成，分段下载尝试未用于安装。


## 2026-09-14 按用户要求清理原全局依赖

迁移完成后，用户另外授权卸载对应全局副本。通过 `C:\Python314\python.exe -m pip uninstall` 移除以下 9 个包，目标均位于 `C:\Python314\Lib\site-packages`：

- psutil 7.2.2、PyYAML 6.0.3、pytest 9.0.3。
- PySide6 / PySide6_Addons / PySide6_Essentials / shiboken6，均为 6.11.1。
- Nuitka 4.1.1、ziglang 0.16.0。

requests 2.32.5 位于用户级 Python314 目录，被 markitdown、google-genai、azure-core 等其他包直接依赖，予以保留；全局未找到 huggingface-hub。没有连带删除通用间接依赖。卸载前确认目标包不存在清单外的必需依赖者，附加功能（extras）的声明不当作默认依赖。

全局目录 ACL 仅允许管理员修改，普通卸载失败后通过 Windows UAC 执行相同的 pip 卸载命令，未修改 ACL。前后包清单比较确认只移除了指定 9 个包；全局 `pip check` 与项目 `uv pip check` 均通过。项目 `.venv` 中的 30 个包保留。卸载清单、前后快照和日志保存在 `C:\Users\PC\.codex\backups\llm-launcher-global-cleanup-20260914-175357`。

卸载后的项目完整回归测试：119 passed in 16.33s；未提交 Git。


## 2026-09-14 v1.3.1 发布验收

用户已授权提交、推送及发布。内置版本与 pyproject 版本同步为 1.3.1，uv.lock 仅更新项目版本；119 项测试通过（16.27 秒），新版本使用项目环境重新构建。原 `dist/main.dist` 已备份至 `D:\Myprogram\llm-launcher\dist\main.dist-before-v1.3.1-20260914-180216`，更新该目录中的程序文件并保留本机配置。

从指定目录按新构建清单打包 `llm-launcher-v1.3.1-windows-x64.zip`，ZIP 根目录可直接找到 EXE，共 69 个文件、33,166,257 字节；不含 config.yaml、crash.log、模型缓存或个人配置。已检查 ZIP CRC、逐文件内容哈希及解压后 EXE 哈希，解压程序隐藏启动后消息循环就绪，继续观察 10 秒未退出且崩溃日志为空。

- ZIP SHA-256：`6cbd7e735b80e2ca41022e322a958104affa14819aae3e0db764bd0496c6fb88`
- EXE SHA-256：`6852e04dc32aacc3e49ef7547b6f4824fd61b6da60fc0921c8a0afc57c9be0a8`
- 发布地址：https://github.com/Narcissu-s1/llm-launcher/releases/tag/v1.3.1
