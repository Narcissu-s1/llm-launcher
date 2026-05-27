import json, urllib.request
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QPlainTextEdit, QLabel
)
from PySide6.QtCore import QThread, Signal
from core.config import ConfigStore

class _ChatWorker(QThread):
    token = Signal(str)
    done = Signal()
    error = Signal(str)

    def __init__(self, port: int, messages: list, api_key: str = ""):
        super().__init__()
        self._port = port
        self._messages = messages
        self._api_key = api_key

    def run(self):
        try:
            url = f"http://127.0.0.1:{self._port}/v1/chat/completions"
            payload = json.dumps({"model": "local", "messages": self._messages, "stream": True}).encode()
            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            req = urllib.request.Request(url, data=payload, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                for raw in resp:
                    line = raw.decode().strip()
                    if line.startswith("data: ") and line != "data: [DONE]":
                        chunk = json.loads(line[6:])
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            self.token.emit(delta)
            self.done.emit()
        except Exception as e:
            self.error.emit(str(e))


class ChatPanel(QWidget):
    def __init__(self, config: ConfigStore):
        super().__init__()
        self._config = config
        self._messages = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        self._display = QPlainTextEdit()
        self._display.setReadOnly(True)
        layout.addWidget(self._display, stretch=1)

        row = QHBoxLayout()
        self._input = QLineEdit(); self._input.setPlaceholderText("输入消息…")
        self._input.returnPressed.connect(self._send)
        self._btn_send = QPushButton("发送"); self._btn_send.setObjectName("btnPrimary")
        self._btn_send.clicked.connect(self._send)
        self._btn_clear = QPushButton("清空历史")
        self._btn_clear.clicked.connect(self._clear)
        row.addWidget(self._input)
        row.addWidget(self._btn_send)
        row.addWidget(self._btn_clear)
        layout.addLayout(row)

    def _send(self):
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self._messages.append({"role": "user", "content": text})
        self._display.appendPlainText(f"\nUser: {text}\nAssistant: ")
        port = self._config.get("server.port", 8080)
        api_key = self._config.get("server.api_key", "")
        worker = _ChatWorker(port, list(self._messages), api_key)
        worker.token.connect(lambda t: self._display.insertPlainText(t))
        worker.done.connect(lambda: self._messages.append(
            {"role": "assistant", "content": self._display.toPlainText().split("Assistant: ")[-1]}
        ))
        worker.error.connect(lambda e: self._display.appendPlainText(f"\n[错误] {e}"))
        worker.start()

    def _clear(self):
        self._messages.clear()
        self._display.clear()
