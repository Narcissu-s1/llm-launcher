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
