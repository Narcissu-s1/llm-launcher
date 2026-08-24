"""高级参数组 UI 测试"""

import os
import sys

import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="session")
def qt_app():
    """确保 QApplication 实例存在"""
    return QApplication.instance() or QApplication(sys.argv)


def test_采样参数包含存在惩罚和频率惩罚(qt_app):
    """采样参数组应能收集和回填 presence/frequency penalty"""
    from ui.widgets.param_groups import SamplingParams

    group = SamplingParams()
    group.restore_params({
        "presence_penalty": 0.3,
        "frequency_penalty": 0.4,
    })

    params = group.collect_params()

    assert params["presence_penalty"] == 0.3
    assert params["frequency_penalty"] == 0.4


def test_聊天模板与推理参数可以收集和回填(qt_app):
    """聊天模板文件、推理模式和格式应随预设保存与恢复。"""
    from ui.widgets.param_groups import ReasoningParams

    group = ReasoningParams()
    group.restore_params({
        "chat_template_file": "D:/templates/chat.jinja",
        "jinja": False,
        "reasoning": "on",
        "reasoning_format": "deepseek",
    })

    params = group.collect_params()

    assert params["chat_template_file"] == "D:/templates/chat.jinja"
    assert params["jinja"] is False
    assert params["reasoning"] == "on"
    assert params["reasoning_format"] == "deepseek"


def test_多模态自动加载和卸载参数可以收集和回填(qt_app):
    """关闭自动 mmproj 和 GPU 卸载时应保留两个否定开关。"""
    from ui.widgets.param_groups import MultimodalParams

    group = MultimodalParams()
    group.restore_params({"mmproj_auto": False, "mmproj_offload": False})

    params = group.collect_params()

    assert params["mmproj_auto"] is False
    assert params["mmproj_offload"] is False
