# ui/app.py
"""Textual TUI 主应用入口：组装布局、连接事件总线"""

import json
import logging
import os
import sys
import threading
import webbrowser

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, Footer, Input, Switch, TabbedContent, TabPane

# 确保 core 模块可导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.events import EventBus, EVENT_STATUS_CHANGED, EVENT_LOG_LINE
from core.config import ConfigStore
from core.model_resolver import ModelResolver
from core.process_manager import ProcessSupervisor, ProcessStatus, PortInUseError, ProcessError
from ui.control_panel import ControlPanel, FileBrowser, DirPicker, PresetNameDialog, JsonFileBrowser
from ui.log_panel import LogPanel
from ui.widgets.monitor_panel import MonitorPanel
from ui.widgets.chat_panel import ChatPanel
from ui.widgets.model_library_panel import ModelLibraryPanel
from ui.widgets.download_panel import DownloadPanel
from core.model_library import find_mmproj

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

/* 预设管理区 */
#preset-row-select {
    height: 3;
}
#preset-row-select Select {
    width: 1fr;
}
#preset-row-actions {
    height: 3;
}
#btn_preset_load {
    width: 1fr;
}
#preset-row-actions2 {
    height: 3;
}
#preset-row-actions2 Button {
    width: 1fr;
}
#preset-row-actions3 {
    height: 3;
}
#preset-row-actions3 Button {
    width: 1fr;
}

/* 模型库面板 */
ModelLibraryPanel {
    height: 1fr;
    padding: 1;
}

#ml-title {
    text-style: bold;
    color: $accent;
    margin-bottom: 1;
}

#ml-dir-row {
    height: 3;
}

#ml-dir-row Input {
    width: 1fr;
}

#ml_table {
    height: 1fr;
}

#ml-action-row {
    height: 3;
    align: left middle;
}

#ml-action-row Button {
    width: 1fr;
}

#ml_status {
    height: 1;
    padding-left: 1;
    color: $text-muted;
}

/* 下载面板 */
DownloadPanel {
    height: 1fr;
    padding: 1;
}

#dl-title {
    text-style: bold;
    color: $accent;
    margin-bottom: 1;
}

#dl-options-row {
    height: 3;
    align: left middle;
}

#dl-action-row {
    height: 3;
}

#dl-action-row Button {
    width: 1fr;
}

#dl_file_table {
    height: 8;
    margin-bottom: 1;
}

#dl_current_file {
    height: 1;
    color: $text-muted;
}

#dl_progress {
    height: 1;
    margin: 0 0 1 0;
}

#dl-log-toolbar {
    height: 3;
    align: left middle;
}

#dl-log-toolbar Label {
    width: 1fr;
    content-align: left middle;
}

#dl_log {
    height: 1fr;
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

#right-tabs {
    height: 1fr;
}

ChatPanel {
    height: 1fr;
}

#chat_log {
    height: 1fr;
}

#chat-input-row {
    height: 3;
}

#chat-input-row Input {
    width: 1fr;
}

#chat-send-row {
    height: 3;
}

#chat-send-row Input {
    width: 1fr;
}

#btn_chat_send {
    width: 10;
    min-width: 10;
}

#btn_chat_clear {
    width: 8;
    min-width: 8;
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
            with TabbedContent(id="right-tabs"):
                with TabPane("运行日志", id="tab_log"):
                    yield LogPanel(id="log")
                with TabPane("API 测试", id="tab_chat"):
                    yield ChatPanel(id="chat")
                with TabPane("模型库", id="tab_models"):
                    yield ModelLibraryPanel(id="model_library")
                with TabPane("下载模型", id="tab_download"):
                    yield DownloadPanel(id="download_panel")
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

        # 初始化预设列表
        panel.refresh_presets(self._config.get_presets())

        # 初始化模型库扫描目录（用上次模型所在目录）
        last_model = config_data["model"]["last_path"]
        if last_model and os.path.isfile(last_model):
            self.query_one("#model_library", ModelLibraryPanel).set_scan_dir(
                os.path.dirname(last_model)
            )

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
        elif button_id == "btn_preset_save":
            self._handle_preset_save()
        elif button_id == "btn_preset_load":
            self._handle_preset_load()
        elif button_id == "btn_preset_delete":
            self._handle_preset_delete()
        elif button_id == "btn_preset_export":
            self._handle_preset_export()
        elif button_id == "btn_preset_import":
            self._handle_preset_import()

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

        # 输出启动命令到日志面板（每对参数一行）
        cmd = self._supervisor._build_command(params)
        log_panel = self.query_one("#log", LogPanel)
        log_panel.add_line(f"启动: {cmd[0]}")
        i = 1
        while i < len(cmd):
            if cmd[i].startswith("-") and i + 1 < len(cmd) and not cmd[i + 1].startswith("-"):
                log_panel.add_line(f"  {cmd[i]} {cmd[i + 1]}")
                i += 2
            else:
                log_panel.add_line(f"  {cmd[i]}")
                i += 1

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

    def _handle_preset_save(self) -> None:
        """保存当前参数为预设"""
        panel = self.query_one("#control", ControlPanel)
        existing = list(self._config.get_presets().keys())
        selected = panel.get_selected_preset() or ""

        def on_name(name: str | None) -> None:
            if not name:
                return
            if name in existing:
                def on_confirm(confirmed: bool | None) -> None:
                    if confirmed:
                        self._do_save_preset(name)
                from ui.confirm_dialog import ConfirmDialog
                self.push_screen(ConfirmDialog(f"预设「{name}」已存在，覆盖？"), on_confirm)
            else:
                self._do_save_preset(name)

        self.push_screen(PresetNameDialog(existing, default=selected), on_name)

    def _do_save_preset(self, name: str) -> None:
        panel = self.query_one("#control", ControlPanel)
        params = panel.collect_params()
        # 只保存 server 参数（排除路径类）
        server_keys = {k for k in params if k not in ("model_path", "mmproj_path", "auto_open_browser", "server_path")}
        preset_data = {k: params[k] for k in server_keys}
        self._config.save_preset(name, preset_data)
        panel.refresh_presets(self._config.get_presets())
        self.notify(f"预设「{name}」已保存")

    def _handle_preset_load(self) -> None:
        """载入选中预设到 UI"""
        panel = self.query_one("#control", ControlPanel)
        name = panel.get_selected_preset()
        if not name:
            self.notify("请先选择一个预设", severity="warning")
            return
        presets = self._config.get_presets()
        if name not in presets:
            self.notify(f"预设「{name}」不存在", severity="error")
            return
        srv = presets[name]
        panel.restore_advanced_params({"server": srv})
        panel.restore_basic_params(srv)
        self.notify(f"已载入预设「{name}」")

    def _handle_preset_delete(self) -> None:
        """删除选中预设"""
        panel = self.query_one("#control", ControlPanel)
        name = panel.get_selected_preset()
        if not name:
            self.notify("请先选择一个预设", severity="warning")
            return

        def on_confirm(confirmed: bool | None) -> None:
            if confirmed:
                self._config.delete_preset(name)
                panel.refresh_presets(self._config.get_presets())
                self.notify(f"预设「{name}」已删除")

        from ui.confirm_dialog import ConfirmDialog
        self.push_screen(ConfirmDialog(f"确认删除预设「{name}」？"), on_confirm)

    def _handle_preset_export(self) -> None:
        """导出所有预设为 JSON 文件"""
        presets = self._config.get_presets()
        if not presets:
            self.notify("没有可导出的预设", severity="warning")
            return
        # 导出到当前目录
        export_path = os.path.join(os.getcwd(), "presets_export.json")
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(presets, f, ensure_ascii=False, indent=2)
        self.notify(f"已导出到 {export_path}")

    def _handle_preset_import(self) -> None:
        """从 JSON 文件导入预设"""
        def on_selected(path: str | None) -> None:
            if not path:
                return
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    self.notify("JSON 格式错误：顶层应为对象", severity="error")
                    return
                for name, params in data.items():
                    if isinstance(params, dict):
                        self._config.save_preset(name, params)
                panel = self.query_one("#control", ControlPanel)
                panel.refresh_presets(self._config.get_presets())
                self.notify(f"已导入 {len(data)} 个预设")
            except (OSError, json.JSONDecodeError) as e:
                self.notify(f"导入失败: {e}", severity="error")

        self.push_screen(JsonFileBrowser(start_dir=os.getcwd()), on_selected)

    def on_model_library_panel_switch_model(self, event: ModelLibraryPanel.SwitchModel) -> None:
        """处理模型库切换模型请求"""
        panel = self.query_one("#control", ControlPanel)

        # 停止当前服务器
        if self._supervisor.status != "stopped":
            self._supervisor.stop()

        # 切换模型路径
        panel.query_one("#model_path", Input).value = event.path
        mmproj = find_mmproj(event.path)
        panel.query_one("#mmproj_path", Input).value = mmproj

        # 载入新模型的专属预设（如有）
        preset = self._config.get_model_preset(event.name)
        ml = self.query_one("#model_library", ModelLibraryPanel)
        if preset:
            panel.restore_advanced_params({"server": preset})
            panel.restore_basic_params(preset)
            ml._set_status(f"已切换，并恢复上次参数")
            self.notify(f"已切换到 {event.name}，并恢复上次记住的参数")
        else:
            ml._set_status(f"已切换（无历史参数）")
            self.notify(f"已切换到 {event.name}")

    def on_model_library_panel_save_model_params(self, event: ModelLibraryPanel.SaveModelParams) -> None:
        """记住选中模型的当前参数"""
        panel = self.query_one("#control", ControlPanel)
        self._config.save_model_preset(event.name, panel.collect_params())
        self.query_one("#model_library", ModelLibraryPanel)._set_status(f"已记住 {event.name} 的参数")
        self.notify(f"已记住「{event.name}」的当前参数")

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
            self._safe_update(
                lambda: self.query_one("#chat", ChatPanel).set_port(port)
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
