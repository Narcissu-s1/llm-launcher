import base64
import json
import os
import urllib.request
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QPlainTextEdit, QLabel, QFileDialog, QMessageBox
)
from PySide6.QtCore import QThread, Signal
from core.config import ConfigStore
from core.model_library import find_mmproj

class _ChatWorker(QThread):
    token = Signal(str)
    timings = Signal(dict)
    done = Signal()
    error = Signal(str)

    def __init__(self, port: int, messages: list, api_key: str = ""):
        super().__init__()
        self._port = port
        self._messages = messages
        self._api_key = api_key
        self._stopped = False

    def stop(self):
        self._stopped = True

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
                    if self._stopped:
                        break
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

            if stats and not self._stopped:
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

        # 附图标签（选图后显示文件名）
        self._image_label = QLabel("")
        self._image_label.setStyleSheet("font-size:11px;color:#718096;")
        self._image_label.setVisible(False)
        self._image_path = ""
        layout.addWidget(self._image_label)

        # 输入行
        row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText("输入消息…")
        self._input.returnPressed.connect(self._send)
        self._btn_image = QPushButton("附图")
        self._btn_image.clicked.connect(self._pick_image)
        self._btn_send = QPushButton("发送")
        self._btn_send.setObjectName("btnPrimary")
        self._btn_send.clicked.connect(self._send)
        self._btn_stop = QPushButton("停止")
        self._btn_stop.setObjectName("btnStop")
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._stop_generation)
        self._btn_clear = QPushButton("清空历史")
        self._btn_clear.clicked.connect(self._clear)
        row.addWidget(self._input)
        row.addWidget(self._btn_image)
        row.addWidget(self._btn_send)
        row.addWidget(self._btn_stop)
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
        if not text and not self._image_path:
            return
        self._input.clear()

        # 构造 content（纯文本 或 多模态）
        if self._image_path:
            # 检查 mmproj 是否已配置（服务端必须加载 mmproj 才能处理图片）
            mmproj = self._config.get("model.mmproj_path") or ""
            if not mmproj:
                model_path = self._config.get("model.last_path") or ""
                if model_path:
                    detected = find_mmproj(model_path)
                    if detected:
                        mmproj = detected
            if not mmproj:
                QMessageBox.warning(
                    self, "未配置 mmproj",
                    "发送图片需要多模态投影文件（mmproj）。\n"
                    "请在左侧启动面板填写 mmproj 路径后重新启动服务，再发送图片。"
                )
                return
            ext = os.path.splitext(self._image_path)[1].lower().lstrip(".")
            mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                    "png": "image/png", "gif": "image/gif",
                    "webp": "image/webp"}.get(ext, "image/jpeg")
            with open(self._image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            content = []
            if text:
                content.append({"type": "text", "text": text})
            content.append({"type": "image_url",
                             "image_url": {"url": f"data:{mime};base64,{b64}"}})
            display_text = f"{text}  [图片: {os.path.basename(self._image_path)}]" if text else f"[图片: {os.path.basename(self._image_path)}]"
            self._image_path = ""
            self._image_label.setVisible(False)
        else:
            content = text
            display_text = text

        self._messages.append({"role": "user", "content": content})
        self._display.appendPlainText(f"\nUser: {display_text}\nAssistant: ")
        self._stats.setVisible(False)
        port = self._config.get("server.port") or 8080
        api_key = self._config.get("server.api_key") or ""
        worker = _ChatWorker(port, list(self._messages), api_key)
        self._workers.append(worker)
        self._btn_send.setEnabled(False)
        self._btn_stop.setEnabled(True)

        def _on_worker_done():
            self._messages.append({"role": "assistant", "content": self._display.toPlainText().split("Assistant: ")[-1]})
            if worker in self._workers:
                self._workers.remove(worker)
            if not self._workers:
                self._btn_send.setEnabled(True)
                self._btn_stop.setEnabled(False)

        def _on_worker_error(e):
            self._display.appendPlainText(f"\n[错误] {e}")
            if worker in self._workers:
                self._workers.remove(worker)
            if not self._workers:
                self._btn_send.setEnabled(True)
                self._btn_stop.setEnabled(False)

        worker.token.connect(self._append_token)
        worker.timings.connect(self._on_timings)
        worker.done.connect(_on_worker_done)
        worker.error.connect(_on_worker_error)
        worker.start()

    def _append_token(self, token: str):
        """将 token 追加到文本末尾，不受光标位置影响"""
        cursor = self._display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._display.setTextCursor(cursor)
        self._display.insertPlainText(token)

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

    def _stop_generation(self):
        for w in list(self._workers):
            w.stop()
        self._btn_stop.setEnabled(False)
        self._btn_send.setEnabled(True)

    def _pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.gif *.webp)"
        )
        if path:
            self._image_path = path
            self._image_label.setText(f"已附图：{os.path.basename(path)}")
            self._image_label.setVisible(True)
