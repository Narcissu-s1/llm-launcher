"""GGUF 模型元数据提取工具

用法：
    python gguf_info.py <模型文件路径>
    python gguf_info.py <目录>           # 扫描目录下所有 .gguf 文件

输出：文件头信息 + 全部 metadata key-value
"""

import os
import struct
import sys

_GGUF_MAGIC = b"GGUF"

_VTYPE_SIZES = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4,
                6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
_VTYPE_NAMES = {0: "uint8", 1: "int8", 2: "uint16", 3: "int16",
                4: "uint32", 5: "int32", 6: "float32", 7: "bool",
                8: "string", 9: "array", 10: "uint64", 11: "int64", 12: "float64"}


def read_string(f) -> str:
    length = struct.unpack("<Q", f.read(8))[0]
    return f.read(length).decode("utf-8", errors="replace")


def read_value(f, vtype: int):
    if vtype == 8:  # string
        return read_string(f)
    if vtype == 9:  # array
        elem_type = struct.unpack("<I", f.read(4))[0]
        count = struct.unpack("<Q", f.read(8))[0]
        items = []
        for _ in range(min(count, 20)):  # 限制数组最多读 20 项
            items.append(read_value(f, elem_type))
        # 跳过剩余项
        for _ in range(count - min(count, 20)):
            skip_value(f, elem_type)
        return items
    size = _VTYPE_SIZES.get(vtype)
    if size is None:
        return f"UNKNOWN_VTYPE({vtype})"
    data = f.read(size)
    fmt = {1: "b", 0: "B", 2: "H", 3: "h", 4: "I", 5: "i",
           6: "f", 7: "?", 10: "Q", 11: "q", 12: "d"}.get(vtype)
    if fmt:
        return struct.unpack(f"<{fmt}", data)[0]
    return data.hex()


def skip_value(f, vtype: int):
    """跳过一个值（用于数组中超出限制的元素）"""
    if vtype == 8:
        length = struct.unpack("<Q", f.read(8))[0]
        f.read(length)
    elif vtype == 9:
        elem_type = struct.unpack("<I", f.read(4))[0]
        count = struct.unpack("<Q", f.read(8))[0]
        for _ in range(count):
            skip_value(f, elem_type)
    else:
        size = _VTYPE_SIZES.get(vtype, 0)
        if size:
            f.read(size)


def extract_gguf_metadata(path: str) -> dict | str:
    """提取 GGUF 文件的完整 metadata，返回字典或错误字符串"""
    name = os.path.basename(path)
    file_size = os.path.getsize(path)

    result = {"file": name, "file_size": file_size}

    try:
        with open(path, "rb") as f:
            magic = f.read(4)
            if magic != _GGUF_MAGIC:
                return f"{name}: 非 GGUF 文件 (magic: {magic})"

            version = struct.unpack("<I", f.read(4))[0]
            tensor_count = struct.unpack("<Q", f.read(8))[0]
            kv_count = struct.unpack("<Q", f.read(8))[0]

            result["gguf_version"] = version
            result["tensor_count"] = tensor_count
            result["kv_count"] = kv_count

            # 读取全部 metadata
            meta = {}
            for _ in range(kv_count):
                key = read_string(f)
                vtype = struct.unpack("<I", f.read(4))[0]
                value = read_value(f, vtype)
                meta[key] = {"type": _VTYPE_NAMES.get(vtype, f"type_{vtype}"), "value": value}
            result["metadata"] = meta

    except Exception as e:
        return f"{name}: 解析失败 - {e}"

    return result


def format_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def print_result(info: dict):
    print(f"{'=' * 60}")
    print(f"文件: {info['file']}")
    print(f"大小: {format_size(info['file_size'])}")
    print(f"GGUF 版本: {info.get('gguf_version', '?')}")
    print(f"张量数: {info.get('tensor_count', '?')}")
    print(f"Metadata 条目: {info.get('kv_count', '?')}")

    meta = info.get("metadata", {})
    if not meta:
        print("  (无 metadata)")
        return

    # 按前缀分组
    groups: dict[str, list] = {}
    for key, entry in meta.items():
        prefix = key.split(".")[0] if "." in key else "(root)"
        groups.setdefault(prefix, []).append((key, entry))

    for group_name in sorted(groups.keys()):
        print(f"\n  [{group_name}]")
        for key, entry in groups[group_name]:
            vtype = entry["type"]
            value = entry["value"]
            print(f"    {key} ({vtype}): {value}")


def main():
    if len(sys.argv) < 2:
        print("用法: python gguf_info.py <文件或目录>")
        sys.exit(1)

    target = sys.argv[1]
    if os.path.isfile(target):
        info = extract_gguf_metadata(target)
        if isinstance(info, str):
            print(info)
        else:
            print_result(info)
    elif os.path.isdir(target):
        for fname in sorted(os.listdir(target)):
            if fname.lower().endswith(".gguf"):
                path = os.path.join(target, fname)
                info = extract_gguf_metadata(path)
                if isinstance(info, str):
                    print(info)
                else:
                    print_result(info)
                print()
    else:
        print(f"路径不存在: {target}")
        sys.exit(1)


if __name__ == "__main__":
    main()
