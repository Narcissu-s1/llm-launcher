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
