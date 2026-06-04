# tests/test_config_preset.py
"""config_preset 单元测试"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.config import ConfigStore
from core.config_preset import (
    export_presets,
    import_presets,
    export_presets_to_file,
    import_presets_from_file,
    PresetFormatError,
)


def _new_store():
    f = tempfile.NamedTemporaryFile(suffix=".yaml", delete=False)
    f.close()
    return ConfigStore(f.name), f.name


def test_导出导入往返():
    """export 后 import 应完整还原数据"""
    src, src_path = _new_store()
    try:
        src.save_preset("code", {"temp": 0.2, "top_p": 0.9})
        src.save_preset("chat", {"temp": 0.8})
        src.save_model_preset("qwen-7b", {"temp": 0.3, "n_gpu_layers": 20})

        text = export_presets(src)

        dst, dst_path = _new_store()
        try:
            result = import_presets(dst, text)
            assert "code" in result["presets_added"]
            assert "chat" in result["presets_added"]
            assert "qwen-7b" in result["model_presets_added"]

            assert dst.get_presets() == {"code": {"temp": 0.2, "top_p": 0.9},
                                          "chat": {"temp": 0.8}}
            assert dst.get_model_preset("qwen-7b") == {"temp": 0.3, "n_gpu_layers": 20}
        finally:
            os.unlink(dst_path)
    finally:
        os.unlink(src_path)


def test_空配置导出():
    """无任何预设时导出也应得到合法 JSON"""
    store, path = _new_store()
    try:
        text = export_presets(store)
        assert '"version": 1' in text
        # 反向应能 import
        store2, path2 = _new_store()
        try:
            result = import_presets(store2, text)
            assert result["presets_added"] == []
            assert result["model_presets_added"] == []
        finally:
            os.unlink(path2)
    finally:
        os.unlink(path)


def test_格式错误抛异常():
    """version 不匹配应抛 PresetFormatError"""
    store, path = _new_store()
    try:
        try:
            import_presets(store, '{"version": 999}')
        except PresetFormatError as e:
            assert "version" in str(e)
        else:
            raise AssertionError("应抛 PresetFormatError")
    finally:
        os.unlink(path)


def test_非JSON文本抛异常():
    """无效 JSON 应抛 PresetFormatError"""
    store, path = _new_store()
    try:
        try:
            import_presets(store, "not a json")
        except PresetFormatError:
            pass
        else:
            raise AssertionError("应抛 PresetFormatError")
    finally:
        os.unlink(path)


def test_导入跳过非字典项():
    """若预设值不是字典，应跳过而非崩溃"""
    store, path = _new_store()
    try:
        text = '{"version": 1, "presets": {"bad": "not a dict", "good": {"x": 1}}}'
        result = import_presets(store, text)
        assert "good" in result["presets_added"]
        assert "bad" not in result["presets_added"]
    finally:
        os.unlink(path)


def test_文件导入导出():
    """import_presets_from_file / export_presets_to_file 端到端"""
    src, src_path = _new_store()
    dst, dst_path = _new_store()
    try:
        src.save_preset("a", {"k": 1})
        tmp_file = src_path + ".export.json"
        try:
            export_presets_to_file(src, tmp_file)
            assert os.path.getsize(tmp_file) > 0
            import_presets_from_file(dst, tmp_file)
            assert dst.get_presets() == {"a": {"k": 1}}
        finally:
            if os.path.exists(tmp_file):
                os.unlink(tmp_file)
    finally:
        os.unlink(src_path)
        os.unlink(dst_path)


def test_导入追加而非覆盖整个预设集():
    """已有同名预设应被覆盖（save_preset 语义）"""
    src, src_path = _new_store()
    try:
        src.save_preset("p", {"old": True})
        text = '{"version": 1, "presets": {"p": {"new": true}}}'
        import_presets(src, text)
        assert src.get_presets() == {"p": {"new": True}}
    finally:
        os.unlink(src_path)


def test_model_name_from_path():
    """GGUF 路径应能正确提取去后缀的模型名"""
    from core.model_library import model_name_from_path
    assert model_name_from_path("D:/models/qwen2.5-7b-instruct-q4_k_m.gguf") \
        == "qwen2.5-7b-instruct-q4_k_m"
    assert model_name_from_path("C:\\models\\sub\\llama-3.1-8b.Q8_0.gguf") \
        == "llama-3.1-8b.Q8_0"
    assert model_name_from_path("a.gguf") == "a"
    assert model_name_from_path("/no/dir/") == ""  # 无文件名返回空


def test_专属预设与通用预设隔离():
    """get_presets / get_model_preset 应互不干扰"""
    store, path = _new_store()
    try:
        store.save_preset("通用", {"temp": 0.5})
        store.save_model_preset("qwen-7b", {"temp": 0.2})
        assert store.get_presets() == {"通用": {"temp": 0.5}}
        assert store.get_model_preset("qwen-7b") == {"temp": 0.2}
        assert store.get_model_preset("通用") == {}  # 通用预设不算模型专属
    finally:
        os.unlink(path)


def test_专属预设可被同名覆盖():
    """同名模型再次保存应覆盖"""
    store, path = _new_store()
    try:
        store.save_model_preset("m", {"a": 1})
        store.save_model_preset("m", {"b": 2})
        assert store.get_model_preset("m") == {"b": 2}
    finally:
        os.unlink(path)
