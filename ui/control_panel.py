# ui/control_panel.py
"""左侧控制面板：模型选择、参数配置、启停按钮"""

import os
import string

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import (
    Button, Collapsible, Input, Label, ListView, ListItem, Select, Static, Switch,
)
from textual.screen import ModalScreen
from ui.widgets.param_groups import (
    KVCacheParams, InferenceParams, SamplingParams,
    ReasoningParams, MultimodalParams, SecurityParams,
)


def _get_available_drives() -> list[str]:
    """获取 Windows 上所有可用盘符"""
    drives = []
    for letter in string.ascii_uppercase:
        drive = f"{letter}:\\"
        if os.path.exists(drive):
            drives.append(drive)
    return drives


def _is_filesystem_root(path: str) -> bool:
    """判断是否在文件系统根目录（盘符下）"""
    return os.path.dirname(path) == path


def _navigate_to_parent(current: str) -> str:
    """返回上级目录，若已在根目录则返回原值"""
    parent = os.path.dirname(current)
    return parent if parent != current else current


class FileBrowser(ModalScreen[str | None]):
    """文件浏览器弹窗，用于选择 GGUF 文件

    显示目录列表，「..」返回上级，Enter 进入目录或选中 .gguf 文件
    """

    def __init__(self, start_dir: str = "."):
        super().__init__()
        self._current_dir = os.path.abspath(
            start_dir if os.path.isdir(start_dir) else "."
        )

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"当前目录: {self._current_dir}", id="browser-path")
            yield ListView(id="file_list")
            with Horizontal(id="browser-actions"):
                yield Button("上级目录", id="btn_parent", variant="primary")
                yield Button("取消", id="btn_cancel", variant="default")

    def on_mount(self) -> None:
        """挂载后加载当前目录内容"""
        self._refresh_list()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """处理按钮点击"""
        if event.button.id == "btn_cancel":
            self.dismiss(None)
        elif event.button.id == "btn_parent":
            new_dir = _navigate_to_parent(self._current_dir)
            if new_dir != self._current_dir:
                self._current_dir = new_dir
            self._refresh_list()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """列表项选中：目录/盘符则进入，.gguf 文件则选中返回"""
        if event.item is None or event.item.name is None:
            return

        choice = event.item.name
        if choice == "..":
            new_dir = _navigate_to_parent(self._current_dir)
            if new_dir != self._current_dir:
                self._current_dir = new_dir
            self._refresh_list()
            return

        # 处理盘符切换（如 "D:\"）
        if choice.endswith(":\\") and os.path.isdir(choice):
            self._current_dir = choice
            self._refresh_list()
            return

        full_path = os.path.join(self._current_dir, choice)
        if os.path.isdir(full_path):
            self._current_dir = full_path
            self._refresh_list()
        elif choice.endswith(".gguf"):
            self.dismiss(full_path)

    def key_escape(self) -> None:
        """Esc 键取消"""
        self.dismiss(None)

    def _refresh_list(self) -> None:
        """刷新文件列表"""
        lst = self.query_one("#file_list", ListView)
        path_label = self.query_one("#browser-path", Label)

        lst.clear()
        path_label.update(f"当前目录: {self._current_dir}")

        items = []

        # 根目录时显示可用盘符，否则显示「..」返回上级
        if _is_filesystem_root(self._current_dir):
            for drive in _get_available_drives():
                items.append(ListItem(Label(f"💾 {drive}"), name=drive))
        else:
            items.append(ListItem(Label("📁 .."), name=".."))

        try:
            entries = sorted(os.listdir(self._current_dir))
        except OSError:
            lst.extend(items)
            return

        # 先列出子目录
        for name in entries:
            full = os.path.join(self._current_dir, name)
            if os.path.isdir(full):
                items.append(ListItem(Label(f"📁 {name}"), name=name))

        # 再列出 .gguf 文件
        for name in entries:
            if name.endswith(".gguf"):
                items.append(ListItem(Label(f"📄 {name}"), name=name))

        lst.extend(items)


class DirPicker(ModalScreen[str | None]):
    """目录选择器弹窗，用于选择 llama.cpp 所在文件夹"""

    def __init__(self, start_dir: str = "."):
        super().__init__()
        self._current_dir = os.path.abspath(
            start_dir if os.path.isdir(start_dir) else "."
        )

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"选择 llama.cpp 目录", id="dir-picker-title")
            yield Label(f"当前: {self._current_dir}", id="dir-picker-path")
            yield ListView(id="dir_list")
            with Horizontal(id="browser-actions"):
                yield Button("选择此目录", id="btn_select_here", variant="success")
                yield Button("上级目录", id="btn_parent", variant="primary")
                yield Button("取消", id="btn_cancel", variant="default")

    def on_mount(self) -> None:
        self._refresh_list()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn_cancel":
            self.dismiss(None)
        elif bid == "btn_select_here":
            self.dismiss(self._current_dir)
        elif bid == "btn_parent":
            new_dir = _navigate_to_parent(self._current_dir)
            if new_dir != self._current_dir:
                self._current_dir = new_dir
            self._refresh_list()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item is None or event.item.name is None:
            return
        choice = event.item.name
        if choice == "..":
            new_dir = _navigate_to_parent(self._current_dir)
            if new_dir != self._current_dir:
                self._current_dir = new_dir
            self._refresh_list()
            return

        # 处理盘符切换（如 "D:\"）
        if choice.endswith(":\\") and os.path.isdir(choice):
            self._current_dir = choice
            self._refresh_list()
            return

        full_path = os.path.join(self._current_dir, choice)
        if os.path.isdir(full_path):
            self._current_dir = full_path
            self._refresh_list()

    def key_escape(self) -> None:
        self.dismiss(None)

    def _refresh_list(self) -> None:
        lst = self.query_one("#dir_list", ListView)
        path_label = self.query_one("#dir-picker-path", Label)
        lst.clear()
        path_label.update(f"当前: {self._current_dir}")

        items = []

        # 根目录时显示可用盘符，否则显示「..」返回上级
        if _is_filesystem_root(self._current_dir):
            for drive in _get_available_drives():
                items.append(ListItem(Label(f"💾 {drive}"), name=drive))
        else:
            items.append(ListItem(Label("📁 .."), name=".."))

        try:
            entries = sorted(os.listdir(self._current_dir))
        except OSError:
            lst.extend(items)
            return

        for name in entries:
            full = os.path.join(self._current_dir, name)
            if os.path.isdir(full):
                items.append(ListItem(Label(f"📁 {name}"), name=name))
        lst.extend(items)


class ControlPanel(Vertical):
    """左侧控制面板"""

    _PARAM_WIDGET_CLASSES = [
        KVCacheParams, InferenceParams, SamplingParams,
        ReasoningParams, MultimodalParams, SecurityParams,
    ]
    """控制面板：左侧栏"""

    def compose(self) -> ComposeResult:
        # 模型选择区
        yield Label("模型选择", classes="section-title")
        with Horizontal(classes="input-row"):
            yield Input(
                placeholder="模型文件路径...",
                id="model_path",
            )
            yield Button("浏览", id="btn_browse_model", variant="primary")
        with Horizontal(classes="input-row"):
            yield Input(
                placeholder="mmproj 文件（可选）...",
                id="mmproj_path",
            )
            yield Button("浏览", id="btn_browse_mmproj", variant="default")

        # llama.cpp 目录
        with Horizontal(classes="input-row"):
            yield Input(
                placeholder="llama.cpp 目录（含 dll 等）...",
                id="llama_cpp_dir",
            )
            yield Button("选择", id="btn_pick_dir", variant="default")

        # 状态指示灯
        with Horizontal(id="status-bar"):
            yield Static("●", id="status_light", classes="status-stopped")
            yield Static("已停止", id="status_text")

        # 基本参数区 — 每行一个参数，Label + 控件在同一行
        yield Label("基本参数", classes="section-title")

        with Horizontal(classes="param-row"):
            yield Label("上下文大小", classes="param-label")
            yield Select(
                [("2048", "2048"), ("4096", "4096"), ("8192", "8192"),
                 ("16384", "16384"), ("32768", "32768")],
                value="4096",
                id="context_size",
            )
        with Horizontal(classes="param-row"):
            yield Label("GPU 层数", classes="param-label")
            yield Input(
                value="0",
                id="n_gpu_layers",
            )
            yield Button("全GPU", id="btn_gpu_all", variant="default")
            yield Button("CPU", id="btn_gpu_cpu", variant="default")
        with Horizontal(classes="param-row"):
            yield Label("并发数", classes="param-label")
            yield Select(
                [("1", "1"), ("2", "2"), ("4", "4"), ("8", "8")],
                value="1",
                id="parallel",
            )
        with Horizontal(classes="param-row"):
            yield Label("端口", classes="param-label")
            yield Input(
                value="8080",
                id="port",
            )
        with Horizontal(classes="param-row"):
            yield Label("监听地址", classes="param-label")
            yield Select(
                [("127.0.0.1（仅本机）", "127.0.0.1"),
                 ("0.0.0.0（局域网）", "0.0.0.0")],
                value="127.0.0.1",
                id="host",
            )

        # 选项区
        with Horizontal(id="options-row"):
            yield Switch(value=True, id="auto_open_browser")
            yield Label("启动后打开浏览器")

        # 高级参数折叠区
        with Collapsible(title="KV Cache 与显存", collapsed=False, id="coll_kvcache"):
            yield KVCacheParams()
        with Collapsible(title="推理速度", collapsed=True, id="coll_inference"):
            yield InferenceParams()
        with Collapsible(title="采样参数", collapsed=False, id="coll_sampling"):
            yield SamplingParams()
        with Collapsible(title="思考模式", collapsed=True, id="coll_reasoning"):
            yield ReasoningParams()
        with Collapsible(title="多模态", collapsed=True, id="coll_multimodal"):
            yield MultimodalParams()
        with Collapsible(title="安全", collapsed=True, id="coll_security"):
            yield SecurityParams()

        # 启停按钮
        with Horizontal(id="action-row"):
            yield Button("▶ 启动", id="btn_start", variant="success")
            yield Button("■ 停止", id="btn_stop", variant="error", disabled=True)

    def update_status(self, status: str) -> None:
        """更新状态指示灯和文字"""
        light = self.query_one("#status_light", Static)
        text = self.query_one("#status_text", Static)

        status_labels = {
            "stopped": ("已停止", "status-stopped"),
            "starting": ("启动中...", "status-starting"),
            "running": ("运行中", "status-running"),
            "crashed": ("已崩溃", "status-crashed"),
        }
        label, css_class = status_labels.get(status, ("未知", "status-stopped"))

        light.update("●")
        light.set_classes(css_class)
        text.update(label)

        # 控制按钮状态
        start_btn = self.query_one("#btn_start", Button)
        stop_btn = self.query_one("#btn_stop", Button)
        start_btn.disabled = status in ("starting", "running")
        stop_btn.disabled = status not in ("starting", "running")

    def collect_params(self) -> dict:
        """收集当前所有参数为字典"""
        params = {
            "model_path": self.query_one("#model_path", Input).value.strip(),
            "mmproj_path": self.query_one("#mmproj_path", Input).value.strip(),
            "port": int(self.query_one("#port", Input).value or "8080"),
            "host": self.query_one("#host", Select).value,
            "context_size": int(self.query_one("#context_size", Select).value),
            "n_gpu_layers": int(self.query_one("#n_gpu_layers", Input).value or "0"),
            "parallel": int(self.query_one("#parallel", Select).value),
            "auto_open_browser": self.query_one("#auto_open_browser", Switch).value,
        }

        # 合并各分组参数
        for widget_cls in self._PARAM_WIDGET_CLASSES:
            widget = self.query_one(widget_cls)
            params.update(widget.collect_params())

        return params

    def restore_advanced_params(self, config_data: dict) -> None:
        """从配置回填高级参数"""
        if not isinstance(config_data, dict):
            return
        server = config_data.get("server", {})
        for widget_cls in self._PARAM_WIDGET_CLASSES:
            widget = self.query_one(widget_cls)
            widget.restore_params(server)
