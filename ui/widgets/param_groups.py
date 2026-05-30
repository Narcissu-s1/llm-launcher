from PySide6.QtWidgets import (
    QGroupBox, QFormLayout, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QLineEdit, QWidget, QVBoxLayout, QPushButton
)

def _safe_int(v, default=0):
    try: return int(v)
    except: return default

def _safe_float(v, default=0.0):
    try: return float(v)
    except: return default


class _CollapsibleGroup(QGroupBox):
    def __init__(self, title: str):
        super().__init__(title)
        self.setCheckable(True)
        self.setChecked(False)
        self.toggled.connect(self._on_toggle)

    def _init_done(self):
        """子类 __init__ 末尾调用，初始化禁用状态"""
        self._on_toggle(False)

    def _on_toggle(self, checked: bool):
        for w in self.findChildren(QWidget):
            w.setEnabled(checked)

    def collect_params(self) -> dict:
        if not self.isChecked():
            return {}
        return self._collect()

    def _collect(self) -> dict:
        raise NotImplementedError

    def restore_params(self, d: dict):
        if d:
            self.setChecked(True)


class KVCacheParams(_CollapsibleGroup):
    def __init__(self):
        super().__init__("KV Cache 与显存")
        form = QFormLayout(self)
        self._ctk = QComboBox(); self._ctk.addItems(["f16","q8_0","q4_0"])
        self._ctv = QComboBox(); self._ctv.addItems(["f16","q8_0","q4_0"])
        self._kvu = QCheckBox("统一 KV 池"); self._kvu.setChecked(True)
        self._no_kv_offload = QCheckBox("KV 不放 GPU")
        self._fa = QComboBox(); self._fa.addItems(["auto", "on", "off"])
        self._cache_prompt = QCheckBox("Prompt Cache"); self._cache_prompt.setChecked(True)
        self._cache_idle = QCheckBox("空闲 Slot 复活"); self._cache_idle.setChecked(True)
        self._cache_ram = QSpinBox(); self._cache_ram.setRange(0, 999999); self._cache_ram.setValue(8192)
        form.addRow("KV-K 量化 (-ctk)", self._ctk)
        form.addRow("KV-V 量化 (-ctv)", self._ctv)
        form.addRow("", self._kvu)
        form.addRow("", self._no_kv_offload)
        form.addRow("Flash Attention (-fa)", self._fa)
        form.addRow("", self._cache_prompt)
        form.addRow("", self._cache_idle)
        form.addRow("Cache RAM (MiB)", self._cache_ram)
        self._init_done()

    def _collect(self):
        return {
            "ctk": self._ctk.currentText(),
            "ctv": self._ctv.currentText(),
            "kvu": self._kvu.isChecked(),
            "no_kv_offload": self._no_kv_offload.isChecked(),
            "flash_attn": self._fa.currentText(),
            "cache_prompt": self._cache_prompt.isChecked(),
            "cache_idle_slots": self._cache_idle.isChecked(),
            "cache_ram": self._cache_ram.value() if self._cache_ram.value() != 8192 else None,
        }

        super().restore_params(d)
        if "ctk" in d: self._ctk.setCurrentText(d["ctk"])
        if "ctv" in d: self._ctv.setCurrentText(d["ctv"])
        if "kvu" in d: self._kvu.setChecked(d["kvu"])
        if "no_kv_offload" in d: self._no_kv_offload.setChecked(d["no_kv_offload"])
        if "flash_attn" in d:
            fa = d["flash_attn"]
            if isinstance(fa, bool):
                fa = "on" if fa else "off"
            self._fa.setCurrentText(str(fa))
        if "cache_prompt" in d: self._cache_prompt.setChecked(d["cache_prompt"])
        if "cache_idle_slots" in d: self._cache_idle.setChecked(d["cache_idle_slots"])
        if "cache_ram" in d and d["cache_ram"]: self._cache_ram.setValue(d["cache_ram"])


class InferenceParams(_CollapsibleGroup):
    def __init__(self):
        super().__init__("推理速度")
        form = QFormLayout(self)
        self._threads = QSpinBox(); self._threads.setRange(-1, 256); self._threads.setValue(-1)
        self._threads_batch = QSpinBox(); self._threads_batch.setRange(-1, 256); self._threads_batch.setValue(-1)
        self._batch = QSpinBox(); self._batch.setRange(1, 65536); self._batch.setValue(2048)
        self._ubatch = QSpinBox(); self._ubatch.setRange(1, 65536); self._ubatch.setValue(512)
        self._threads_http = QSpinBox(); self._threads_http.setRange(-1, 256); self._threads_http.setValue(-1)
        self._no_warmup = QCheckBox("跳过预热")
        self._jinja = QCheckBox("启用 Jinja 模板 (--jinja)")
        self._jinja.setChecked(True)
        self._context_shift = QCheckBox("上下文滑动 (--context-shift)"); self._context_shift.setChecked(True)
        self._keep = QSpinBox(); self._keep.setRange(0, 131072); self._keep.setValue(0)
        self._poll = QSpinBox(); self._poll.setRange(0, 100); self._poll.setValue(50)
        form.addRow("线程数 (-t)", self._threads)
        form.addRow("Prompt 线程 (-tb)", self._threads_batch)
        form.addRow("逻辑批大小 (-b)", self._batch)
        form.addRow("物理批大小 (-ub)", self._ubatch)
        form.addRow("HTTP 线程数", self._threads_http)
        form.addRow("", self._no_warmup)
        form.addRow("", self._jinja)
        form.addRow("", self._context_shift)
        form.addRow("保护前缀 (--keep)", self._keep)
        form.addRow("轮询级别 (--poll)", self._poll)
        self._init_done()

    def _collect(self):
        return {
            "threads": self._threads.value() if self._threads.value() != -1 else None,
            "threads_batch": self._threads_batch.value() if self._threads_batch.value() != -1 else None,
            "batch_size": self._batch.value() if self._batch.value() != 2048 else None,
            "ubatch_size": self._ubatch.value() if self._ubatch.value() != 512 else None,
            "threads_http": self._threads_http.value() if self._threads_http.value() != -1 else None,
            "no_warmup": self._no_warmup.isChecked(),
            "jinja": self._jinja.isChecked(),
            "context_shift": self._context_shift.isChecked(),
            "keep": self._keep.value(),
            "poll": self._poll.value() if self._poll.value() != 50 else None,
        }

        super().restore_params(d)
        if "threads" in d and d["threads"]: self._threads.setValue(d["threads"])
        if "threads_batch" in d and d["threads_batch"]: self._threads_batch.setValue(d["threads_batch"])
        if "batch_size" in d: self._batch.setValue(d["batch_size"])
        if "ubatch_size" in d: self._ubatch.setValue(d["ubatch_size"])
        if "threads_http" in d and d["threads_http"]: self._threads_http.setValue(d["threads_http"])
        if "no_warmup" in d: self._no_warmup.setChecked(d["no_warmup"])


class SamplingParams(_CollapsibleGroup):
    def __init__(self):
        super().__init__("采样参数")
        form = QFormLayout(self)
        self._temp = QDoubleSpinBox(); self._temp.setRange(0.0, 2.0); self._temp.setValue(0.6); self._temp.setSingleStep(0.05)
        self._top_k = QSpinBox(); self._top_k.setRange(0, 1000); self._top_k.setValue(40)
        self._top_p = QDoubleSpinBox(); self._top_p.setRange(0.0, 1.0); self._top_p.setValue(0.90); self._top_p.setSingleStep(0.05)
        self._min_p = QDoubleSpinBox(); self._min_p.setRange(0.0, 1.0); self._min_p.setValue(0.05); self._min_p.setSingleStep(0.01)
        self._repeat_penalty = QDoubleSpinBox(); self._repeat_penalty.setRange(0.5, 2.0); self._repeat_penalty.setValue(1.1); self._repeat_penalty.setSingleStep(0.05)
        self._seed = QSpinBox(); self._seed.setRange(-1, 2**31-1); self._seed.setValue(-1)
        self._n_predict = QSpinBox(); self._n_predict.setRange(-1, 100000); self._n_predict.setValue(-1)
        self._ignore_eos = QCheckBox("忽略 EOS")
        form.addRow("Temperature", self._temp)
        form.addRow("Top-K", self._top_k)
        form.addRow("Top-P", self._top_p)
        form.addRow("Min-P", self._min_p)
        form.addRow("重复惩罚", self._repeat_penalty)
        form.addRow("随机种子", self._seed)
        form.addRow("最大生成长度", self._n_predict)
        form.addRow("", self._ignore_eos)
        self._init_done()

    def _collect(self):
        return {
            "temperature": self._temp.value(),
            "top_k": self._top_k.value(),
            "top_p": self._top_p.value(),
            "min_p": self._min_p.value(),
            "repeat_penalty": self._repeat_penalty.value(),
            "seed": self._seed.value(),
            "n_predict": self._n_predict.value(),
            "ignore_eos": self._ignore_eos.isChecked(),
        }

        super().restore_params(d)
        if "temperature" in d: self._temp.setValue(d["temperature"])
        if "top_k" in d: self._top_k.setValue(d["top_k"])
        if "top_p" in d: self._top_p.setValue(d["top_p"])
        if "min_p" in d: self._min_p.setValue(d["min_p"])
        if "repeat_penalty" in d: self._repeat_penalty.setValue(d["repeat_penalty"])
        if "seed" in d: self._seed.setValue(d["seed"])
        if "n_predict" in d: self._n_predict.setValue(d["n_predict"])
        if "ignore_eos" in d: self._ignore_eos.setChecked(d["ignore_eos"])


class ReasoningParams(_CollapsibleGroup):
    def __init__(self):
        super().__init__("思考/推理模式")
        form = QFormLayout(self)
        self._rea = QComboBox(); self._rea.addItems(["auto","on","off"])
        self._rea_format = QComboBox(); self._rea_format.addItems(["auto","none","deepseek","deepseek-legacy"])
        self._rea_budget = QSpinBox(); self._rea_budget.setRange(-1, 100000); self._rea_budget.setValue(-1)
        form.addRow("思考模式 (-rea)", self._rea)
        form.addRow("思考格式", self._rea_format)
        form.addRow("思考预算", self._rea_budget)
        self._init_done()

    def _collect(self):
        return {
            "reasoning": self._rea.currentText(),
            "reasoning_format": self._rea_format.currentText() if self._rea_format.currentText() != "none" else None,
            "reasoning_budget": self._rea_budget.value(),
        }

        super().restore_params(d)
        if "reasoning" in d: self._rea.setCurrentText(d["reasoning"])
        if "reasoning_format" in d and d["reasoning_format"]: self._rea_format.setCurrentText(d["reasoning_format"])
        if "reasoning_budget" in d: self._rea_budget.setValue(d["reasoning_budget"])


class MultimodalParams(_CollapsibleGroup):
    def __init__(self):
        super().__init__("多模态")
        form = QFormLayout(self)
        self._mmproj_offload = QCheckBox("视觉编码器放 GPU"); self._mmproj_offload.setChecked(True)
        self._img_min = QSpinBox(); self._img_min.setRange(0, 10000); self._img_min.setValue(0)
        self._img_max = QSpinBox(); self._img_max.setRange(0, 10000); self._img_max.setValue(0)
        form.addRow("", self._mmproj_offload)
        form.addRow("最小视觉 Token", self._img_min)
        form.addRow("最大视觉 Token", self._img_max)
        self._init_done()

    def _collect(self):
        return {
            "mmproj_offload": self._mmproj_offload.isChecked(),
            "image_min_tokens": self._img_min.value() if self._img_min.value() > 0 else None,
            "image_max_tokens": self._img_max.value() if self._img_max.value() > 0 else None,
        }

        super().restore_params(d)
        if "mmproj_offload" in d: self._mmproj_offload.setChecked(d["mmproj_offload"])
        if "image_min_tokens" in d and d["image_min_tokens"]: self._img_min.setValue(d["image_min_tokens"])
        if "image_max_tokens" in d and d["image_max_tokens"]: self._img_max.setValue(d["image_max_tokens"])


class SecurityParams(_CollapsibleGroup):
    def __init__(self):
        super().__init__("安全与访问控制")
        form = QFormLayout(self)
        self._api_key = QLineEdit(); self._api_key.setPlaceholderText("留空不传参")
        self._timeout = QSpinBox(); self._timeout.setRange(0, 86400); self._timeout.setValue(1200)
        self._metrics = QCheckBox("Prometheus 监控 (--metrics)")
        self._slots = QCheckBox("Slots 端点 (--slots)"); self._slots.setChecked(True)
        form.addRow("API Key", self._api_key)
        form.addRow("超时秒数", self._timeout)
        form.addRow("", self._metrics)
        form.addRow("", self._slots)
        self._init_done()

    def _collect(self):
        return {
            "api_key": self._api_key.text() or None,
            "timeout": self._timeout.value(),
            "metrics": self._metrics.isChecked(),
            "slots": self._slots.isChecked(),
        }

        super().restore_params(d)
        if "api_key" in d and d["api_key"]: self._api_key.setText(d["api_key"])
        if "timeout" in d: self._timeout.setValue(d["timeout"])
        if "metrics" in d: self._metrics.setChecked(d["metrics"])
        if "slots" in d: self._slots.setChecked(d["slots"])


class SpeculativeParams(_CollapsibleGroup):
    def __init__(self):
        super().__init__("投机解码 (Speculative Decoding)")
        form = QFormLayout(self)
        self._spec_type = QComboBox()
        self._spec_type.addItems(["none", "draft-simple", "draft-eagle3", "draft-mtp", "ngram-simple", "ngram-map-k", "ngram-map-k4v", "ngram-mod", "ngram-cache"])
        self._draft_n_max = QSpinBox(); self._draft_n_max.setRange(1, 64); self._draft_n_max.setValue(3)
        self._draft_n_min = QSpinBox(); self._draft_n_min.setRange(0, 64); self._draft_n_min.setValue(0)
        self._draft_p_split = QDoubleSpinBox(); self._draft_p_split.setRange(0.0, 1.0); self._draft_p_split.setSingleStep(0.05); self._draft_p_split.setValue(0.1)
        self._draft_p_min = QDoubleSpinBox(); self._draft_p_min.setRange(0.0, 1.0); self._draft_p_min.setSingleStep(0.05); self._draft_p_min.setValue(0.0)
        form.addRow("类型 (--spec-type)", self._spec_type)
        form.addRow("最大草稿数 (--spec-draft-n-max)", self._draft_n_max)
        form.addRow("最小草稿数 (--spec-draft-n-min)", self._draft_n_min)
        form.addRow("分割概率 (--spec-draft-p-split)", self._draft_p_split)
        form.addRow("最小概率 (--spec-draft-p-min)", self._draft_p_min)
        self._init_done()

    def _collect(self):
        return {
            "spec_type": self._spec_type.currentText(),
            "spec_draft_n_max": self._draft_n_max.value(),
            "spec_draft_n_min": self._draft_n_min.value(),
            "spec_draft_p_split": self._draft_p_split.value(),
            "spec_draft_p_min": self._draft_p_min.value(),
        }
