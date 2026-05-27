import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock


def test_GPU检测失败时隐藏():
    """nvidia-smi 不可用时应标记 _gpu_available = False"""
    from ui.widgets.monitor_panel import MonitorPanel

    panel = MonitorPanel()
    # 模拟 nvidia-smi 不存在
    with patch("subprocess.run", side_effect=FileNotFoundError):
        panel._detect_gpu()
    assert panel._gpu_available is False


def test_格式化内存():
    """_format_bytes 应正确格式化"""
    from ui.widgets.monitor_panel import MonitorPanel

    assert MonitorPanel._format_bytes(1024) == "1.00 KB"
    assert MonitorPanel._format_bytes(1024 * 1024) == "1.00 MB"
    assert MonitorPanel._format_bytes(1024 * 1024 * 1024) == "1.00 GB"
