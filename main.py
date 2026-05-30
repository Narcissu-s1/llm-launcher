# main.py
"""LLM 本地模型启动器 入口文件"""

import sys
import os
import logging
import traceback

# 崩溃日志写到 exe 同目录的 crash.log
_base = os.path.dirname(os.path.abspath(sys.argv[0]))
_log_path = os.path.join(_base, "crash.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(_log_path, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)


def main():
    from PySide6.QtWidgets import QApplication
    from ui.app import LlamaLauncherApp

    app = QApplication(sys.argv)
    app.setApplicationName("LLM Launcher")

    qss_path = os.path.join(_base, "assets", "theme_light.qss")
    if os.path.exists(qss_path):
        with open(qss_path, encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    window = LlamaLauncherApp()
    window.show()
    sys.exit(app.exec())


try:
    main()
except Exception:
    logging.error("启动崩溃:\n%s", traceback.format_exc())
    raise
