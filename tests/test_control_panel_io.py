# tests/test_control_panel_io.py
"""ControlPanel 的导入/导出/模型专属预设 UI 测试

策略：mock QFileDialog 与 QMessageBox，避免打开真实对话框，
只验证 control_panel 的逻辑路径（数据流过 import_presets / export_presets）。
"""

import json
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="session")
def qt_app():
    """确保 QApplication 实例存在（PySide6 测试必备）"""
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def config_path():
    """每个测试一个独立 config.yaml"""
    f = tempfile.NamedTemporaryFile(suffix=".yaml", delete=False)
    f.close()
    yield f.name
    if os.path.exists(f.name):
        os.unlink(f.name)


@pytest.fixture
def control(qt_app, config_path):
    """构造 ControlPanel（最小依赖：config + mock supervisor）"""
    from core.config import ConfigStore
    from ui.control_panel import ControlPanel

    config = ConfigStore(config_path)
    supervisor = MagicMock()
    return ControlPanel(config, supervisor)


def test_导出预设调用核心模块并写入文件(control, config_path):
    """_export_presets 应调 export_presets_to_file,内容包含已保存的 preset"""
    from core.config_preset import export_presets_to_file

    control._config.save_preset("code", {"temp": 0.2})

    out_path = config_path + ".export.json"
    with patch("ui.control_panel.QFileDialog.getSaveFileName",
               return_value=(out_path, "JSON (*.json)")):
        control._export_presets()

    assert os.path.exists(out_path)
    data = json.loads(open(out_path, encoding="utf-8").read())
    assert data["version"] == 1
    assert "code" in data["presets"]
    assert data["presets"]["code"]["temp"] == 0.2
    os.unlink(out_path)


def test_导出预设用户取消时不写文件(control):
    """QFileDialog 返回空路径（用户取消）应直接返回，不写文件"""
    import core.config_preset

    called = {"n": 0}
    original = core.config_preset.export_presets_to_file

    def spy(*a, **kw):
        called["n"] += 1
        return original(*a, **kw)

    with patch("ui.control_panel.QFileDialog.getSaveFileName",
               return_value=("", "")), \
         patch("core.config_preset.export_presets_to_file", side_effect=spy):
        control._export_presets()

    assert called["n"] == 0  # 没调到核心


def test_导入预设成功(control, config_path):
    """_import_presets 应从文件读取预设并写入 ConfigStore"""
    src_path = config_path + ".src.json"
    open(src_path, "w", encoding="utf-8").write(json.dumps({
        "version": 1,
        "presets": {"chat": {"temp": 0.7}},
        "model_presets": {"qwen-7b": {"temp": 0.3}},
    }, ensure_ascii=False))

    with patch("ui.control_panel.QFileDialog.getOpenFileName",
               return_value=(src_path, "JSON (*.json)")), \
         patch("ui.control_panel.QMessageBox.information") as mock_info, \
         patch("ui.control_panel.QMessageBox.warning") as mock_warn:
        control._import_presets()

    assert mock_warn.call_count == 0  # 没报错
    assert mock_info.call_count == 1  # 弹了成功框
    assert control._config.get_presets() == {"chat": {"temp": 0.7}}
    assert control._config.get_model_preset("qwen-7b") == {"temp": 0.3}

    # 文案包含通用和模型专属的数量
    info_text = mock_info.call_args.args[2]
    assert "1 个" in info_text  # 1 通用 + 1 模型

    os.unlink(src_path)


def test_导入预设用户取消时不调核心(control):
    """QFileDialog 返回空路径（用户取消）应直接返回"""
    with patch("ui.control_panel.QFileDialog.getOpenFileName",
               return_value=("", "")):
        control._import_presets()
    # 验证：ConfigStore 没新增预设
    assert control._config.get_presets() == {}


def test_导入预设格式错误弹警告(control, config_path):
    """无效 JSON 应弹警告框,不写入 ConfigStore"""
    bad_path = config_path + ".bad.json"
    open(bad_path, "w", encoding="utf-8").write("not a json")

    with patch("ui.control_panel.QFileDialog.getOpenFileName",
               return_value=(bad_path, "JSON (*.json)")), \
         patch("ui.control_panel.QMessageBox.warning") as mock_warn, \
         patch("ui.control_panel.QMessageBox.information") as mock_info:
        control._import_presets()

    assert mock_warn.call_count == 1
    assert mock_info.call_count == 0
    assert control._config.get_presets() == {}
    os.unlink(bad_path)


def test_save_model_preset_for_path_空路径弹警告(control):
    """空路径应弹警告,不调 save_model_preset"""
    with patch("ui.control_panel.QMessageBox.warning") as mock_warn, \
         patch.object(control._config, "save_model_preset") as mock_save:
        control.save_model_preset_for_path("")

    assert mock_warn.call_count == 1
    assert mock_save.call_count == 0


def test_save_model_preset_for_path_新预设直接保存(control):
    """无现有专属预设 → 直接 save_model_preset + 弹成功框"""
    test_path = "D:/models/qwen2.5-7b-instruct-q4_k_m.gguf"

    with patch("ui.control_panel.QMessageBox.information") as mock_info, \
         patch("ui.control_panel.QMessageBox.warning") as mock_warn, \
         patch("ui.confirm_dialog.ConfirmDialog.exec", return_value=True):
        control.save_model_preset_for_path(test_path)

    assert mock_warn.call_count == 0
    assert mock_info.call_count == 1
    saved = control._config.get_model_preset("qwen2.5-7b-instruct-q4_k_m")
    assert saved is not None
    # 关键：model_path 字段被剔除（专属预设不存 model_path）
    assert "model_path" not in saved


def test_save_model_preset_for_path_覆盖已存在的预设需确认(control):
    """已有同名专属预设 → 弹 ConfirmDialog,确认后覆盖"""
    control._config.save_model_preset("qwen-7b", {"old": True})

    with patch("ui.confirm_dialog.ConfirmDialog.exec", return_value=True) as mock_exec, \
         patch("ui.control_panel.QMessageBox.information"):
        control.save_model_preset_for_path("/some/path/qwen-7b.gguf")

    assert mock_exec.call_count == 1
    saved = control._config.get_model_preset("qwen-7b")
    # 新参数生效,旧参数被覆盖
    assert "old" not in saved


def test_save_model_preset_for_path_取消覆盖(control):
    """ConfirmDialog 取消 → 不写入"""
    control._config.save_model_preset("qwen-7b", {"old": True})

    with patch("ui.confirm_dialog.ConfirmDialog.exec", return_value=False), \
         patch("ui.control_panel.QMessageBox.information") as mock_info:
        control.save_model_preset_for_path("/some/path/qwen-7b.gguf")

    assert mock_info.call_count == 0
    assert control._config.get_model_preset("qwen-7b") == {"old": True}
