# ui/widgets/model_library_panel.py
"""模型库面板：扫描目录、展示模型信息、一键切换"""

import os

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, DataTable, Input, Label, Static


class ModelLibraryPanel(Vertical):

    class SwitchModel(Message):
        def __init__(self, path: str, name: str):
            super().__init__()
            self.path = path
            self.name = name

    class SaveModelParams(Message):
        def __init__(self, name: str):
            super().__init__()
            self.name = name

    def compose(self) -> ComposeResult:
        yield Label("模型库", id="ml-title")
        with Horizontal(id="ml-dir-row"):
            yield Input(placeholder="扫描目录...", id="ml_scan_dir")
            yield Button("浏览", id="btn_ml_browse", variant="default")
            yield Button("扫描", id="btn_ml_scan", variant="primary")
        yield DataTable(id="ml_table", cursor_type="row", zebra_stripes=True)
        with Horizontal(id="ml-action-row"):
            yield Button("切换到此模型", id="btn_ml_switch", variant="success")
            yield Button("记住此模型参数", id="btn_ml_save_params", variant="default")
        yield Static("", id="ml_status")

    def on_mount(self) -> None:
        table = self.query_one("#ml_table", DataTable)
        table.add_columns("模型名称", "参数量", "量化", "大小")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_ml_browse":
            self._do_browse()
        elif event.button.id == "btn_ml_scan":
            self._do_scan()
        elif event.button.id == "btn_ml_switch":
            self._do_switch()
        elif event.button.id == "btn_ml_save_params":
            self._do_save_params()

    def _do_browse(self) -> None:
        from ui.control_panel import DirPicker
        current = self.query_one("#ml_scan_dir", Input).value.strip() or "."

        def on_selected(path: str | None) -> None:
            if path:
                self.query_one("#ml_scan_dir", Input).value = path

        self.app.push_screen(DirPicker(start_dir=current, title="选择模型扫描目录"), on_selected)

    def _do_scan(self) -> None:
        from core.model_library import scan_directory, format_size, format_params
        directory = self.query_one("#ml_scan_dir", Input).value.strip()
        if not directory:
            self._set_status("请输入扫描目录", error=True)
            return
        if not os.path.isdir(directory):
            self._set_status("目录不存在", error=True)
            return
        models = scan_directory(directory)
        table = self.query_one("#ml_table", DataTable)
        table.clear()
        self._models = models
        for m in models:
            table.add_row(
                m.name, format_params(m.param_count), m.quant_type, format_size(m.file_size),
                key=m.path,
            )
        self._set_status(f"找到 {len(models)} 个模型")

    def _selected_model(self):
        table = self.query_one("#ml_table", DataTable)
        if not hasattr(self, "_models") or not self._models:
            return None
        idx = table.cursor_row
        if idx < 0 or idx >= len(self._models):
            return None
        return self._models[idx]

    def _do_switch(self) -> None:
        model = self._selected_model()
        if not model:
            self._set_status("请先扫描并选择一个模型", error=True)
            return
        self.post_message(self.SwitchModel(model.path, model.name))

    def _do_save_params(self) -> None:
        model = self._selected_model()
        if not model:
            self._set_status("请先扫描并选择一个模型", error=True)
            return
        self.post_message(self.SaveModelParams(model.name))

    def _set_status(self, text: str, error: bool = False) -> None:
        s = self.query_one("#ml_status", Static)
        s.update(f"[red]{text}[/red]" if error else text)

    def set_scan_dir(self, directory: str) -> None:
        self.query_one("#ml_scan_dir", Input).value = directory
