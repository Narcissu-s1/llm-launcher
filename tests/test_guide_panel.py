"""内置参数指南内容测试"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _guide_text() -> str:
    from ui.widgets.guide_panel import _SECTIONS

    parts = []
    for title, rows in _SECTIONS:
        parts.append(title)
        for row in rows:
            parts.extend(row)
    return "\n".join(parts)


def test_内置参数说明覆盖当前可调参数():
    """参数指南应覆盖 UI 中已有的可调启动参数"""
    text = _guide_text()

    for flag in [
        "--n-cpu-moe",
        "--spec-type",
        "--spec-draft-n-max",
        "--spec-draft-n-min",
        "--spec-draft-p-split",
        "--spec-draft-p-min",
        "-md",
    ]:
        assert flag in text


def test_slots说明默认值与UI一致():
    """Slots UI 默认勾选,指南默认值也应写为开启"""
    text = _guide_text()

    assert "Slots 端点  --slots" in text
    assert "Slots 端点  --slots\n开启" in text
