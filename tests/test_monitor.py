import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock


def test_GPU检测失败时不崩溃():
    """nvidia-smi 不可用时 _collect 应返回不含 GPU 键的字典，不抛异常"""
    from ui.widgets.monitor_panel import _MonitorWorker

    worker = _MonitorWorker(lambda: None)
    with patch("subprocess.check_output", side_effect=FileNotFoundError):
        stats = worker._collect()
    assert "gpu_util" not in stats
    assert "vram_used_mb" not in stats


def test_格式化内存():
    """_format_bytes 应正确格式化"""
    from ui.widgets.monitor_panel import _format_bytes

    assert _format_bytes(1024) == "1.00 KB"
    assert _format_bytes(1024 * 1024) == "1.00 MB"
    assert _format_bytes(1024 * 1024 * 1024) == "1.00 GB"
