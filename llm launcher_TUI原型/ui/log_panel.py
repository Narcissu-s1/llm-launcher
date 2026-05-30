# ui/log_panel.py
"""右侧日志面板：实时显示 llama-server 输出日志"""

import subprocess
from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Button, RichLog


class LogPanel(Vertical):
    """日志面板：显示 llama-server 的 stdout/stderr 输出"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 保存纯文本行用于复制（不含 RichLog markup 标签）
        self._plain_lines: list[str] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="log-toolbar"):
            yield Label("运行日志", classes="section-title")
            yield Button("复制全部", id="btn_copy_log", variant="default")
            yield Button("清空", id="btn_clear_log", variant="default")
        yield RichLog(
            id="log_view",
            highlight=True,
            markup=True,
            max_lines=5000,
        )

    def add_line(self, line: str) -> None:
        """添加一行日志

        Args:
            line: 日志文本
        """
        log = self.query_one("#log_view", RichLog)
        timestamp = datetime.now().strftime("%H:%M:%S")

        # 保存纯文本
        self._plain_lines.append(f"[{timestamp}] {line}")

        # RichLog 显示（带关键词高亮）
        if "error" in line.lower() or "cuda error" in line.lower():
            log.write(f"[{timestamp}] [bold red]{line}[/bold red]")
        elif "server is listening" in line.lower():
            log.write(f"[{timestamp}] [bold green]{line}[/bold green]")
        elif "out of memory" in line.lower():
            log.write(f"[{timestamp}] [bold yellow]{line}[/bold yellow]")
        else:
            log.write(f"[{timestamp}] {line}")

    def clear(self) -> None:
        """清空日志"""
        self.query_one("#log_view", RichLog).clear()
        self._plain_lines.clear()

    def copy_all(self) -> None:
        """复制全部日志到剪贴板"""
        if not self._plain_lines:
            return
        text = "\n".join(self._plain_lines)
        try:
            subprocess.run(
                ["clip.exe"],
                input=text,
                text=True,
                encoding="utf-8",
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=5,
            )
        except (subprocess.TimeoutExpired, OSError):
            pass  # 复制失败时静默忽略
