# ui/app.py
"""PySide6 主窗口占位（Task 4 将完整实现）"""

from PySide6.QtWidgets import QMainWindow, QLabel


class LlamaLauncherApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LLM Launcher")
        self.resize(1200, 800)
        self.setCentralWidget(QLabel("占位"))
