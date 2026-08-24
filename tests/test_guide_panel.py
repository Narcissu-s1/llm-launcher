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
        "--chat-template-file",
        "--jinja",
        "--no-jinja",
        "--reasoning",
        "--reasoning-format",
        "--mmproj-auto",
        "--no-mmproj",
        "--mmproj-offload",
        "--no-mmproj-offload",
    ]:
        assert flag in text


def test_slots说明默认值与UI一致():
    """Slots UI 默认勾选,指南默认值也应写为开启"""
    text = _guide_text()

    assert "Slots 端点  --slots" in text
    assert "Slots 端点  --slots\n开启" in text


def test_n_gpu_layers说明默认值与参数指南一致():
    """GPU 层数默认值应为 auto,不再使用旧的 -1=全部语义"""
    text = _guide_text()

    assert "GPU 层数  --n-gpu-layers\nauto" in text
    assert "-1 = 全部卸载" not in text


def test_n_cpu_moe说明使用模型层数上限():
    """CPU MoE 层数应说明 0 默认值和模型层数上限"""
    text = _guide_text()

    assert "CPU MoE 层数  --n-cpu-moe\n0（不传参），范围 0 ~ 模型层数" in text
    assert "范围 -1 ~ 256" not in text
