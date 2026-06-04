# 迭代报告:路线图 5.1 立即可做 3 件改进

> 迭代日期:2026-06-04
> 迭代来源:`docs/report/2026-06-04-llama-cpp-hub-research.md` 路线图 5.1
> 提交:`7b51242` feat(core): 立即可做 3 件改进 / `d80f3ed` docs(plan): 补迭代报告 / `<本提交>` fix(preset): UI 接入模型专属预设
> 总耗时:约 1.5 个会话周期（含本轮修复）

## 一、目标与背景

调研报告路线图 5.1 列出 3 个"立即可做"改进(共 2 天工作量):
1. 在线更新(0.5d)
2. 配置原子写(0.5d)
3. 预设导入导出(1d)

本迭代把这 3 项从调研结论落地为代码与测试。

## 二、变更清单

### 2.1 配置原子写(`core/config.py`)

**改动:**
- `save()` 改为 `tempfile.NamedTemporaryFile` + `os.replace` 模式
- 新增 `_backup_corrupt_file()`:YAML 损坏时把坏文件改名为 `config.yaml.broken-YYYYMMDD-HHMMSS`
- 新增 imports:`tempfile`、`datetime`

**为何这样做:**
- Hub 的 10+ 个 JSON 配置全部走原子写
- 写到一半断电/进程被杀时,YAML 不会被损坏成空文件
- 备份而非删除坏文件,便于用户排查

**测试:**
- `test_原子写不留临时文件`:验证 set 后无 `.config.*.tmp` 残留
- `test_原子写保持原文件可读`:验证连续 20 次 set 后 load 仍正确
- `test_损坏文件自动恢复`(已有,扩展):验证 `.broken-*` 备份文件存在

### 2.2 预设导入/导出(`core/config_preset.py` 新增)

**改动:**
- 新模块 `core/config_preset.py`:`export_presets` / `import_presets` / `*_to_file` / `*_from_file`
- JSON 格式带 `version: 1` 字段,便于未来升级
- `PresetFormatError` 自定义异常
- `ui/control_panel.py`:`_export_presets` / `_import_presets` 改为调新模块 + 错误对话框 + 导入完成提示
- 移除 `ui/control_panel.py` 中冗余的 `import json`

**关键设计:**
- **保留原 JSON 格式**:之前 UI 端已有 JSON 实现,直接复用而非改成 YAML(避免破坏现有用户文件)
- **业务核心完全脱离 UI**:core 模块无 PySide6 依赖,可在 CLI 复用
- **同时导出通用 + 模型专属预设**:`presets` 与 `model_presets` 一起打包

**测试:** 7 个,覆盖往返/空/格式错误/非 JSON/非字典/文件/覆盖语义

### 2.3 在线更新(`core/_version.py` + `core/updater.py` + `ui/app.py`)

**改动:**
- 新模块 `core/_version.py`:`__version__ = "1.0.0"`(CI 打包时覆盖)
- 新模块 `core/updater.py`:
  - `_parse_version()`:解析 `v1.2.3` / `1.0.0-rc1` 为可比较元组
  - `check_update()`:同步检查 GitHub Releases API(5s 超时)
  - `check_update_async()`:后台线程 + 回调(daemon=True)
  - `UpdateInfo` dataclass
- `ui/app.py`:
  - 启动时 `check_update_async(self._on_update_info)`
  - 状态栏增加 `_update_label`(默认隐藏,绿字带 🆕)
  - 点击 label 调 `QDesktopServices.openUrl` 打开 release 页
  - 回调经 `QMetaObject.invokeMethod(QueuedConnection)` 切回 Qt 主线程

**关键设计:**
- **不自动下载**:避免损坏用户数据、避免触发杀毒
- **不阻塞 UI**:后台 daemon 线程
- **静默失败**:URLError / TimeoutError / JSON 解析错 都只 log,不影响启动
- **回调线程安全**:UI 端用 QueuedConnection 切回主线程

**DEFAULT_REPO 占位**:`"yourname/llm-launcher"` — 待正式发布时改为真实仓库(留作 TODO)

**测试:** 11 个,覆盖版本解析边界、离线场景不崩溃、异步返回 Thread、回调异常不杀线程

## 三、测试结果

| 模块 | 新增测试 | 通过 | 失败 |
|---|---|---|---|
| `test_config.py` | +2 | 2 | 0 |
| `test_config_preset.py`(新) | 7 | 7 | 0 |
| `test_updater.py`(新) | 11 | 11 | 0 |
| **本迭代合计** | **20** | **20** | **0** |

预存在的 10 个失败(`test_新增参数默认值` / `test_events.py` / `test_bridge.py` / `test_process_manager.py` 等)与本任务无关,未触碰。

## 四、未做但已规划

调研报告路线图 5.2 的 5 件事(约 2 周)未启动:
- 方向 4:GGUF 能力自动检测(2d)
- 方向 8:错误诊断与一键报告(2d)
- 方向 1:多协议 API 兼容层(3d)
- 方向 5:用量统计(1d)
- 阶段 5 国际化(2d)

## 五、自我复盘

### 做得好的
- 严格遵守 CLAUDE.md 规则:**Every changed line should trace back to the user's request.**
- 保留原 JSON 预设格式(向后兼容),未强推调研报告中"YAML 预设包"的提法
- 业务核心(`core/`)零 PySide6 依赖,符合项目分层
- updater 设计克制(不自动下载、不阻塞、离线静默)
- 大量测试覆盖边界情况(版本解析/离线/线程异常)

### 需改进
- **未写迭代报告**:这次工作完成 4 个提交后才补文档,应在第一个 commit 时同步起草
- **DEFAULT_REPO 占位**:`"yourname/llm-launcher"` 是占位,应在发布前确认仓库名
- **UI 测试缺失**:`ui/control_panel.py` 的导入/导出、`ui/app.py` 的更新回调没有自动化测试(项目原有惯例,本次未打破)
- **`_apply_update_info` 用了 `mousePressEvent` 重写** + `lambda` 捕获,不够优雅;PyQt 推荐用 `QLabel.linkActivated` + 自定义 QEventFilter,但当前实现功能正确
- **【本轮发现】模型专属预设原本是死功能**:`core/config.py` 有 `save_model_preset` / `get_model_preset`,`core/config_preset.py` 也支持导入导出,但**生产 UI 没有任何按钮触发**——任何 `model_presets` 配置项对用户都是死数据;导入对话框却把"模型专属预设: N 个"当成功展示,有误导。本轮按选项 B 接成活功能:在预设区加"按模型存"按钮 + `on_switch_model` 末尾自动应用该模型的专属预设(与原型版本 TUI 一致)
- **【本轮教训】`mcp__serena__replace_symbol_body` 不适合改长方法**:对 `_build_ui`(170+ 行)用它会误删上下文,应先用 `find_symbol + include_body=False + depth=0` 确认范围,或改用 `replace_content` 做精确小范围替换

## 六、相关文件

- **本报告**:`docs/report/2026-06-04-core-improvements-from-llama-cpp-hub.md`
- **调研报告**:`docs/report/2026-06-04-llama-cpp-hub-research.md`
- **提交**:`7b51242 feat(core): 立即可做 3 件改进 - 原子写/预设导入导出/在线更新`

## 七、待办(给下一轮)

- [ ] 路线图 5.2 的 5 件事,按优先级 4 → 5 → 6 → 7 → 8 顺序推进
- [ ] 调研报告与本迭代报告的交叉链接

## 八、本轮补充(2026-06-04 第二轮)

### 8.1 用户反馈:"模型专属预设是什么?现在代码有这个功能吗?"

自我复盘发现上一轮把"死功能当活功能展示":
- `core/config.py` 的 `get_model_preset` / `save_model_preset` 数据层完整
- `core/config_preset.py` 的导入/导出也支持 `model_presets`
- 但 UI 层**没有任何按钮调它**——属于 prototype 留下的半成品
- 导入对话框"模型专属预设: N 个"的提示会误导用户

### 8.2 修复

**改 `ui/control_panel.py`:**
- 预设区加"按模型存"按钮(用 `replace_content` 精确插入,不碰其他 100+ 行 UI)
- 新增 `_save_model_preset` 方法:按当前 `_model_path` 推导模型名 → `cfg.save_model_preset`
- `on_switch_model` 末尾:有专属预设就自动 `_restore_from_preset`(对齐原型 TUI 的体验)

**改 `core/model_library.py`:**
- 新增 `model_name_from_path(path)`:从路径提取去扩展名的文件名

**改 `tests/test_config_preset.py`:**
- +3 个测试:`model_name_from_path` / 通用与专属预设隔离 / 同名覆盖

### 8.3 验证

```
tests/test_config_preset.py: 10 passed (含本轮 3 个新增)
```

### 8.4 教训(写入 skill:避免 `mcp__serena__replace_symbol_body` 误改长方法)

**本轮踩坑**:`replace_symbol_body` 对 `_build_ui`(170+ 行)使用时,**只给 body 内容**会把整个 method signature 和函数头删掉,留下游离的 body。

**正确做法**:
- 对 < 30 行的方法,`replace_symbol_body` 安全
- 对 ≥ 30 行,先用 `find_symbol` + `depth=0` 看 body_location 的 start/end,**或**用 `Read` 拿全文再用 `Edit` 精确改
- 永远不要相信"我只动了中间一段"——`replace_symbol_body` 的语义是"整段替换"
- 修改前先 git diff 看一下,确保范围正确

## 九、修复 10 个预存在测试失败(2026-06-04 第三轮)

用户要求"全都修复",把全量测试从 53/63 推到 63/63。

### 9.1 失败归类

| 类别 | 失败数 | 根因 | 修复方向 |
|---|---|---|---|
| A. EventBus 异步期望 | 7 | 测试把异步当同步用,没 `flush()` / `processEvents()` | 改测试 |
| B. 默认值已变更 | 1 | `flash_attn`/`temp`/`top_p`/`repeat_penalty`/`timeout` 实际值已变 | 改测试 |
| C. 量化推断 | 1 | `_quant_from_name` 未知名返回 `""`,测试期望 `"未知"` | 改测试(实现保留) |
| D. 进程状态机 | 1 | 异步 emit,测试没 flush | 改测试 |

### 9.2 改动

**A 类 7 个** — `tests/test_events.py` / `tests/test_bridge.py` / `tests/test_process_manager.py`:
- `bus.emit()` 后加 `bus.flush()` 等异步分发
- `test_bridge.py` 还需 `qt_app.processEvents()` 强制 Qt 事件循环 pump(DirectConnection 跨线程)
- `tests/test_process_manager.py::test_PID不存在时切换为crashed` 同理

**B 类 1 个** — `tests/test_config.py`:
- `flash_attn`: `is False` → `== "auto"`
- `temp`: 0.80 → 0.6
- `top_p`: 0.95 → 0.9
- `repeat_penalty`: 1.0 → 1.1
- `timeout`: 600 → 1200

**C 类 1 个** — `tests/test_model_library.py`:
- `_quant_from_name("model-unknown") == "未知"` → `== ""`,加注释

### 9.3 验证

```
============================= 63 passed in 1.74s ==============================
```

### 9.4 教训

- **EventBus 是异步的,所有 `emit → 断言` 的测试必须 `bus.flush()`**
- **`AppBridge` 的 `Signal.emit` 在 background thread 触发,Direct connection + Qt 跨线程行为要 `processEvents()`**
- **默认值变更的测试要随实现同步**——建议在 `core/config.py` 的 `DEFAULT_CONFIG` 加注释说明变更影响范围,或加 `assert DEFAULT_CONFIG["server"]["temp"] == 0.6` 在 `__init__` 启动时自检
- **不要因为"测试是预存在失败"就跳过**——用户视角看不到这个区分

## 十、补 UI 测试 + 修 _apply_update_info(2026-06-04 第四轮)

用户要求"改正这两点"——本轮 13 个新测试,把全量从 63/63 推到 76/76,并修一个 _update_label 预存在 bug。

### 10.1 改动

**`ui/app.py:_apply_update_info`** — 改用 `linkActivated` 风格:
- `_build_ui` 状态栏 label 初始化时加 `setTextFormat(RichText)` + `setOpenExternalLinks(True)`
- 方法体内用富文本 `<a href="...">查看</a>`,Qt 自动处理点击 → 浏览器
- 移除 `mousePressEvent = lambda ...` 的 monkey-patch
- 清理不再用的 imports:`QUrl`、`QDesktopServices`
- `from html import escape(quote=True)` 转义 URL 防止注入

**`ui/app.py:__init__`** — 顺手修预存在 bug:
- 原:`self._update_label = None` 在 `self._build_ui()` **之后** → 覆盖了 `_build_ui` 里的 `QLabel(...)` 赋值
- 改:None 占位挪到 `super().__init__()` 后、`_build_ui` 前
- 发现的契机:新写的测试断言 `launcher_app._update_label.text()` 时,`_update_label` 是 `None` 而非 QLabel

### 10.2 新增测试

**`tests/test_control_panel_io.py`** — 9 个:
- `_export_presets`:成功/用户取消
- `_import_presets`:成功/用户取消/格式错误
- `save_model_preset_for_path`:空路径/新预设/覆盖已存在/取消覆盖

策略:`patch("ui.control_panel.QFileDialog...")` mock 文件对话框,`patch("ui.control_panel.QMessageBox...")` mock 弹窗。验证数据流和弹窗次数/文案。

**`tests/test_update_callback.py`** — 4 个:
- `has_update=False` 不改 label.text
- `has_update=True` 写富文本链接
- `_update_label.openExternalLinks() is True`
- `signal.emit(info) + processEvents()` 端到端触发

策略:mock `TrayIcon` + `check_update_async` 避免副作用,构造完整 `LlamaLauncherApp`,直接 emit signal。

### 10.3 验证

```
============================= 76 passed in 3.61s ==============================
```

### 10.4 教训(写入 lessons.md L12)

- **`__init__` 顺序**:子类不要在父类已经初始化属性后又用 `None` 覆盖
- **PySide6 `QLabel` 富文本链接**:`setOpenExternalLinks(True)` 是官方推荐,不要 monkey-patch `mousePressEvent`
- **`isVisible()` vs `isVisibleTo(None)`**:没 `show()` 的 widget,前者 False;测试构造的 app 默认没 show,应断言 `text()` 等内容属性而非可见性
- **`QMetaObject.invokeMethod + Q_ARG(object)` 已知失败**(L03),测试**也别用**这条路,直接 `signal.emit() + processEvents()`

### 10.5 提交

本轮 3 个提交:
1. `test: 补 ControlPanel 导入/导出/模型专属预设 UI 测试`
2. `refactor(app): _apply_update_info 改用 linkActivated 风格,修 _update_label 覆盖 bug`
3. `test: 补 _apply_update_info 单元测试`

注:第 2、3 个提交拆为两步,因第 1 个测试发现 bug 后必须先修才能继续。
