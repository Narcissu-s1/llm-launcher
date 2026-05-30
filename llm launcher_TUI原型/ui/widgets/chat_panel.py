# ui/widgets/chat_panel.py
"""API 测试面板：向本地 llama-server 发送聊天请求"""

import json
import threading
import urllib.request
from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, RichLog


class ChatPanel(Vertical):
    """简易聊天测试面板，支持纯文本和图片 URL"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._port = 8080
        self._history: list[dict] = []

    def compose(self) -> ComposeResult:
        yield RichLog(id="chat_log", highlight=False, markup=True, max_lines=2000)
        with Horizontal(id="chat-input-row"):
            yield Input(placeholder="图片 URL（可选）", id="chat_image_url")
        with Horizontal(id="chat-send-row"):
            yield Input(placeholder="输入消息...", id="chat_input")
            yield Button("发送", id="btn_chat_send", variant="primary")
            yield Button("清空", id="btn_chat_clear", variant="default")

    def set_port(self, port: int) -> None:
        self._port = port

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_chat_send":
            self._send()
        elif event.button.id == "btn_chat_clear":
            self._history.clear()
            self.query_one("#chat_log", RichLog).clear()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "chat_input":
            self._send()

    def _send(self) -> None:
        text = self.query_one("#chat_input", Input).value.strip()
        if not text:
            return
        image_url = self.query_one("#chat_image_url", Input).value.strip()
        self.query_one("#chat_input", Input).value = ""

        # 构造消息内容
        if image_url:
            content = [
                {"type": "text", "text": text},
                {"type": "image_url", "image_url": {"url": image_url}},
            ]
        else:
            content = text

        self._history.append({"role": "user", "content": content})
        self._append(f"[bold cyan]你:[/bold cyan] {text}")
        if image_url:
            self._append(f"[dim]  图片: {image_url}[/dim]")

        port = self._port
        history = list(self._history)
        threading.Thread(target=self._request, args=(port, history), daemon=True).start()

    def _request(self, port: int, history: list) -> None:
        url = f"http://127.0.0.1:{port}/v1/chat/completions"
        body = json.dumps({"model": "local", "messages": history, "stream": False}).encode()
        try:
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            reply = data["choices"][0]["message"]["content"]
            self._history.append({"role": "assistant", "content": reply})
            self.app.call_from_thread(self._append, f"[bold green]模型:[/bold green] {reply}")
        except Exception as e:
            self.app.call_from_thread(self._append, f"[bold red]错误:[/bold red] {e}")

    def _append(self, text: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.query_one("#chat_log", RichLog).write(f"[dim]{ts}[/dim] {text}")
