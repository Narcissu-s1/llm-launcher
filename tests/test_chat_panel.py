"""聊天面板 Markdown 渲染测试。"""

import os
import sys

import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def panel(qt_app, tmp_path):
    from core.config import ConfigStore
    from ui.widgets.chat_panel import ChatPanel

    return ChatPanel(ConfigStore(str(tmp_path / "config.yaml")))


def test_助手消息以基础markdown渲染(panel):
    """标题、加粗、列表和行内代码应由 QTextEdit 渲染为富文本。"""
    panel._display_messages = [
        ("用户", "请列出要点"),
        ("助手", "# 标题\n\n**加粗**\n\n- 条目\n\n`code`"),
    ]

    panel._render_display()

    html = panel._display.toHtml()
    assert "font-weight:700" in html
    assert "<ul" in html
    assert "code" in panel._display.toPlainText()


def test_流式回答保留原始markdown并在完成后写入历史(panel):
    """分片 token 的 Markdown 不应从显示控件反推。"""
    panel._display_messages = [("用户", "测试"), ("助手", "")]
    panel._append_token("**bo")
    panel._append_token("ld**")

    panel._finish_assistant_message()

    assert panel._assistant_buffer == "**bold**"
    assert panel._messages[-1] == {"role": "assistant", "content": "**bold**"}
    assert "font-weight:700" in panel._display.toHtml()


def test_清空聊天时同步清空markdown状态(panel):
    """清空历史后不应留下显示或原始回答缓存。"""
    panel._messages.append({"role": "user", "content": "测试"})
    panel._display_messages.append(("用户", "测试"))
    panel._assistant_buffer = "回答"
    panel._render_display()

    panel._clear()

    assert panel._messages == []
    assert panel._display_messages == []
    assert panel._assistant_buffer == ""
    assert panel._display.toPlainText() == ""
