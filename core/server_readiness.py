"""llama-server 启动就绪日志的兼容判断。"""

_READY_LOG_MARKERS = (
    "server is listening",  # 旧版 llama.cpp
    "listening on",         # 新版 llama.cpp
)


def is_server_ready_log(line: str) -> bool:
    """返回日志行是否表示 llama-server 已开始监听。"""
    line_lower = line.lower()
    return any(marker in line_lower for marker in _READY_LOG_MARKERS)
