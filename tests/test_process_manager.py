# tests/test_process_manager.py
"""ProcessSupervisor 单元测试"""

import sys
import os
import time
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.events import EventBus
from core.process_manager import ProcessSupervisor, ProcessStatus


def test_初始状态为stopped():
    """新创建的 supervisor 状态应为 stopped"""
    bus = EventBus()
    sup = ProcessSupervisor(bus)
    assert sup.status() == ProcessStatus.STOPPED


def test_start成功emit_starting事件():
    """start 应 emit status_changed: starting（事件在启动子进程前即发送）"""
    bus = EventBus()
    events = []
    bus.on("status_changed", lambda **d: events.append(d))

    sup = ProcessSupervisor(bus)

    mock_process = MagicMock()
    mock_process.pid = 12345
    # stdout 作为可迭代对象（Queue reader 线程遍历它）
    mock_process.stdout = []
    # poll 返回非 None 表示进程已退出，让轮询循环快速结束
    mock_process.poll.return_value = 0

    with patch("subprocess.Popen", return_value=mock_process), \
         patch("socket.socket") as mock_socket_class:
        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 1  # 非0 = 端口空闲
        mock_socket_class.return_value = mock_socket

        sup.start({
            "model_path": "test.gguf",
            "port": 8080,
            "host": "127.0.0.1",
            "context_size": 4096,
            "n_gpu_layers": 0,
            "parallel": 1,
        })

        # 等待后台线程完成
        time.sleep(0.3)

    # start() 内部发送 starting 事件
    status_events = [e for e in events if e.get("status")]
    assert len(status_events) >= 1
    assert status_events[0]["status"] == "starting"


def test_stop终止进程():
    """stop 应调用 terminate() 和 wait()"""
    bus = EventBus()
    sup = ProcessSupervisor(bus)

    mock_proc = MagicMock()
    mock_proc.pid = 12345
    mock_proc.is_running.return_value = True

    with patch("psutil.Process", return_value=mock_proc):
        sup._pid = 12345
        sup._status = ProcessStatus.RUNNING
        sup.stop()

    mock_proc.terminate.assert_called_once()
    mock_proc.wait.assert_called_once_with(timeout=3)


def test_PID不存在时切换为crashed():
    """轮询检测到 PID 不存在时应 emit crashed 事件"""
    bus = EventBus()
    events = []
    bus.on("status_changed", lambda **d: events.append(d))

    sup = ProcessSupervisor(bus)
    sup._pid = 99999
    sup._status = ProcessStatus.RUNNING

    with patch("psutil.pid_exists", return_value=False):
        sup._check_process()

    crashed_events = [e for e in events if e.get("status") == "crashed"]
    assert len(crashed_events) == 1
    assert crashed_events[0]["exit_code"] == -1


def test_高级参数_KVCache():
    """KV Cache 参数应正确拼接到命令行"""
    bus = EventBus()
    sup = ProcessSupervisor(bus)

    params = {
        "model_path": "test.gguf",
        "server_path": "llama-server",
        "port": 8080,
        "host": "127.0.0.1",
        "context_size": 4096,
        "n_gpu_layers": 0,
        "parallel": 1,
        "cache_type_k": "q8_0",
        "flash_attn": True,
    }

    cmd = sup._build_command(params)
    assert "-ctk" in cmd
    assert cmd[cmd.index("-ctk") + 1] == "q8_0"
    assert "-fa" in cmd


def test_高级参数_采样():
    """采样参数非默认值时应拼接到命令行"""
    bus = EventBus()
    sup = ProcessSupervisor(bus)

    params = {
        "model_path": "test.gguf",
        "server_path": "llama-server",
        "port": 8080,
        "host": "127.0.0.1",
        "context_size": 4096,
        "n_gpu_layers": 0,
        "parallel": 1,
        "temp": 0.7,
        "top_k": 20,
    }

    cmd = sup._build_command(params)
    assert "--temp" in cmd
    assert cmd[cmd.index("--temp") + 1] == "0.7"
    assert "--top-k" in cmd
    assert cmd[cmd.index("--top-k") + 1] == "20"


def test_高级参数_默认值不拼接():
    """默认值参数不应出现在命令行中"""
    bus = EventBus()
    sup = ProcessSupervisor(bus)

    params = {
        "model_path": "test.gguf",
        "server_path": "llama-server",
        "port": 8080,
        "host": "127.0.0.1",
        "context_size": 4096,
        "n_gpu_layers": 0,
        "parallel": 1,
        # 所有高级参数都是默认值
    }

    cmd = sup._build_command(params)
    assert "-ctk" not in cmd
    assert "-fa" not in cmd
    assert "--temp" not in cmd
    assert "--api-key" not in cmd


def test_高级参数_安全():
    """API Key 非空时应拼接"""
    bus = EventBus()
    sup = ProcessSupervisor(bus)

    params = {
        "model_path": "test.gguf",
        "server_path": "llama-server",
        "port": 8080,
        "host": "127.0.0.1",
        "context_size": 4096,
        "n_gpu_layers": 0,
        "parallel": 1,
        "api_key": "my-secret-key",
    }

    cmd = sup._build_command(params)
    assert "--api-key" in cmd
    assert cmd[cmd.index("--api-key") + 1] == "my-secret-key"
