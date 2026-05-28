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
    timings = Signal(dict)   # {'ttft_ms', 'prompt_n', 'prompt_ms', 'prompt_per_s', 'gen_n', 'gen_ms', 'gen_per_s'}
    done = Signal()
    error = Signal(str)

    def __init__(self, port: int, messages: list, api_key: str = ""):
        super().__init__()
        self._port = port
        self._messages = messages
        self._api_key = api_key

    def run(self):
        import time
        try:
            url = f"http://127.0.0.1:{self._port}/v1/chat/completions"
            payload = json.dumps({"model": "local", "messages": self._messages, "stream": True}).encode()
            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            req = urllib.request.Request(url, data=payload, headers=headers)

            t_start = time.monotonic()
            t_first = None
            stats = {}

            with urllib.request.urlopen(req, timeout=60) as resp:
                for raw in resp:
                    line = raw.decode().strip()
                    if not line.startswith("data: ") or line == "data: [DONE]":
                        continue
                    chunk = json.loads(line[6:])
                    choice = chunk["choices"][0]
                    delta = choice["delta"].get("content", "")
                    if delta:
                        if t_first is None:
                            t_first = time.monotonic()
                        self.token.emit(delta)
                    # 最后一个 chunk 含 timings（llama.cpp 扩展字段）
                    if choice.get("finish_reason") and "timings" in chunk:
                        t = chunk["timings"]
                        stats = {
                            "ttft_ms":     round((t_first - t_start) * 1000) if t_first else 0,
                            "prompt_n":    t.get("prompt_n", 0),
                            "prompt_ms":   round(t.get("prompt_ms", 0)),
                            "prompt_per_s": round(t.get("prompt_per_second", 0), 1),
                            "gen_n":       t.get("predicted_n", 0),
                            "gen_ms":      round(t.get("predicted_ms", 0)),
                            "gen_per_s":   round(t.get("predicted_per_second", 0), 1),
                        }

            if stats:
                self.timings.emit(stats)
            self.done.emit()
        except Exception as e:
            self.error.emit(str(e))


class ChatPanel(QWidget):
    def __init__(self, config: ConfigStore):
        super().__init__()
        self._config = config
        self._messages = []
        self._workers = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        # 模型信息栏
        self._model_info = QLabel("模型未加载")
        self._model_info.setStyleSheet(
            "font-family:'DM Mono',Consolas;font-size:11px;color:#718096;"
            "background:#f8fafb;border:1px solid #e8eef2;border-radius:4px;padding:4px 8px;"
        )
        self._model_info.setWordWrap(True)
        layout.addWidget(self._model_info)

        # 对话显示区
        self._display = QPlainTextEdit()
        self._display.setReadOnly(True)
        layout.addWidget(self._display, stretch=1)

        # 统计信息栏
        self._stats = QLabel("")
        self._stats.setStyleSheet(
            "font-family:'DM Mono',Consolas;font-size:11px;color:#718096;"
            "background:#f8fafb;border:1px solid #e8eef2;border-radius:4px;padding:4px 8px;"
        )
        self._stats.setVisible(False)
        layout.addWidget(self._stats)

        # 输入行
        row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText("输入消息…")
        self._input.returnPressed.connect(self._send)
        self._btn_send = QPushButton("发送")
        self._btn_send.setObjectName("btnPrimary")
        self._btn_send.clicked.connect(self._send)
        self._btn_clear = QPushButton("清空历史")
        self._btn_clear.clicked.connect(self._clear)
        row.addWidget(self._input)
        row.addWidget(self._btn_send)
        row.addWidget(self._btn_clear)
        layout.addLayout(row)

    def update_model_info(self, params: dict):
        """由外部（启动时）调用，更新模型信息栏"""
        model_name = params.get("model_path", "")
        if model_name:
            import os
            model_name = os.path.basename(model_name)
        parts = [
            f"模型: {model_name or '—'}",
            f"端口: {params.get('port', 8080)}",
            f"上下文: {params.get('context_size', '—')}",
            f"GPU层: {params.get('n_gpu_layers', '—')}",
        ]
        self._model_info.setText("  |  ".join(parts))

    def _send(self):
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self._messages.append({"role": "user", "content": text})
        self._display.appendPlainText(f"\nUser: {text}\nAssistant: ")
        self._stats.setVisible(False)
        port = self._config.get("server.port") or 8080
        api_key = self._config.get("server.api_key") or ""
        worker = _ChatWorker(port, list(self._messages), api_key)
        self._workers.append(worker)
        worker.token.connect(lambda t: self._display.insertPlainText(t))
        worker.timings.connect(self._on_timings)
        worker.done.connect(lambda: (
            self._messages.append({"role": "assistant", "content": self._display.toPlainText().split("Assistant: ")[-1]}),
            self._workers.remove(worker) if worker in self._workers else None
        ))
        worker.error.connect(lambda e: (
            self._display.appendPlainText(f"\n[错误] {e}"),
            self._workers.remove(worker) if worker in self._workers else None
        ))
        worker.start()

    def _on_timings(self, s: dict):
        ttft = s.get("ttft_ms", 0)
        p_n, p_ms, p_spd = s.get("prompt_n", 0), s.get("prompt_ms", 0), s.get("prompt_per_s", 0)
        g_n, g_ms, g_spd = s.get("gen_n", 0), s.get("gen_ms", 0), s.get("gen_per_s", 0)
        text = (
            f"首字延迟 {ttft} ms  │  "
            f"Prompt {p_n} tok / {p_ms} ms / {p_spd} t/s  │  "
            f"生成 {g_n} tok / {g_ms} ms / {g_spd} t/s"
        )
        self._stats.setText(text)
        self._stats.setVisible(True)

    def _clear(self):
        self._messages.clear()
        self._display.clear()
