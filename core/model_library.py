# core/model_library.py
"""扫描目录下的 GGUF 模型文件，解析基本元数据"""

import os
import struct
from dataclasses import dataclass, field


# GGUF 魔数
_GGUF_MAGIC = b"GGUF"

# 量化类型映射（GGUF type id → 名称）
_QUANT_NAMES = {
    0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1",
    6: "Q5_0", 7: "Q5_1", 8: "Q8_0", 9: "Q8_1",
    10: "Q2_K", 11: "Q3_K_S", 12: "Q3_K_M", 13: "Q3_K_L",
    14: "Q4_K_S", 15: "Q4_K_M", 16: "Q5_K_S", 17: "Q5_K_M",
    18: "Q6_K", 19: "Q8_K", 20: "IQ2_XXS", 21: "IQ2_XS",
    24: "IQ3_XXS", 26: "IQ1_S", 27: "IQ4_NL", 28: "IQ3_S",
    29: "IQ2_S", 30: "IQ4_XS", 31: "IQ1_M", 32: "BF16",
}

# GGUF value type ids
_VTYPE_UINT32 = 4
_VTYPE_UINT64 = 8
_VTYPE_STRING = 8  # 注意：string 在 metadata 里 type=8 不对，实际 string=9
# 正确映射
_VTYPE = {0: "uint8", 1: "int8", 2: "uint16", 3: "int16",
          4: "uint32", 5: "int32", 6: "float32", 7: "bool",
          8: "string", 9: "array", 10: "uint64", 11: "int64", 12: "float64"}

_VTYPE_SIZES = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4,
                6: 4, 7: 1, 10: 8, 11: 8, 12: 8}


@dataclass
class ModelInfo:
    path: str
    name: str                    # 文件名（不含扩展名）
    file_size: int               # 字节
    quant_type: str = "未知"
    param_count: int = 0         # 参数量（个）
    size_label: str = ""         # 原始 size_label，如 "35B-A3B"
    architecture: str = ""
    context_length: int = 0      # 模型最大上下文长度（token）
    block_count: int = 0         # Transformer 层数（--n-gpu-layers 上限）


def scan_directory(directory: str) -> list[ModelInfo]:
    """扫描目录（非递归）下所有 .gguf 文件，返回 ModelInfo 列表"""
    if not os.path.isdir(directory):
        return []
    results = []
    for root, _, files in os.walk(directory):
        for fname in sorted(files):
            if not fname.lower().endswith(".gguf"):
                continue
            if "mmproj" in fname.lower():
                continue
            info = _parse_gguf(os.path.join(root, fname))
            results.append(info)
    return results


def find_mmproj(model_path: str) -> str:
    """在模型同目录下查找 mmproj 文件，找到返回路径，否则返回空字符串"""
    directory = os.path.dirname(model_path)
    for fname in os.listdir(directory):
        if "mmproj" in fname.lower() and fname.lower().endswith(".gguf"):
            return os.path.join(directory, fname)
    return ""


def _parse_gguf(path: str) -> ModelInfo:
    """解析 GGUF 文件头，提取量化类型和参数量"""
    name = os.path.splitext(os.path.basename(path))[0]
    file_size = os.path.getsize(path)
    info = ModelInfo(path=path, name=name, file_size=file_size)

    try:
        with open(path, "rb") as f:
            magic = f.read(4)
            if magic != _GGUF_MAGIC:
                info.quant_type = _quant_from_name(name)
                return info

            version = struct.unpack("<I", f.read(4))[0]
            if version not in (2, 3):
                return info

            tensor_count = struct.unpack("<Q", f.read(8))[0]
            kv_count = struct.unpack("<Q", f.read(8))[0]

            # 读取 metadata key-value 对
            meta = _read_metadata(f, kv_count)

        arch = meta.get("general.architecture", "")
        info.architecture = arch

        # 量化类型：优先从 file_type 推断，其次从文件名推断
        file_type = meta.get("general.file_type")
        if isinstance(file_type, int):
            info.quant_type = _quant_from_file_type(file_type)
        if not info.quant_type:
            info.quant_type = _quant_from_name(name)

        # 参数量：优先从 general.size_label（如 "752M" / "7.6B" / "35B-A3B"）
        size_label = meta.get("general.size_label", "")
        if isinstance(size_label, str) and size_label:
            info.size_label = size_label
            info.param_count = _parse_size_label(size_label)
        # context_length
        ctx_key = f"{arch}.context_length" if arch else ""
        if ctx_key and ctx_key in meta:
            info.context_length = int(meta[ctx_key])
        elif "llama.context_length" in meta:
            info.context_length = int(meta["llama.context_length"])

        # block_count（Transformer 层数，即 --n-gpu-layers 的有效上限）
        blk_key = f"{arch}.block_count" if arch else ""
        if blk_key and blk_key in meta:
            info.block_count = int(meta[blk_key])

        # 兜底：metadata 中的 parameter_count
        if info.param_count == 0:
            param_key = f"{arch}.parameter_count" if arch else ""
            if param_key and param_key in meta:
                info.param_count = int(meta[param_key])
            elif "general.parameter_count" in meta:
                info.param_count = int(meta["general.parameter_count"])
            else:
                for k, v in meta.items():
                    if k.endswith(".parameter_count") and isinstance(v, int) and v > 0:
                        info.param_count = v
                        break

    except Exception:
        pass

    return info


def _read_metadata(f, kv_count: int) -> dict:
    """读取 GGUF metadata，返回 {key: value} 字典"""
    meta = {}
    _INTERESTING = {"general.architecture", "general.size_label",
                    "general.parameter_count", "general.quantization_version",
                    "general.file_type"}
    for _ in range(kv_count):
        key = _read_string(f)
        vtype = struct.unpack("<I", f.read(4))[0]
        value = _read_value(f, vtype)
        if (key in _INTERESTING
                or key.endswith(".parameter_count")
                or key.endswith(".context_length")
                or key.endswith(".block_count")):
            meta[key] = value
        if key == "general.architecture" and isinstance(value, str):
            _INTERESTING.add(f"{value}.parameter_count")
            _INTERESTING.add(f"{value}.context_length")
            _INTERESTING.add(f"{value}.block_count")
    return meta


def _read_string(f) -> str:
    length = struct.unpack("<Q", f.read(8))[0]
    return f.read(length).decode("utf-8", errors="replace")


def _read_value(f, vtype: int):
    if vtype == 8:  # string
        return _read_string(f)
    if vtype == 9:  # array
        elem_type = struct.unpack("<I", f.read(4))[0]
        count = struct.unpack("<Q", f.read(8))[0]
        for _ in range(count):
            _read_value(f, elem_type)
        return None
    size = _VTYPE_SIZES.get(vtype)
    if size is None:
        raise ValueError(f"unknown vtype {vtype}")
    data = f.read(size)
    fmt = {1: "b", 0: "B", 2: "H", 3: "h", 4: "I", 5: "i",
           6: "f", 7: "?", 10: "Q", 11: "q", 12: "d"}.get(vtype, "B" * size)
    if len(fmt) == 1:
        return struct.unpack(f"<{fmt}", data)[0]
    return data


def _quant_from_name(name: str) -> str:
    """从文件名中提取量化类型，如 'model-Q4_K_M.gguf' → 'Q4_K_M'"""
    upper = name.upper()
    for q in sorted(_QUANT_NAMES.values(), key=len, reverse=True):
        if q in upper:
            return q
    return ""


# general.file_type → 量化类型映射（来源：llama.cpp llama_ftype 枚举）
_FILE_TYPE_MAP: dict[int, str] = {
    0: "F32",
    1: "F16",
    2: "Q4_0",
    3: "Q4_1",
    7: "Q8_0",
    8: "Q5_0",
    9: "Q5_1",
    10: "Q2_K",
    11: "Q3_K_S",
    12: "Q3_K_M",
    13: "Q3_K_L",
    14: "Q4_K_S",
    15: "Q4_K_M",
    16: "Q5_K_S",
    17: "Q5_K_M",
    18: "Q6_K",
    19: "IQ2_XXS",
    20: "IQ2_XS",
    21: "Q2_K_S",
    22: "IQ3_XS",
    23: "IQ3_XXS",
    24: "IQ1_S",
    25: "IQ4_NL",
    26: "IQ3_S",
    27: "IQ3_M",
    28: "IQ2_S",
    29: "IQ2_M",
    30: "IQ4_XS",
    31: "IQ1_M",
    32: "BF16",
    36: "TQ1_0",
    37: "TQ2_0",
    38: "MXFP4_MOE",
    39: "NVFP4",
    40: "Q1_0",
}


def _quant_from_file_type(file_type: int) -> str:
    """从 general.file_type 推断量化类型"""
    return _FILE_TYPE_MAP.get(file_type, "")


def _parse_size_label(label: str) -> int:
    """解析 size_label 字符串为参数量，如 '752M' → 752_000_000, '7.6B' → 7_600_000_000"""
    label = label.strip().upper()
    multiplier = 1
    if label.endswith("B"):
        multiplier = 1_000_000_000
        num = label[:-1]
    elif label.endswith("M"):
        multiplier = 1_000_000
        num = label[:-1]
    elif label.endswith("K"):
        multiplier = 1_000
        num = label[:-1]
    else:
        try:
            return int(label)
        except ValueError:
            return 0
    try:
        return int(float(num) * multiplier)
    except ValueError:
        return 0


def format_size(n: int) -> str:
    """字节数格式化为人类可读"""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def format_params(n: int) -> str:
    """参数量格式化，如 7123456789 → '7.1B'"""
    if n <= 0:
        return "未知"
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.0f}M"
    return str(n)
