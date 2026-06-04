# core/config_preset.py
"""预设导入/导出

将 ConfigStore 中的预设（presets / model_presets）打包为 JSON 文本，
便于用户间分享调参经验。

格式示例：
{
    "version": 1,
    "presets": {"code": {"temp": 0.2, ...}},
    "model_presets": {"qwen2.5-7b": {"temp": 0.3, ...}}
}
"""

import json
import logging
from typing import Any

from core.config import ConfigStore

logger = logging.getLogger(__name__)

_PRESET_FORMAT_VERSION = 1


class PresetFormatError(ValueError):
    """预设文件格式无效（version 不匹配 / 结构错误）"""


def _collect(cfg: ConfigStore) -> dict:
    """从 ConfigStore 收集所有预设"""
    return {
        "presets": cfg.get_presets(),
        "model_presets": {
            name: cfg.get_model_preset(name)
            for name in _list_model_preset_names(cfg)
        },
    }


def _list_model_preset_names(cfg: ConfigStore) -> list:
    """列出所有模型专属预设名（不复制参数本体）"""
    data = cfg.load()
    return list(data.get("model_presets", {}).keys())


def export_presets(cfg: ConfigStore) -> str:
    """导出全部预设为 JSON 文本

    Args:
        cfg: ConfigStore 实例

    Returns:
        JSON 字符串（ensure_ascii=False，缩进 2）
    """
    payload = {"version": _PRESET_FORMAT_VERSION}
    payload.update(_collect(cfg))
    return json.dumps(payload, ensure_ascii=False, indent=2)


def export_presets_to_file(cfg: ConfigStore, path: str) -> None:
    """导出预设到文件"""
    text = export_presets(cfg)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def import_presets(cfg: ConfigStore, text: str) -> dict:
    """从 JSON 文本导入预设，写入 ConfigStore

    Args:
        cfg: 目标 ConfigStore
        text: JSON 文本

    Returns:
        {"presets_added": [...], "model_presets_added": [...]}

    Raises:
        PresetFormatError: 格式无效
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise PresetFormatError(f"JSON 解析失败: {e}") from e

    if not isinstance(data, dict):
        raise PresetFormatError("根节点必须是对象")
    if data.get("version") != _PRESET_FORMAT_VERSION:
        raise PresetFormatError(
            f"预设格式 version 不匹配: 期望 {_PRESET_FORMAT_VERSION}, 实际 {data.get('version')}"
        )

    presets_added: list = []
    model_presets_added: list = []

    for name, params in (data.get("presets") or {}).items():
        if not isinstance(params, dict):
            logger.warning("跳过非字典预设: %s", name)
            continue
        cfg.save_preset(name, params)
        presets_added.append(name)

    for model_name, params in (data.get("model_presets") or {}).items():
        if not isinstance(params, dict):
            logger.warning("跳过非字典模型预设: %s", model_name)
            continue
        cfg.save_model_preset(model_name, params)
        model_presets_added.append(model_name)

    return {
        "presets_added": presets_added,
        "model_presets_added": model_presets_added,
    }


def import_presets_from_file(cfg: ConfigStore, path: str) -> dict:
    """从文件导入预设"""
    with open(path, encoding="utf-8") as f:
        return import_presets(cfg, f.read())
