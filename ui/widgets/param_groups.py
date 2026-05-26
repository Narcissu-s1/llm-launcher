"""高级参数分组 Widget"""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, Label, Select, Switch


def _safe_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _safe_float(value: str, default: float) -> float:
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


class KVCacheParams(Horizontal):
    """KV Cache 与显存参数组"""

    def compose(self) -> ComposeResult:
        yield Label("KV Cache 与显存", classes="section-title")
        with Horizontal(classes="param-row"):
            yield Label("K Cache 量化", classes="param-label")
            yield Select(
                [("f16", "f16"), ("q8_0", "q8_0"), ("q4_0", "q4_0")],
                value="f16",
                id="cache_type_k",
            )
        with Horizontal(classes="param-row"):
            yield Label("V Cache 量化", classes="param-label")
            yield Select(
                [("f16", "f16"), ("q8_0", "q8_0"), ("q4_0", "q4_0")],
                value="f16",
                id="cache_type_v",
            )
        with Horizontal(classes="param-row"):
            yield Label("统一 KV 池", classes="param-label")
            yield Switch(value=True, id="kv_unified")
        with Horizontal(classes="param-row"):
            yield Label("KV 不放 GPU", classes="param-label")
            yield Switch(value=False, id="no_kv_offload")
        with Horizontal(classes="param-row"):
            yield Label("Flash Attention", classes="param-label")
            yield Switch(value=False, id="flash_attn")
        with Horizontal(classes="param-row"):
            yield Label("Prompt Cache", classes="param-label")
            yield Switch(value=True, id="cache_prompt")
        with Horizontal(classes="param-row"):
            yield Label("空闲 Slot 复活", classes="param-label")
            yield Switch(value=True, id="cache_idle_slots")

    def collect_params(self) -> dict:
        """收集 KV Cache 参数"""
        return {
            "cache_type_k": self.query_one("#cache_type_k", Select).value,
            "cache_type_v": self.query_one("#cache_type_v", Select).value,
            "kv_unified": self.query_one("#kv_unified", Switch).value,
            "no_kv_offload": self.query_one("#no_kv_offload", Switch).value,
            "flash_attn": self.query_one("#flash_attn", Switch).value,
            "cache_prompt": self.query_one("#cache_prompt", Switch).value,
            "cache_idle_slots": self.query_one("#cache_idle_slots", Switch).value,
        }

    def restore_params(self, params: dict) -> None:
        """从配置回填 KV Cache 参数"""
        self.query_one("#cache_type_k", Select).value = params.get("cache_type_k", "f16")
        self.query_one("#cache_type_v", Select).value = params.get("cache_type_v", "f16")
        self.query_one("#kv_unified", Switch).value = params.get("kv_unified", True)
        self.query_one("#no_kv_offload", Switch).value = params.get("no_kv_offload", False)
        self.query_one("#flash_attn", Switch).value = params.get("flash_attn", False)
        self.query_one("#cache_prompt", Switch).value = params.get("cache_prompt", True)
        self.query_one("#cache_idle_slots", Switch).value = params.get("cache_idle_slots", True)


class InferenceParams(Horizontal):
    """推理速度参数组"""

    def compose(self) -> ComposeResult:
        yield Label("推理速度", classes="section-title")
        with Horizontal(classes="param-row"):
            yield Label("线程数", classes="param-label")
            yield Input(value="-1", id="threads", placeholder="-1=自动")
        with Horizontal(classes="param-row"):
            yield Label("Prompt 线程", classes="param-label")
            yield Input(value="-1", id="threads_batch", placeholder="-1=等于线程数")
        with Horizontal(classes="param-row"):
            yield Label("逻辑批大小", classes="param-label")
            yield Input(value="2048", id="batch_size")
        with Horizontal(classes="param-row"):
            yield Label("物理批大小", classes="param-label")
            yield Input(value="512", id="ubatch_size")
        with Horizontal(classes="param-row"):
            yield Label("HTTP 线程", classes="param-label")
            yield Input(value="-1", id="threads_http", placeholder="-1=自动")
        with Horizontal(classes="param-row"):
            yield Label("跳过预热", classes="param-label")
            yield Switch(value=False, id="no_warmup")

    def collect_params(self) -> dict:
        return {
            "threads": _safe_int(self.query_one("#threads", Input).value, -1),
            "threads_batch": _safe_int(self.query_one("#threads_batch", Input).value, -1),
            "batch_size": _safe_int(self.query_one("#batch_size", Input).value, 2048),
            "ubatch_size": _safe_int(self.query_one("#ubatch_size", Input).value, 512),
            "threads_http": _safe_int(self.query_one("#threads_http", Input).value, -1),
            "no_warmup": self.query_one("#no_warmup", Switch).value,
        }

    def restore_params(self, params: dict) -> None:
        self.query_one("#threads", Input).value = str(params.get("threads", -1))
        self.query_one("#threads_batch", Input).value = str(params.get("threads_batch", -1))
        self.query_one("#batch_size", Input).value = str(params.get("batch_size", 2048))
        self.query_one("#ubatch_size", Input).value = str(params.get("ubatch_size", 512))
        self.query_one("#threads_http", Input).value = str(params.get("threads_http", -1))
        self.query_one("#no_warmup", Switch).value = params.get("no_warmup", False)


class SamplingParams(Horizontal):
    """采样参数组"""

    def compose(self) -> ComposeResult:
        yield Label("采样参数", classes="section-title")
        with Horizontal(classes="param-row"):
            yield Label("温度", classes="param-label")
            yield Input(value="0.80", id="temp")
        with Horizontal(classes="param-row"):
            yield Label("Top-K", classes="param-label")
            yield Input(value="40", id="top_k")
        with Horizontal(classes="param-row"):
            yield Label("Top-P", classes="param-label")
            yield Input(value="0.95", id="top_p")
        with Horizontal(classes="param-row"):
            yield Label("Min-P", classes="param-label")
            yield Input(value="0.05", id="min_p")
        with Horizontal(classes="param-row"):
            yield Label("重复惩罚", classes="param-label")
            yield Input(value="1.0", id="repeat_penalty")
        with Horizontal(classes="param-row"):
            yield Label("随机种子", classes="param-label")
            yield Input(value="-1", id="seed", placeholder="-1=随机")
        with Horizontal(classes="param-row"):
            yield Label("最大生成", classes="param-label")
            yield Input(value="-1", id="n_predict", placeholder="-1=无限")

    def collect_params(self) -> dict:
        return {
            "temp": _safe_float(self.query_one("#temp", Input).value, 0.80),
            "top_k": _safe_int(self.query_one("#top_k", Input).value, 40),
            "top_p": _safe_float(self.query_one("#top_p", Input).value, 0.95),
            "min_p": _safe_float(self.query_one("#min_p", Input).value, 0.05),
            "repeat_penalty": _safe_float(self.query_one("#repeat_penalty", Input).value, 1.0),
            "seed": _safe_int(self.query_one("#seed", Input).value, -1),
            "n_predict": _safe_int(self.query_one("#n_predict", Input).value, -1),
        }

    def restore_params(self, params: dict) -> None:
        self.query_one("#temp", Input).value = str(params.get("temp", 0.80))
        self.query_one("#top_k", Input).value = str(params.get("top_k", 40))
        self.query_one("#top_p", Input).value = str(params.get("top_p", 0.95))
        self.query_one("#min_p", Input).value = str(params.get("min_p", 0.05))
        self.query_one("#repeat_penalty", Input).value = str(params.get("repeat_penalty", 1.0))
        self.query_one("#seed", Input).value = str(params.get("seed", -1))
        self.query_one("#n_predict", Input).value = str(params.get("n_predict", -1))


class ReasoningParams(Horizontal):
    """思考/推理模式参数组"""

    def compose(self) -> ComposeResult:
        yield Label("思考模式", classes="section-title")
        with Horizontal(classes="param-row"):
            yield Label("启用模式", classes="param-label")
            yield Select(
                [("auto", "auto"), ("on", "on"), ("off", "off")],
                value="auto",
                id="reasoning",
            )
        with Horizontal(classes="param-row"):
            yield Label("思考格式", classes="param-label")
            yield Select(
                [("auto", "auto"), ("none", "none"), ("deepseek", "deepseek"), ("deepseek-legacy", "deepseek-legacy")],
                value="auto",
                id="reasoning_format",
            )
        with Horizontal(classes="param-row"):
            yield Label("思考预算", classes="param-label")
            yield Input(value="-1", id="reasoning_budget", placeholder="-1=不限")

    def collect_params(self) -> dict:
        return {
            "reasoning": self.query_one("#reasoning", Select).value,
            "reasoning_format": self.query_one("#reasoning_format", Select).value,
            "reasoning_budget": _safe_int(self.query_one("#reasoning_budget", Input).value, -1),
        }

    def restore_params(self, params: dict) -> None:
        self.query_one("#reasoning", Select).value = params.get("reasoning", "auto")
        self.query_one("#reasoning_format", Select).value = params.get("reasoning_format", "auto")
        self.query_one("#reasoning_budget", Input).value = str(params.get("reasoning_budget", -1))


class MultimodalParams(Horizontal):
    """多模态参数组"""

    def compose(self) -> ComposeResult:
        yield Label("多模态", classes="section-title")
        with Horizontal(classes="param-row"):
            yield Label("视觉放 GPU", classes="param-label")
            yield Switch(value=True, id="mmproj_offload")
        with Horizontal(classes="param-row"):
            yield Label("最小视觉 Token", classes="param-label")
            yield Input(value="0", id="image_min_tokens", placeholder="0=默认")
        with Horizontal(classes="param-row"):
            yield Label("最大视觉 Token", classes="param-label")
            yield Input(value="0", id="image_max_tokens", placeholder="0=默认")

    def collect_params(self) -> dict:
        return {
            "mmproj_offload": self.query_one("#mmproj_offload", Switch).value,
            "image_min_tokens": _safe_int(self.query_one("#image_min_tokens", Input).value, 0),
            "image_max_tokens": _safe_int(self.query_one("#image_max_tokens", Input).value, 0),
        }

    def restore_params(self, params: dict) -> None:
        self.query_one("#mmproj_offload", Switch).value = params.get("mmproj_offload", True)
        self.query_one("#image_min_tokens", Input).value = str(params.get("image_min_tokens", 0))
        self.query_one("#image_max_tokens", Input).value = str(params.get("image_max_tokens", 0))


class SecurityParams(Horizontal):
    """安全与访问控制参数组"""

    def compose(self) -> ComposeResult:
        yield Label("安全", classes="section-title")
        with Horizontal(classes="param-row"):
            yield Label("API Key", classes="param-label")
            yield Input(value="", id="api_key", placeholder="留空不校验")
        with Horizontal(classes="param-row"):
            yield Label("超时秒数", classes="param-label")
            yield Input(value="600", id="timeout")
        with Horizontal(classes="param-row"):
            yield Label("Prometheus", classes="param-label")
            yield Switch(value=False, id="metrics")
        with Horizontal(classes="param-row"):
            yield Label("Slots 端点", classes="param-label")
            yield Switch(value=True, id="slots")

    def collect_params(self) -> dict:
        return {
            "api_key": self.query_one("#api_key", Input).value.strip(),
            "timeout": _safe_int(self.query_one("#timeout", Input).value, 600),
            "metrics": self.query_one("#metrics", Switch).value,
            "slots": self.query_one("#slots", Switch).value,
        }

    def restore_params(self, params: dict) -> None:
        self.query_one("#api_key", Input).value = params.get("api_key", "")
        self.query_one("#timeout", Input).value = str(params.get("timeout", 600))
        self.query_one("#metrics", Switch).value = params.get("metrics", False)
        self.query_one("#slots", Switch).value = params.get("slots", True)
