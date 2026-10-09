# 经验教训库(Lessons Learned)

> 维护目的:沉淀本项目实践中踩过的坑,避免重蹈覆辙。
> 每条经验包含:场景、错误信号、根因、正确做法、可复制的检测命令。
> 来源标注对应提交/迭代报告。

---

## 索引

| # | 教训 | 来源 |
|---|---|---|
| L01 | [MCP `replace_symbol_body` 改长方法会误删函数头](#l01) | `6f6b944` |
| L02 | [`python -c "import ast; ast.parse()"` 只查语法不查名字解析](#l02) | `8f4326c` |
| L03 | [`Q_ARG(object, ...)` 不是合法 QMetaType,Qt meta-system 无法 marshal Python 对象](#l03) | `ac755e2` |
| L04 | [EventBus 异步,测试 emit→断言 必须 `bus.flush()`](#l04) | `02794a9` |
| L05 | [AppBridge Signal 跨线程 Direct connection 要 `qt_app.processEvents()`](#l05) | `02794a9` |
| L06 | [默认值变更要同步测试,加启动时自检](#l06) | `02794a9` |
| L07 | [把死功能当活功能展示是误导](#l07) | `6f6b944` |
| L08 | [调研报告要随实现同步归档,迭代报告必写](#l08) | `d80f3ed` |
| L09 | [UI 归属调整要走 signal 路由,不要直接耦合](#l09) | `0825231` |
| L10 | [签名同步修改,占位常量 `yourname/xxx` 提交前必填](#l10) | `7b51242` |
| L11 | [不要用插件目录(`docs/superpowers/`)放项目文档](#l11) | 本次迁移 |
| L12 | [init 子类属性顺序:子类不要在父类初始化前覆盖属性](#l12) | 本次 |
| L13 | [新增 llama-server 参数时要同时打通默认值、UI、命令行和测试](#l13) | `f126e32` |
| L14 | [内置参数说明要从现有 UI 可调项反查](#l14) | `f126e32` |
| L15 | [SpinBox 箭头失效先查 QSS 子控件命中区域](#l15) | 本次 |
| L16 | [`--n-gpu-layers` 默认值语义要和 llama-server 的 auto 对齐](#l16) | 本次 |
| L17 | [`--n-cpu-moe` 上限应按模型层数而不是专家数](#l17) | 本次 |
| L18 | [模型元数据驱动的参数上限要覆盖所有模型路径入口](#l18) | 本次 |
| L19 | [正式发布前要同时核对标签基线、版本号和 Release 内容](#l19) | `v1.2.0` 发布 |
| L20 | [桌面应用 Release 必须包含经过解压启动验证的二进制资产](#l20) | `v1.2.0` 发布补充 |
| L21 | [新增开关参数时要保留默认值的“未显式传参”语义](#l21) | 本次 |
| L22 | [Windows 启动脚本必须固定工作目录](#l22) | 本次 |
| L23 | [引擎日志不能作为稳定 API 假设](#l23) | 本次 |
| L24 | [流式回答的原文状态不能依赖显示控件](#l24) | 本次 |
| L25 | [发布包不能携带开发机的运行时配置](#l25) | `v1.3.0` 发布 |

---

<a id="l01"></a>
## L01 — MCP `replace_symbol_body` 改长方法会误删函数头

**场景**:对 `ControlPanel._build_ui`(170+ 行)调 `replace_symbol_body`,只传 body 字符串。

**错误信号**:
```
IndentationError: unindent does not match any outer indentation level
```
或更隐蔽:文件还能跑,但 UI 一片空白(整个 method 被吞,只剩游离的 body)。

**根因**:
- `replace_symbol_body` 的语义是**整段替换** — 它不会自动保留 `def method_name(self):` 函数头
- 长方法(≥ 30 行)容易误判 body 范围,丢上下文

**正确做法**:
- < 30 行的方法:`replace_symbol_body` 安全
- ≥ 30 行:先用 `find_symbol + depth=0` 看 `body_location` 范围,**或**用 `Read` 拿全文再用 `Edit` 精确改
- 修改前先 `git diff` 确认范围
- 永远不假设"我只动了中间一段"

**检测命令**:
```bash
git diff --stat <file>
# 或
python -c "import ast; ast.parse(open('<file>', encoding='utf-8').read())"
```

---

<a id="l02"></a>
## L02 — `ast.parse` 只查语法不查名字解析

**场景**:改完 `ui/app.py` 加了 `Signal(object)`,用 `python -c "import ast; ast.parse(...)"` 验证通过就提交了。

**错误信号**:
```python
NameError: name 'Signal' is not defined
```
只在**运行** `import ui.app` 时才暴露。

**根因**:
- `ast.parse()` 解析成 AST 但**不执行模块**,NameError/AttributeError 这类运行时错全查不到
- 类级 `Signal(...)` 引用了 `PySide6.QtCore.Signal`,模块顶部 import 列表决定能否找到

**正确做法**:
- 改完 import 列表 / 类级 Signal 字段后,**必须** `python -c "import <module>"` 做真实 import 验证
- 这一步几乎零成本,但能 100% 拦截这种错

**检测命令**(改动 PySide / 顶层 import 后必跑):
```bash
python -c "import <module>; print('<module> import OK')"
```

---

<a id="l03"></a>
## L03 — `Q_ARG(object, ...)` 跨线程调用失败

**场景**:后台线程拿到 `UpdateInfo` dataclass 后,用 `QMetaObject.invokeMethod(self, "_apply", QueuedConnection, Q_ARG(object, info))` 切到主线程。

**错误信号**:
```
WARNING update callback 异常: qArgDataFromPyType: Unable to find a QMetaType for "object".
```

**根因**:
- `QMetaObject.invokeMethod` + `Q_ARG()` 走 **Qt meta-system**
- meta-system 只认 C++ 类型,`"object"` 不是合法 `QMetaType` 标识符
- Python dataclass / 任意 PyObject 都没法通过 meta-system marshal

**正确做法**:
- 跨线程传 Python 对象用 **`Signal`**(PySide6 自动 queued marshalling)
- 给一个 `QObject` 派生类加 `Signal(object)`,子线程 `emit`,Qt 自动 queued 到主线程
- 这与本项目 `EventBus → AppBridge → Signal` 模式一致

**反例**(❌):
```python
QMetaObject.invokeMethod(self, "_apply", QueuedConnection, Q_ARG(object, info))
```

**正例**(✅):
```python
class MyWidget(QMainWindow):
    update_info_received = Signal(object)  # 类级 Signal

    def _on_update_info(self, info):
        self.update_info_received.emit(info)  # 子线程 emit,Qt 自动 queued

# _connect_signals:
self.update_info_received.connect(self._apply_update_info)  # 主线程 slot
```

---

<a id="l04"></a>
## L04 — EventBus 异步,测试必须 `bus.flush()`

**场景**:测试 `bus.emit("foo", x=1)` 后立刻断言 `received == [...]`。

**错误信号**:
```
AssertionError: assert [] == [...]
```

**根因**:
- `EventBus.emit()` 把事件塞进 `Queue` 立即返回
- dispatch 线程异步消费(见 `core/events.py`)
- `emit → 断言` 之间没等,assertion 永远 fail

**正确做法**:
- 测试每次 `emit` 后加 `bus.flush()`(已实现,内部用 sentinel 触发)
- 这是 **7 个预存在失败** 的根因(`test_events.py` 4 个 + `test_bridge.py` 3 个)

**示例**:
```python
def test_x():
    bus = EventBus()
    received = []
    bus.on("foo", lambda **d: received.append(d))
    bus.emit("foo", x=1)
    bus.flush()  # ← 关键
    assert received == [{"x": 1}]
```

---

<a id="l05"></a>
## L05 — AppBridge Signal 跨线程 Direct connection 要 `processEvents()`

**场景**:`AppBridge` 订阅 `EventBus`,`bridge.signal.connect(slot)`,slot 直接 append 到 list。

**错误信号**:即使加了 `bus.flush()`,`received` 还是空。

**根因**:
- `EventBus.dispatch` 线程 emit → `AppBridge.signal.emit(...)` 在 background thread
- PySide6 的 `Signal.emit` 在**非 Qt 线程**调用时,即便 Direct connection 也可能走 AutoConnection → **QueuedConnection**
- Queued connection 需 Qt 事件循环 pump 才会触发 slot
- 测试没 `QApplication.exec()`,事件循环没跑

**正确做法**:
```python
@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication(sys.argv)

def test_bridge(qt_app):
    bus.emit(...)
    bus.flush()
    qt_app.processEvents()  # ← 关键,强制 pump
    assert received == [...]
```

**两层缺一不可**:`bus.flush()`(等 EventBus 异步分发)+ `processEvents()`(等 Qt 事件循环)

---

<a id="l06"></a>
## L06 — 默认值变更要同步测试 + 启动时自检

**场景**:`core/config.py` 的 `DEFAULT_CONFIG` 改了(`flash_attn`: `False → "auto"` / `temp`: 0.80 → 0.6 / `top_p`: 0.95 → 0.9 / `repeat_penalty`: 1.0 → 1.1 / `timeout`: 600 → 1200),测试没同步。

**错误信号**:
```
AssertionError: assert 'auto' is False
```

**根因**:
- 默认值是**契约**的一部分,改了实现不通知测试 = 隐性破坏
- 团队多人协作时更容易踩:有人改了 `DEFAULT_CONFIG`,别人测试一夜全红

**正确做法(短期)**:
- 改 `DEFAULT_CONFIG` 时**主动同步** `tests/test_config.py::test_新增参数默认值`

**正确做法(长期,建议)**:在 `core/config.py` 启动时自检:
```python
def _self_check():
    assert DEFAULT_CONFIG["server"]["temp"] == 0.6, "默认值变更未同步测试"
_self_check()
```
或 pytest `pytest.fixture(autouse=True)` 在每次跑测试前校验。

---

<a id="l07"></a>
## L07 — 把死功能当活功能展示是误导

**场景**:`core/config.py` 有 `save_model_preset` / `get_model_preset`,`core/config_preset.py` 也支持导入导出,但**生产 UI 没有任何按钮调它**。导入对话框却显示"模型专属预设: N 个"。

**根因**:
- 数据层完整,UI 层是 prototype 留下的半成品
- "导入成功"的展示文案把"被存盘"和"对用户可用"混为一谈

**教训**:
- 给用户看成功消息前,自己手动跑一遍完整流程,确认能 end-to-end 用
- CLAUDE.md 规则:"Don't add 'flexibility' or 'configurability' that wasn't requested."
- 写 docstring / UI 文案时,用"已存盘"而非"已保存为可用预设"等模糊措辞

**检测**:
```bash
# 数据层有方法?UI 端有没有人调?
grep -rn "save_model_preset\|get_model_preset" ui/
# 输出空 → 死功能
```

---

<a id="l08"></a>
## L08 — 调研报告要随实现同步归档,迭代报告必写

**场景**:调研 + 实现 + 1 个 commit 完成,但**忘了写迭代报告**。最后用户问起才补。

**根因**:
- 没有"调研→实现→报告"一体化流程
- 容易"实现完了就算了",报告拖到忘记

**正确做法(CLAUDE.md 工作留痕)**:
- **每个 commit 必带工作记录** —— 可放在 commit message + 文档
- 调研类工作:产出 `docs/report/<date>-<topic>-research.md`(一次性研究)
- 实施计划:产出 `docs/plan/<date>-<topic>.md`
- 设计规范:产出 `docs/spec/<date>-<topic>.md`
- 迭代复盘:产出 `docs/report/<date>-<topic>.md`
- **建议**:调研/计划文档 commit 与第一个实现 commit **同步**起草,而不是收尾补

**本项目文档结构**:
```
docs/
├── plan/      # 实施计划(未来要做)
├── spec/      # 设计规范(项目当前状态)
├── report/    # 调研/迭代复盘(历史性)
├── img/       # 截图资源
├── lessons.md # 经验教训库
└── *.html     # 第三方/历史文档
```

---

<a id="l09"></a>
## L09 — UI 归属调整要走 signal 路由

**场景**:"按模型存"按钮原本在 `ControlPanel` 的预设区,但语义上属于"模型库"。要移到 `ModelLibraryPanel`。

**错误做法**:
- 让 `ModelLibraryPanel` 直接 import `ControlPanel` 并调 `control.save_model_preset_for_path(...)`
- 跨层耦合,违反 `core/ui` 解耦原则

**正确做法**:
- `ModelLibraryPanel` 暴露 `request_model_preset_save = Signal(str)`
- `app.py` 在 `_connect_signals` 路由:`library.request_model_preset_save → control.save_model_preset_for_path`
- `ControlPanel` 暴露公共方法 `save_model_preset_for_path(path)`,供外部调用
- 业务方法变成可注入服务,UI 层只剩 wire-up

**对照本项目架构**:
- `core/` 零 UI 依赖(原则)
- `ui/widgets/*` 互相不直接 import(原则)
- `ui/app.py` 是唯一耦合点(通过 `bridge.py` 桥接 EventBus,直接信号走 `_connect_signals`)

---

<a id="l10"></a>
## L10 — 占位常量 `yourname/xxx` 提交前必填

**场景**:`core/updater.py::DEFAULT_REPO = "yourname/llm-launcher"` 当作占位。

**根因**:
- 占位符留在代码里 = 运行时 100% 失败
- 用户首次启动看到"更新检查失败: HTTP Error 404: Not Found",体验差

**正确做法**:
- 提交前**用真实值替换**占位符
- 如果发布前确实不知道,改用 `None` + 显式报错:
  ```python
  DEFAULT_REPO = None  # 必须在打包前设置

  def check_update(repo=None, ...):
      if repo is None:
          raise ValueError("请先在 core/updater.py 设置 DEFAULT_REPO")
  ```
- 或在 `__init__` 加 self-check:`assert DEFAULT_REPO != "yourname/..."`

---

<a id="l11"></a>
## L11 — 不要用插件目录放项目文档

**场景**:把项目自己的设计文档/调研/迭代报告放在 `docs/superpowers/{plans,specs}/` 下。

**错误信号**:
- 用户/维护者看到目录,误以为是 superpowers 插件自身的配置
- 迁移时(插件升级/卸载)有丢失风险
- 文档不应该被插件生命周期管理

**根因**:
- `docs/superpowers/` 是 **superpowers 插件的工作目录**(它约定俗成的位置)
- 项目自己不应"借用"插件目录
- 这是命名空间污染

**正确做法**:
- 项目文档放项目自有目录:
  ```
  docs/
  ├── plans/      # 实施 / 迭代报告
  ├── specs/      # 调研 / 设计
  └── lessons.md  # 经验教训
  ```
- **判断标准**:问自己"卸载 superpowers 插件后,这些文件还应该存在吗?"
  - 答"应该" → 不在 `docs/superpowers/`
  - 答"无所谓" → 也别放,图省事会留隐患

**迁移方法**(已落地的 10 个文件):
```bash
git mv docs/superpowers/plans docs/plans
git mv docs/superpowers/specs docs/specs
git mv docs/superpowers/lessons.md docs/lessons.md
# 顺手修文档内的交叉引用(本项目修了 3 处)
```

---

<a id="l12"></a>
## L12 — `__init__` 里赋值顺序:不要用 `None` 覆盖 `_build_ui` 已经赋好的属性

**场景**:`LlamaLauncherApp.__init__` 里:
```python
self._build_ui()                # 内部 self._update_label = QLabel(...)
...
self._tray = TrayIcon(...)
self._update_label = None       # ← 覆盖了 _build_ui 的赋值!
check_update_async(self._on_update_info)
```
注释还写着"在 _build_ui 之后绑定"——但实际逻辑是**覆盖**。

**错误信号**:
- `_update_label is None` 即使在完整 UI 构造后
- 测试加 `_update_label` 断言时全失败
- 真实运行时若代码路径"先 None 初始化再被覆盖"则**可能永远 None**

**根因**:
- `_build_ui` 已经初始化 `self._update_label` 为 `QLabel(...)`
- 后续 `self._update_label = None` 把它**重置**回 None
- 注释是"占位"语义,代码是"覆盖"语义,二者矛盾

**正确做法**:
- 占位初始化放**最早**(在 `super().__init__()` 之后立即):
  ```python
  def __init__(self):
      super().__init__()
      self._update_label = None  # ← 占位,_build_ui 会覆盖
      ...
      self._build_ui()  # 真的赋值在这里
  ```
- 或者干脆**不写占位 None**,直接相信 `_build_ui` 会赋值,在访问前断言

**检测**:
- `grep "self\._\w\+ = None" 同一文件多次出现` — 多次出现说明可能覆盖
- `pytest` 构造实例后断言关键属性非 None(本项目新增 `test_update_callback.py` 就是这么发现的)

---

## 附录:本次迭代涉及的所有教训(11 个 commit)

| Commit | 教训 |
|---|---|
| `7b51242` | L08(调研报告) + L10(占位常量) |
| `d80f3ed` | L08(迭代报告补) |
| `6f6b944` | L01(replace_symbol_body) + L07(死功能) |
| `0825231` | L09(UI 归属调整) |
| `ac755e2` | L03(Q_ARG 跨线程) |
| `8f4326c` | L02(ast.parse 不查名字) |
| `02794a9` | L04(flush) + L05(processEvents) + L06(默认值同步) |

---

<a id="l13"></a>
## L13 — 新增 llama-server 参数时要同时打通默认值、UI、命令行和测试

**场景**:添加 `--presence-penalty` / `--frequency-penalty` 时,仅在 UI 或命令构造某一侧增加都会导致参数无法完整生效。

**正确做法**:
- `core/config.py` 增加默认值,默认值要与 llama-server 文档一致。
- `ui/widgets/param_groups.py` 增加控件、收集和回填。
- `core/process_manager.py` 只在非默认值时拼接命令行参数。
- 测试覆盖默认值、命令行拼接和 UI 收集/回填。

---

<a id="l14"></a>
## L14 — 内置参数说明要从现有 UI 可调项反查,不要只按旧文档补文字

**场景**:更新参数指南时,旧说明缺少 `--n-cpu-moe` 和投机解码参数,同时 `Slots` 默认值写成关闭,但 UI 默认勾选且命令构造只在关闭时传 `--no-slots`。

**正确做法**:
- 先对照 `ui/widgets/param_groups.py` 的控件和 `core/process_manager.py` 的命令行拼接。
- 指南只写当前已经可调、会实际传参的选项。
- 为指南覆盖范围加轻量测试,至少锁住容易漏掉的新增参数和默认值文案。

---

<a id="l15"></a>
## L15 — SpinBox 箭头失效先查 QSS 子控件命中区域

**场景**:参数面板数值输入框右侧的增大按钮不好点/看起来不起作用。单独测试业务逻辑时 `QSpinBox` 能增加数值,但全局样式只设置了 `QSpinBox` 整体 padding,没有显式定义 `::up-button` / `::down-button` 宽度。

**正确做法**:
- 用 `QStyle.subControlRect(... SC_SpinBoxUp ...)` 检查右侧按钮命中区域。
- 给 `QSpinBox/QDoubleSpinBox` 设置足够的 `padding-right`。
- 显式定义 `QSpinBox::up-button/down-button` 和 `QDoubleSpinBox::up-button/down-button` 的宽度、位置和 hover 样式。
- 测试不仅断言宽度,还要用 `QTest.mouseClick` 点击 up-button 中心确认数值增加。

---

<a id="l16"></a>
## L16 — `--n-gpu-layers` 默认值语义要和 llama-server 的 auto 对齐

**场景**:项目旧默认值把 `-1` 当作"全部卸载到 GPU",但当前 llama-server 参数指南写的是 `auto`。继续把 `-1` 当默认值会导致 UI、README、内置指南和真实命令行语义不一致。

**正确做法**:
- 配置默认值使用 `"auto"`,默认启动时不拼接 `--n-gpu-layers`,交给 llama-server 自己决定。
- UI 可以用 `QSpinBox` 的 `-1` 作为特殊显示值,但 `collect_params()` 必须转成 `"auto"`。
- 数字模式才拼接 `--n-gpu-layers N`,并在选择模型后用 GGUF metadata 的 `block_count` 限制最大值。
- 测试要覆盖默认不拼接、数字值拼接、UI 上限按 `block_count` 夹紧、内置说明默认值为 `auto`。

---

<a id="l17"></a>
## L17 — `--n-cpu-moe` 上限应按模型层数而不是专家数

**场景**:`--n-cpu-moe N` 的 N 表示前 N 层 MoE 权重保留在 CPU,不是每层 expert 数。GGUF metadata 常见的 `expert_count` / `expert_used_count` 不能作为该参数上限。

**正确做法**:
- 用 GGUF metadata 的 `{architecture}.block_count` 作为保守且正确的数值上限。
- UI 范围设为 `0..block_count`,默认 `0` 不拼接命令行。
- 选择模型后同时更新 `--n-gpu-layers` 和 `--n-cpu-moe` 的数值上限。
- 测试覆盖命令行默认不拼接、UI 上限按 `block_count` 夹紧、指南说明不再写固定 `-1..256`。

---

<a id="l18"></a>
## L18 — 模型元数据驱动的参数上限要覆盖所有模型路径入口

**场景**:只在 `on_switch_model()` 中调用 `_update_ctx_for_model()`,导致从模型库切换时有上限,但启动恢复 `model.last_path` 或左侧"浏览"选择模型时仍保留初始上限。

**正确做法**:
- 所有设置主模型路径的入口都要触发同一个 metadata 刷新逻辑。
- 至少覆盖:启动 `_restore()`、浏览 `_browse_model()`、模型库切换 `on_switch_model()`。
- 测试分别构造这三个入口,断言 `--n-gpu-layers` 和 `--n-cpu-moe` 的最大值都按 `block_count` 更新。

---

<a id="l19"></a>
## L19 — 正式发布前要同时核对标签基线、版本号和 Release 内容

**场景**:准备 `v1.2.0` 时,代码中的版本号仍带 `_dev` 后缀,README 也没有汇总上一版本标签之后的实际变更。

**正确做法**:
- 用上一正式标签到 `HEAD` 的提交区间作为发布记录基线,再用迭代报告和实际 diff 交叉核对。
- 正式打标签前把应用版本从开发版同步为发布版,避免已安装的新版本仍提示自己需要更新。
- Release 简介只列用户可感知的变化,不要直接堆叠提交标题。
- 标签、提交、远端分支和 GitHub Release 创建后分别做在线核验。

---

<a id="l20"></a>
## L20 — 桌面应用 Release 必须包含经过解压启动验证的二进制资产

**场景**:只创建了 GitHub 标签和 Release 说明,但没有上传用户可直接下载运行的 Windows 二进制包。

**错误信号**:
- Release 的 `assets` 为空。
- 用户只能下载 Source code,无法按 README 的“下载解压后直接运行”流程使用程序。

**正确做法**:
- 正式版本必须从发布提交重新构建,不能把带 `_dev` 版本号的旧 EXE 当作正式产物。
- 打包完整 Nuitka standalone 目录,保留 DLL、PYD、Qt 插件和 `assets`,排除 `crash.log`、构建目录、缓存及运行时 `config.yaml`。
- 上传前执行 ZIP 完整性和必需文件检查,从 ZIP 解压后的目录再次启动 EXE,确认不会立即退出或生成崩溃日志。
- 上传后用 GitHub 返回的资产大小和 SHA-256 摘要与本地文件逐项比对,资产可在线下载才算发布完成。

---

<a id="l21"></a>
## L21 — 新增开关参数时要保留默认值的“未显式传参”语义

**场景**:为 llama-server 增加聊天模板、推理和 mmproj 相关控制项。`--mmproj-auto` 与 `--mmproj-offload` 的上游默认值均为开启。

**正确做法**:
- UI 用复选框表达开关，但默认开启时不额外传正向参数；仅在用户关闭时传 `--no-mmproj` 或 `--no-mmproj-offload`。
- 路径参数统一经 `_safe_path()` 转为正斜杠，避免 Windows 下传给子进程时出现编码或转义差异。
- 新增参数至少覆盖默认值、UI 收集/预设回填、命令行序列化和内置指南测试。

**验证命令**:
```powershell
.venv\Scripts\python.exe -m pytest tests\test_process_manager.py tests\test_param_groups.py tests\test_config.py tests\test_guide_panel.py -q
```

---

<a id="l22"></a>
## L22 — Windows 启动脚本必须固定工作目录

**场景**:双击或从其他目录调用 `main.py` 启动脚本时，应用会读取相对路径的资源与配置。

**正确做法**:
- 用 `cd /d "%~dp0"` 先切换至脚本所在目录，再执行 `python main.py`。
- 仅在异常退出时 `pause`，方便用户读取报错；正常关闭不额外阻塞。

---

<a id="l23"></a>
## L23 — 引擎日志不能作为稳定 API 假设

**场景**:新版 llama.cpp 将启动日志从 `server is listening` 改为 `listening on`，启动器因精确匹配旧字符串而永久显示“启动中”。

**正确做法**:
- 将旧版和新版监听文本集中到共享就绪判断，供进程状态机与日志监控器共用。
- 启动阶段子进程退出时同样要进入 `CRASHED`，不能只处理运行后退出。
- 用旧、新两种日志各写一条回归测试，升级引擎时先验证状态转换。

---

<a id="l24"></a>
## L24 — 流式回答的原文状态不能依赖显示控件

**场景**:聊天框从纯文本改为 Markdown 富文本后，不能再从控件显示文本中切分得到助手回答。

**正确做法**:
- 单独保存流式原始 Markdown，再在每次 token 到达后渲染显示。
- 完成时将原始 Markdown 写入消息历史，避免格式化、标题或回答中的角色标签影响上下文。
- 清空操作同时清空 API 历史、显示记录和流式缓冲。

---

<a id="l25"></a>
## L25 — 发布包不能携带开发机的运行时配置

**场景**:构建脚本把工作目录的 `config.yaml` 作为数据文件打入 standalone 目录，其中可能包含本机模型路径、窗口状态或其他个人设置。

**正确做法**:
- 发布构建只包含程序运行所需的资源；`config.yaml` 留给应用在首次启动时自动生成默认值。
- 发布前检查 standalone 目录和压缩包，确认其中没有 `config.yaml`、`crash.log` 或其他本机运行痕迹。

---

<a id="l26"></a>
## L26 — 新增枚举型启动参数要保留上游默认语义

**场景**:为 llama-server 增加 `-lm` / `--load-mode MODE`，其默认值为 `auto`，且上游还提供 `none`、`mmap`、`mlock`、`mmap+mlock`、`dio` 等明确取值。

**正确做法**:
- UI 使用固定下拉选项，避免把无效字符串传给引擎。
- `auto` 时不显式传参，保持上游自动选择；只有非默认值才序列化为 `--load-mode MODE`。
- 覆盖默认配置、预设回填、命令行构造和内置参数指南的回归测试。

---

## L27 — 环境迁移必须核对解释器、下载清单和构建入口

**场景**：项目原本直接调用全局 Python，uv 可执行文件存在但未进入当前 PATH；旧 uv 内置 Python 下载列表落后于官方最新列表。

**做法**：先实测解释器和 uv 的路径，再固定 uv 托管 Python 的实际补丁版本。启动、测试和 Nuitka 均使用项目环境，Zig 路径从环境内的模块定位。包隔离、锁文件重建、GUI 启动和 EXE 构建分别记录验证结果。

**本次排查**：用户会话的系统代理与沙箱可见配置不同；下载停顿应检查实际资产链接和正常用户会话的代理，不能仅凭端口监听判断下载成功。旧文件删除受权限限制时按授权提升操作权限，不据此重建或清理全局环境。批量补丁失败后应检查已落地的部分，再继续剩余修改。

**验收补充**：旧的共享 pytest 临时目录可能受其他会话权限影响，应为本项目配置专用 `.pytest_cache/tmp`。Qt 离屏冒烟不能直接等同于真实桌面验收；测试脚本需要显式停止监控线程后退出，并处理离屏平台的中文字体。隐藏启动时 `MainWindowHandle=0` 不代表进程启动失败，应结合消息循环、进程状态和日志判断。Windows 多层字符串中嵌套 Python 代码容易产生转义错误，验证脚本优先使用 PowerShell 单引号 here-string。

## L28 — 依赖下载路径只按当次小样本选择

首版全局测速工具位于 `~/.codex/scripts/download-route.py`；并行请求同一文件前 1 MiB、每路最多 5 秒，比较包含连接等待的平均接收速度。允许 HTTP 206 的限时部分下载参与比较，错误响应不参与，两路均失败返回 null。实测正常路径与双失败路径通过。探测只反映当前样本，不保证整次安装速度；仅影响该次下载的环境，不修改永久代理配置。


## L29 — 下载竞速复用连接和已有数据

第二版下载脚本改为必须提供实际文件 URL；直连和代理各自保存临时文件，约 5 秒后保留已接收字节更多的一路（提前完成则直接采用），终止另一路，让获胜进程继续原连接，成功后再生成目标文件。两路均没有数据时等待至有数据或连接超时，不凭零字节盲选；失败不留下成品，不覆盖已有文件。受控双路测试验证各线路仅请求一次、保留数据并继续、慢路停止、完整内容一致；真实 PyPI requests wheel 下载的 SHA-256 与锁文件一致。此工具是单文件下载器，pip/uv 应消费已下载本地文件，不能接管包管理器已有的网络连接。


## L30 — 按整次依赖安装选路，避免误做单文件下载器

用户的常见场景是 pip/uv 安装多项依赖，最终全局脚本采用 `download-route.py -- 安装命令`：并行限时测速一次，随后只为安装子进程设置代理环境，依赖解析、并发和缓存继续交给包管理器。测速数据不复用；明确仅使用缓存时直接运行原命令。受控测试覆盖两种选路、两路失败不执行、无代理跳过探测、含空格参数、退出码和父环境不变；实际 `uv sync --locked --dry-run` 已通过且未改动依赖。Windows 管道可能按本地代码页编码 Python 输出，脚本明确使用 UTF-8 输出诊断，避免中文 JSON/帮助文本乱码。


## L31 — 清理迁移后的全局依赖要核对实际安装位置

同一 Python 的系统 site-packages 与用户 site-packages 必须分别识别；不能把沙箱中看不到的用户级包直接认定为未安装。卸载前记录包名、版本、位置并检查默认依赖关系，保留其他软件实际需要的用户级 requests。Windows 受保护安装目录使用 UAC 和正常 pip 卸载，不扩大 ACL 权限；卸载后比较完整包清单以确认只删除指定项，再检查全局依赖和项目虚拟环境。

## L32 — 发布版本、指定目录与压缩内容必须一致

用户指定发布目录时，先核对 EXE 哈希和内置版本；版本升级后重新构建，再更新指定目录的程序文件并保留本机配置。压缩包按新构建的文件清单收集内容，排除运行时配置和日志，校验 ZIP 完整性及解压后 EXE 的哈希与启动状态；推送后核对远程分支、标签和 release 资产摘要。

<a id="l33"></a>
## L33 — 参数同步要区分来源、旧指南与实际传参

**来源**：2026-10-09 HTTP Server 参数同步。

新参数标记必须比较同步前的完整 `data-keys` 集合；把组合卡拆开，或补上原本未显示的别名，都不能当作新参数。参数表的 Argument 列同样包含枚举事实；只读 Explanation 会漏掉 `--spec-type` 的类型列表。匹配参数名需包含点号，例如 `--fim-qwen-1.5b-default`，否则新增和移除数量会误报。弃用项保留并加删除线；来源不再列出的旧项注明「来源未列出，支持状态待核实」，不能仅凭文档缺项认定引擎已移除。用户追问标记含义后，提交前同步修正卡片状态与工作记录。

界面默认值与上游默认值不同时，要比较上游默认值决定是否省略传参；否则温度 0.6、Top-P 0.9、重复惩罚 1.1 会静默变成上游值。统一 KV 的默认还取决于并发模式，明确勾选时应明确传入正向开关。`reasoning-format=none` 会保留未解析的思考内容，不能解释成隐藏思考。

预设测试应贯通“回填 → 收集 → 命令生成”。此次发现部分回填代码位于 `_collect` 的 return 后，投机组也未接入控制面板回填；仅测试下拉选项存在无法发现这些问题。

**执行中的坑**：Python 的启动路径警告不等于脚本没有执行，重试前先检查 `git diff`；补丁失败也应先核对落地状态。Windows 沙箱临时目录可能允许创建却禁止后续改名，测试应使用项目临时目录。虚拟环境与浏览器回归最终使用获准的实际环境，避免把替代解释器下的环境检查跳过记录成通过。浏览器选择器应来自最新快照，不能猜分类 ID。

**提交检查**：既有 `docs/*` 忽略规则会让文档避开普通 diff 检查。将本次指定文档显式暂存后再运行 `git diff --cached --check`；此次因此发现并清除了指南的 7 处行尾空格。沙箱禁止写入 `.git/index.lock` 时使用已授权的 Git 操作，不调整仓库 ACL。
