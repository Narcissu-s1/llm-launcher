from datetime import datetime
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QPlainTextEdit, QLabel
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt

class LogPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(12, 6, 12, 6)
        header.addWidget(QLabel("日志"))
        header.addStretch()
        btn_clear = QPushButton("清空")
        btn_copy = QPushButton("复制")
        btn_clear.clicked.connect(self.clear)
        btn_copy.clicked.connect(self.copy_all)
        header.addWidget(btn_clear)
        header.addWidget(btn_copy)
        layout.addLayout(header)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("DM Mono, Consolas, Courier New", 11))
        self._log.setMaximumBlockCount(5000)
        layout.addWidget(self._log)

    def add_line(self, line: str):
        ts = datetime.now().strftime("%H:%M:%S")
        lower = line.lower()
        if line.startswith(">>> ") or line.startswith("    "):
            color = "#4a9eff"
        elif any(k in lower for k in ["error", "failed", "oom", "killed"]):
            color = "#e53e3e"
        elif any(k in lower for k in ["warn", "warning"]):
            color = "#d69e2e"
        elif any(k in lower for k in ["loaded", "listening", "success", "ready", "llm loaded", "model loaded"]):
            color = "#1a9e6e"
        else:
            color = "#718096"
        html = f'<span style="color:#a0aec0">{ts}</span> <span style="color:{color}">{line}</span>'
        self._log.appendHtml(html)

    def clear(self):
        self._log.clear()

    def copy_all(self):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._log.toPlainText())
