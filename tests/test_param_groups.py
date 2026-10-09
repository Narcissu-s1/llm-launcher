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


@pytest.mark.parametrize("cache_type", ["f32", "f16", "bf16", "q8_0", "q4_0", "q4_1", "iq4_nl", "q5_0", "q5_1"])
@pytest.mark.parametrize("cache_ram", [-1, 0, 8192])
def test_KV类型与缓存特殊值回填(qt_app, cache_type, cache_ram):
    from ui.widgets.param_groups import KVCacheParams

    group = KVCacheParams()
    group.restore_params({"ctk": cache_type, "ctv": cache_type, "cache_ram": cache_ram, "kvu": False})
    params = group.collect_params()
    assert params["ctk"] == params["ctv"] == cache_type
    assert params["cache_ram"] == (None if cache_ram == 8192 else cache_ram)
    assert params["kvu"] is False


@pytest.mark.parametrize("spec_type", ["draft-dflash", "draft-dspark"])
def test_新增投机类型回填(qt_app, spec_type):
    from ui.widgets.param_groups import SpeculativeParams

    group = SpeculativeParams()
    group.restore_params({"spec_type": spec_type})
    assert group.collect_params()["spec_type"] == spec_type


def test_推理格式none保留为明确取值(qt_app):
    from ui.widgets.param_groups import ReasoningParams

    group = ReasoningParams()
    group.restore_params({"reasoning_format": "none"})
    assert group.collect_params()["reasoning_format"] == "none"


def test_滑动窗口和全部前缀可回填(qt_app):
    from ui.widgets.param_groups import InferenceParams

    group = InferenceParams()
    group.setChecked(True)
    assert group.collect_params()["context_shift"] is False
    group.restore_params({"context_shift": True, "keep": -1, "poll": 0})
    params = group.collect_params()
    assert params["context_shift"] is True
    assert params["keep"] == -1
    assert params["poll"] == 0


def test_读写超时默认值与旧预设回填(qt_app):
    from ui.widgets.param_groups import SecurityParams

    group = SecurityParams()
    group.setChecked(True)
    assert group.collect_params()["timeout"] == 3600
    group.restore_params({"timeout": 1200})
    assert group.collect_params()["timeout"] == 1200
