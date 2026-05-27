# ui/app.py
"""Textual TUI 主应用入口：组装布局、连接事件总线"""

import logging
import os
import sys
import threading
import webbrowser

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, Footer, Input, Switch

# 确保 core 模块可导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.events import EventBus, EVENT_STATUS_CHANGED, EVENT_LOG_LINE
from core.config import ConfigStore
from core.model_resolver import ModelResolver
from core.process_manager import ProcessSupervisor, ProcessStatus, PortInUseError, ProcessError
from ui.control_panel import ControlPanel, FileBrowser, DirPicker
from ui.log_panel import LogPanel
from ui.widgets.monitor_panel import MonitorPanel

logger = logging.getLogger(__name__)

TUI_CSS = """
Screen {
    layout: horizontal;
}

ControlPanel {
    width: 44;
    min-width: 44;
    max-width: 44;
    background: $surface;
    border: solid $primary-background;
    padding: 1 2;
    overflow-y: auto;
}

ControlPanel .section-title {
    text-style: bold;
    color: $accent;
    margin-top: 1;
    padding-top: 1;
    border-top: solid $primary-background;
}

/* 模型选择行：Input + 浏览按钮 */
ControlPanel .input-row {
    height: 3;
}

ControlPanel .input-row Input {
    width: 1fr;
}

ControlPanel .input-row Button {
    width: 10;
    min-width: 10;
}

/* 参数行：Label + 控件 */
ControlPanel .param-row {
    height: 3;
}

ControlPanel .param-label {
    width: 14;
    content-align: left middle;
    padding-right: 1;
}

ControlPanel .param-row Input {
    width: 1fr;
}

ControlPanel .param-row Select {
    width: 1fr;
}

/* GPU 快捷按钮：紧凑宽度 */
#btn_gpu_all, #btn_gpu_cpu {
    width: 7;
    min-width: 7;
}

ControlPanel #status-bar {
    height: 1;
    margin-top: 1;
    align: center middle;
}

ControlPanel #status-text {
    padding-left: 1;
}

ControlPanel .status-stopped { color: gray; }
ControlPanel .status-starting { color: yellow; }
ControlPanel .status-running { color: green; }
ControlPanel .status-crashed { color: red; }

/* 折叠面板：高度由内容决定 */
ControlPanel Collapsible {
    height: auto;
}

ControlPanel Collapsible .collapsible-contents {
    height: auto;
}

ControlPanel #options-row {
    height: 3;
    margin-top: 1;
}

ControlPanel #action-row {
    height: 3;
    margin-top: 1;
}

ControlPanel #action-row Button {
    width: 50%;
}

LogPanel {
    width: 1fr;
    background: $panel;
    border: solid $primary-background;
    padding: 1;
}

#right-pane {
    width: 1fr;
    layout: vertical;
}

#monitor {
    height: auto;
    max-height: 3;
    background: $panel;
    border: solid $primary-background;
    padding: 0 1;
}

#mon_gpu {
    width: 1fr;
}

#mon_cpu {
    width: 1fr;
}

#mon_ram {
    width: 1fr;
}

#mon_slots {
    width: 1fr;
}

#log-toolbar {
    height: 3;
    align: left middle;
}

#log-toolbar .section-title {
    width: 1fr;
}

#log-toolbar Button {
    width: 14;
    margin-left: 1;
}

LogPanel RichLog {
    height: 1fr;
}

/* 文件浏览器弹窗 */
FileBrowser {
    align: center middle;
}

FileBrowser Vertical {
    width: 66;
    height: 80%;
    background: $surface;
    border: thick $accent;
    padding: 1;
}

#browser-path {
    height: 1;
    text-style: bold;
    color: $text-muted;
    margin-bottom: 1;
}

#file_list {
    height: 1fr;
    border: solid $primary-background;
}

#browser-actions {
    height: 3;
    margin-top: 1;
    align-horizontal: right;
}

#browser-actions Button {
    width: 14;
}

/* 目录选择器弹窗（llama.cpp 目录） */
DirPicker {
    align: center middle;
}

DirPicker Vertical {
    width: 60;
    height: 70%;
    background: $surface;
    border: thick $accent;
    padding: 1;
}

#dir-picker-title {
    height: 1;
    text-style: bold;
    margin-bottom: 1;
}

#dir-picker-path {
    height: 1;
    color: $text-muted;
    margin-bottom: 1;
}

#dir_list {
    height: 1fr;
    border: solid $primary-background;
}
"""


class LlamaLauncherApp(App):
    """LLM 本地模型启动器主应用"""

    CSS = TUI_CSS
    TITLE = "LLM 本地模型启动器"

    def __init__(self):
        super().__init__()
        self._event_bus = EventBus()
        self._config = ConfigStore("config.yaml")
        self._supervisor = ProcessSupervisor(self._event_bus)
        self._model_resolver: ModelResolver | None = None

    def compose(self) -> ComposeResult:
        """组装界面布局"""
        yield ControlPanel(id="control")
        with Vertical(id="right-pane"):
            yield LogPanel(id="log")
            yield MonitorPanel(id="monitor")
        yield Footer()

    def on_mount(self) -> None:
        """应用挂载后初始化事件绑定和数据加载"""
        config_data = self._config.load()

        # 回填 UI 控件
        panel = self.query_one("#control", ControlPanel)
        panel.query_one("#model_path", Input).value = config_data["model"]["last_path"]
        panel.query_one("#mmproj_path", Input).value = config_data["model"]["mmproj_path"]
        panel.query_one("#llama_cpp_dir", Input).value = config_data["app"]["llama_cpp_dir"]
        panel.query_one("#port", Input).value = str(config_data["server"]["port"])
        panel.query_one("#auto_open_browser", Switch).value = config_data["app"]["auto_open_browser"]

        # 初始化 ModelResolver
        self._model_resolver = ModelResolver(
            config_path=config_data["app"]["llama_cpp_dir"]
        )

        # 绑定事件总线
        self._event_bus.on(EVENT_STATUS_CHANGED, self._on_status_changed)
        self._event_bus.on(EVENT_LOG_LINE, self._on_log_line)

        # 回填高级参数
        panel.restore_advanced_params(config_data)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """统一按钮事件处理，按 button id 分发"""
        button_id = event.button.id
        if button_id == "btn_start":
            self._handle_start()
        elif button_id == "btn_stop":
            self._handle_stop()
        elif button_id == "btn_browse_model":
            self._handle_browse()
        elif button_id == "btn_browse_mmproj":
            self._handle_browse_mmproj()
        elif button_id == "btn_pick_dir":
            self._handle_pick_dir()
        elif button_id == "btn_gpu_all":
            self.query_one("#n_gpu_layers", Input).value = "9999"
        elif button_id == "btn_gpu_cpu":
            self.query_one("#n_gpu_layers", Input).value = "0"
        elif button_id == "btn_copy_log":
            self.query_one("#log", LogPanel).copy_all()
            self.notify("日志已复制到剪贴板")
        elif button_id == "btn_clear_log":
            self.query_one("#log", LogPanel).clear()

    def _handle_start(self) -> None:
        """处理启动按钮点击"""
        panel = self.query_one("#control", ControlPanel)
        params = panel.collect_params()

        if not params["model_path"]:
            self.notify("请先选择模型文件", severity="error")
            return

        if not os.path.isfile(params["model_path"]):
            self.notify(f"模型文件不存在: {params['model_path']}", severity="error")
            return

        # 解析 llama-server 路径
        try:
            server_path = self._model_resolver.resolve()
        except FileNotFoundError as e:
            self.notify(str(e), severity="error")
            return

        params["server_path"] = server_path

        # 保存参数到配置
        llama_dir = panel.query_one("#llama_cpp_dir", Input).value.strip()
        self._config.set("model.last_path", params["model_path"])
        self._config.set("model.mmproj_path", params["mmproj_path"])
        self._config.set("app.llama_cpp_dir", llama_dir)
        self._config.set("server.port", params["port"])
        self._config.set("server.host", params["host"])
        self._config.set("server.context_size", params["context_size"])
        self._config.set("server.n_gpu_layers", params["n_gpu_layers"])
        self._config.set("server.parallel", params["parallel"])
        self._config.set("app.auto_open_browser", params["auto_open_browser"])

        try:
            self._supervisor.start(params)
        except PortInUseError as e:
            self.notify(f"端口 {e.port} 已被占用，请更换端口", severity="error")
        except ProcessError as e:
            self.notify(str(e), severity="error")

    def _handle_stop(self) -> None:
        """处理停止按钮点击"""
        self._supervisor.stop()

    def _handle_browse(self) -> None:
        """打开文件浏览器选择 GGUF 模型"""
        panel = self.query_one("#control", ControlPanel)
        last_dir = os.path.dirname(
            panel.query_one("#model_path", Input).value or "."
        )

        def on_selected(path: str | None) -> None:
            if path:
                panel.query_one("#model_path", Input).value = path
                # 自动检测同目录下的 mmproj
                model_dir = os.path.dirname(path)
                try:
                    for fname in os.listdir(model_dir):
                        if "mmproj" in fname.lower() and fname.endswith(".gguf"):
                            panel.query_one("#mmproj_path", Input).value = os.path.join(
                                model_dir, fname
                            )
                            break
                except OSError:
                    pass  # 目录不可读时忽略

        self.push_screen(FileBrowser(start_dir=last_dir), on_selected)

    def _handle_browse_mmproj(self) -> None:
        """打开文件浏览器选择 mmproj 文件"""
        panel = self.query_one("#control", ControlPanel)
        current = panel.query_one("#mmproj_path", Input).value
        last_dir = os.path.dirname(current) if current else os.path.dirname(
            panel.query_one("#model_path", Input).value or "."
        )

        def on_selected(path: str | None) -> None:
            if path:
                panel.query_one("#mmproj_path", Input).value = path

        self.push_screen(FileBrowser(start_dir=last_dir), on_selected)

    def _handle_pick_dir(self) -> None:
        """打开目录选择器选择 llama.cpp 目录"""
        panel = self.query_one("#control", ControlPanel)
        current = panel.query_one("#llama_cpp_dir", Input).value or "."

        def on_selected(dir_path: str | None) -> None:
            if dir_path:
                panel.query_one("#llama_cpp_dir", Input).value = dir_path
                # 同步更新 ModelResolver
                self._model_resolver = ModelResolver(config_path=dir_path)

        self.push_screen(DirPicker(start_dir=current), on_selected)

    def _safe_update(self, fn, *args, **kwargs) -> None:
        """安全跨线程更新 UI

        Textual 的 call_from_thread 只能从后台线程调用。
        当从主线程调用时（如启停按钮），直接执行 UI 更新。
        """
        if threading.current_thread() is threading.main_thread():
            fn(*args, **kwargs)
        else:
            self.call_from_thread(fn, *args, **kwargs)

    def _on_status_changed(self, **data) -> None:
        """响应进程状态变化事件"""
        status = data.get("status", "stopped")

        self._safe_update(
            lambda: self.query_one("#control", ControlPanel).update_status(status)
        )

        if status == "starting":
            self._safe_update(
                lambda: self.query_one("#log", LogPanel).add_line("正在启动 llama-server...")
            )

        if status == "running":
            config_data = self._config.load()
            if config_data["app"]["auto_open_browser"]:
                port = config_data["server"]["port"]
                webbrowser.open(f"http://127.0.0.1:{port}")

            self._safe_update(
                lambda: self.query_one("#log", LogPanel).add_line("服务器已就绪，可通过浏览器访问")
            )

            # 启动监控
            pid = data.get("pid")
            port = config_data["server"]["port"]
            self._safe_update(
                lambda: self.query_one("#monitor", MonitorPanel).start_monitoring(pid, port)
            )

        if status == "stopped":
            self._safe_update(
                lambda: self.query_one("#log", LogPanel).add_line("服务器已停止")
            )
            self._safe_update(
                lambda: self.query_one("#monitor", MonitorPanel).stop_monitoring()
            )

        if status == "crashed":
            exit_code = data.get("exit_code", -1)
            msg = f"llama-server 异常退出 (退出码: {exit_code})，请检查日志"
            self._safe_update(
                lambda: self.query_one("#log", LogPanel).add_line(msg)
            )
            self._safe_update(
                lambda: self.notify(msg, severity="error")
            )
            self._safe_update(
                lambda: self.query_one("#monitor", MonitorPanel).stop_monitoring()
            )

    def _on_log_line(self, **data) -> None:
        """响应日志行事件"""
        line = data.get("line", "")
        self._safe_update(
            lambda: self.query_one("#log", LogPanel).add_line(line)
        )
