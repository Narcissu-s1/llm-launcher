# main.py
"""LLM 本地模型启动器 入口文件"""

import sys
import logging
from PySide6.QtWidgets import QApplication
from ui.app import LlamaLauncherApp

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("LLM Launcher")
    window = LlamaLauncherApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
