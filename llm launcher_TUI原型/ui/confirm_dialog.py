# ui/confirm_dialog.py
"""通用二次确认弹窗"""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ConfirmDialog(ModalScreen[bool]):
    """显示确认消息，返回 True（确认）或 False（取消）"""

    def __init__(self, message: str):
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Label(self._message)
            with Horizontal():
                yield Button("确认", id="btn_confirm_ok", variant="error")
                yield Button("取消", id="btn_confirm_cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn_confirm_ok")

    def key_escape(self) -> None:
        self.dismiss(False)
