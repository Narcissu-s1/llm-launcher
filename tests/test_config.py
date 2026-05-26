# tests/test_config.py
"""ConfigStore 单元测试"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.config import ConfigStore


def test_文件不存在时返回默认值():
    """配置文件不存在时，load 应返回默认配置字典"""
    store = ConfigStore("/nonexistent/path/config.yaml")
    config = store.load()
    assert config["model"]["last_path"] == ""
    assert config["model"]["mmproj_path"] == ""
    assert config["server"]["port"] == 8080
    assert config["server"]["host"] == "127.0.0.1"


def test_读写正常():
    """save 后 load 应读到相同数据"""
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        tmp_path = f.name

    try:
        store = ConfigStore(tmp_path)
        data = store.load()
        data["server"]["port"] = 9999
        store.save(data)

        store2 = ConfigStore(tmp_path)
        loaded = store2.load()
        assert loaded["server"]["port"] == 9999
    finally:
        os.unlink(tmp_path)


def test_get_set方法():
    """get/set 支持点号嵌套路径"""
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        tmp_path = f.name

    try:
        store = ConfigStore(tmp_path)
        store.set("model.last_path", "D:/models/test.gguf")
        assert store.get("model.last_path") == "D:/models/test.gguf"
        assert store.get("server.port") == 8080  # 默认值还在
    finally:
        os.unlink(tmp_path)


def test_损坏文件自动恢复():
    """配置文件内容损坏时用默认值重建"""
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w", encoding="utf-8") as f:
        f.write("::: 这不是合法的 YAML :::")
        tmp_path = f.name

    try:
        store = ConfigStore(tmp_path)
        config = store.load()
        # 应返回默认值而非崩溃
        assert config["server"]["port"] == 8080
    finally:
        os.unlink(tmp_path)


def test_新增参数默认值():
    """Phase 2 新增参数应有正确的默认值"""
    from core.config import DEFAULT_CONFIG

    server = DEFAULT_CONFIG["server"]

    # KV Cache
    assert server["cache_type_k"] == "f16"
    assert server["cache_type_v"] == "f16"
    assert server["kv_unified"] is True
    assert server["no_kv_offload"] is False
    assert server["flash_attn"] is False
    assert server["cache_prompt"] is True
    assert server["cache_idle_slots"] is True

    # 推理速度
    assert server["threads"] == -1
    assert server["threads_batch"] == -1
    assert server["batch_size"] == 2048
    assert server["ubatch_size"] == 512
    assert server["threads_http"] == -1
    assert server["no_warmup"] is False

    # 采样参数
    assert server["temp"] == 0.80
    assert server["top_k"] == 40
    assert server["top_p"] == 0.95
    assert server["min_p"] == 0.05
    assert server["repeat_penalty"] == 1.0
    assert server["seed"] == -1
    assert server["n_predict"] == -1

    # 思考模式
    assert server["reasoning"] == "auto"
    assert server["reasoning_format"] == "auto"
    assert server["reasoning_budget"] == -1

    # 多模态
    assert server["mmproj_offload"] is True
    assert server["image_min_tokens"] == 0
    assert server["image_max_tokens"] == 0

    # 安全
    assert server["api_key"] == ""
    assert server["timeout"] == 600
    assert server["metrics"] is False
    assert server["slots"] is True
