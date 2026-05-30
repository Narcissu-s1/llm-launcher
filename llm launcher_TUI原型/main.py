# main.py
"""LLM 本地模型启动器 入口文件"""

import logging
import os
import sys

# 确保项目根目录在 sys.path 中，方便 core/ui 导入
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from ui.app import LlamaLauncherApp


def setup_logging():
    """配置日志格式与级别"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main():
    """应用入口"""
    setup_logging()
    app = LlamaLauncherApp()
    app.run()


if __name__ == "__main__":
    main()
