# core/config.py
"""YAML 配置文件读写，线程安全的便携式存储"""

import logging
import os
import threading
from copy import deepcopy
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# 默认配置模板
DEFAULT_CONFIG = {
    "model": {
        "last_path": "",         # 上次选择的 GGUF 模型路径
        "mmproj_path": "",       # mmproj 视觉投影文件路径
    },
    "server": {
        # Phase 1
        "port": 8080,            # 监听端口
        "host": "127.0.0.1",     # 监听地址
        "context_size": 32768,   # 上下文大小 (-c)
        "n_gpu_layers": -1,      # GPU 层数 (--n-gpu-layers)，-1=全部
        "parallel": 1,           # 并发数 (-np)
        # Phase 2 - KV Cache
        "cache_type_k": "f16",   # K 缓存类型
        "cache_type_v": "f16",   # V 缓存类型
        "kv_unified": True,      # 使用统一 KV 缓存
        "no_kv_offload": False,  # 禁用 KV 缓存卸载到 GPU
        "flash_attn": "auto",    # Flash Attention (on/off/auto)
        "cache_prompt": True,    # 缓存提示词
        "cache_idle_slots": True,# 空闲槽位可用于缓存
        "cache_ram": 8192,       # prompt cache 内存上限 (MiB)
        # Phase 2 - 推理速度
        "threads": -1,           # 推理线程数（-1=自动）
        "threads_batch": -1,     # 批处理线程数（-1=自动）
        "batch_size": 2048,      # 批大小
        "ubatch_size": 512,      # 微批大小
        "threads_http": -1,      # HTTP 服务线程数（-1=自动）
        "no_warmup": False,      # 跳过预热
        # Phase 2 - 采样参数
        "temp": 0.60,            # 温度
        "top_k": 40,             # Top-K 采样
        "top_p": 0.90,           # Top-P 采样
        "min_p": 0.05,           # Min-P 采样
        "repeat_penalty": 1.10,  # 重复惩罚
        "seed": -1,              # 随机种子（-1=随机）
        "n_predict": -1,         # 最大生成 token 数（-1=无限）
        "ignore_eos": False,     # 忽略结束符持续生成
        # Phase 2 - 思考模式
        "reasoning": "auto",     # 启用推理/思考模式
        "reasoning_format": "auto",  # 推理输出格式
        "reasoning_budget": -1,  # 推理 token 预算（-1=自动）
        # Phase 2 - 多模态
        "mmproj_offload": True,  # 将 mmproj 卸载到 GPU
        "image_min_tokens": 0,   # 图像最少 token 数
        "image_max_tokens": 0,   # 图像最多 token 数
        # Phase 2 - 安全
        "api_key": "",           # API 密钥（空=不启用认证）
        "timeout": 1200,         # 请求超时（秒）
        "metrics": False,        # 启用 /metrics 端点
        "slots": True,           # 启用 /slots 端点
        "tools": False,          # 启用内置 WUI 工具界面（--tools）
    },
    "app": {
        "auto_open_browser": False,  # 启动后自动打开浏览器
        "llama_cpp_dir": "",        # llama.cpp 所在目录（含 dll 等，空则自动搜索）
        "router_mode": False,       # 路由模式：启用 --models-dir 替代 -m
        "models_dir": "",           # 路由模式下的模型目录
    },
    "presets": {},  # 预设：{name: {server params...}}
}


class ConfigStore:
    """YAML 配置文件读写

    配置以 YAML 格式存储，文件不存在时自动用默认值创建。
    所有读写操作线程安全（使用 RLock，同一个线程可重入）。
    """

    def __init__(self, config_path: str):
        """初始化配置存储

        Args:
            config_path: YAML 配置文件完整路径
        """
        self._config_path = config_path
        self._lock = threading.RLock()
        self._data: dict | None = None

    def load(self) -> dict:
        """加载配置文件，文件不存在或损坏时返回默认值

        Returns:
            配置字典的深拷贝
        """
        with self._lock:
            self._load_unlocked()
            return deepcopy(self._data)

    def save(self, data: dict) -> None:
        """保存配置字典到文件

        Args:
            data: 完整配置字典
        """
        with self._lock:
            self._data = deepcopy(data)
            self._save_unlocked()

    def get(self, key: str) -> Any:
        """读取单个配置项，支持点号嵌套路径，线程安全

        Args:
            key: 配置键，如 "model.last_path" 或 "server.port"

        Returns:
            配置值，路径不存在时返回 None
        """
        with self._lock:
            if self._data is None:
                self._load_unlocked()

            parts = key.split(".")
            node = self._data
            for part in parts:
                if isinstance(node, dict) and part in node:
                    node = node[part]
                else:
                    return None
            return node

    def set(self, key: str, value: Any) -> None:
        """设置单个配置项，支持点号嵌套路径，自动保存，线程安全

        Args:
            key: 配置键，如 "server.port"
            value: 新值
        """
        with self._lock:
            if self._data is None:
                self._load_unlocked()

            parts = key.split(".")
            node = self._data
            for part in parts[:-1]:
                if part not in node:
                    node[part] = {}
                node = node[part]
            node[parts[-1]] = value
            self._save_unlocked()

    def _load_unlocked(self) -> None:
        """内部加载逻辑（不加锁，由调用方持锁）"""
        if not os.path.exists(self._config_path):
            self._data = deepcopy(DEFAULT_CONFIG)
            self._save_unlocked()
            return

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
            self._data = self._merge_defaults(loaded, DEFAULT_CONFIG)
        except (yaml.YAMLError, OSError) as e:
            logger.warning("配置文件损坏，使用默认值: %s", e)
            self._data = deepcopy(DEFAULT_CONFIG)
            self._save_unlocked()

    def _save_unlocked(self) -> None:
        """内部保存方法（不加锁，由调用方持锁）"""
        os.makedirs(os.path.dirname(self._config_path) or ".", exist_ok=True)
        with open(self._config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self._data, f, allow_unicode=True, sort_keys=False)

    def _merge_defaults(self, loaded: dict, defaults: dict) -> dict:
        """递归合并，用 defaults 中的键补全 loaded 中缺失的键"""
        result = deepcopy(defaults)
        for key, value in loaded.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_defaults(value, result[key])
            else:
                result[key] = value
        return result

    def get_presets(self) -> dict:
        """返回所有预设 {name: params_dict}"""
        with self._lock:
            if self._data is None:
                self._load_unlocked()
            return deepcopy(self._data.get("presets", {}))

    def save_preset(self, name: str, params: dict) -> None:
        """保存或覆盖一个预设"""
        with self._lock:
            if self._data is None:
                self._load_unlocked()
            if "presets" not in self._data:
                self._data["presets"] = {}
            self._data["presets"][name] = deepcopy(params)
            self._save_unlocked()

    def delete_preset(self, name: str) -> None:
        """删除一个预设，不存在时静默忽略"""
        with self._lock:
            if self._data is None:
                self._load_unlocked()
            self._data.get("presets", {}).pop(name, None)
            self._save_unlocked()

    def get_model_preset(self, model_name: str) -> dict:
        """返回指定模型的专属预设，不存在时返回空字典"""
        with self._lock:
            if self._data is None:
                self._load_unlocked()
            return deepcopy(self._data.get("model_presets", {}).get(model_name, {}))

    def save_model_preset(self, model_name: str, params: dict) -> None:
        """保存模型专属预设"""
        with self._lock:
            if self._data is None:
                self._load_unlocked()
            if "model_presets" not in self._data:
                self._data["model_presets"] = {}
            self._data["model_presets"][model_name] = deepcopy(params)
            self._save_unlocked()
