# core/process_manager.py
"""llama-server 进程生命周期管理：启动、停止、存活检测"""

import atexit
import logging
import os
import socket
import subprocess
import threading
import time
from collections import deque
from enum import Enum
from queue import Queue, Empty

import psutil

from core.events import EventBus, EVENT_STATUS_CHANGED, EVENT_LOG_LINE

logger = logging.getLogger(__name__)


class ProcessStatus(str, Enum):
    """进程状态枚举"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    CRASHED = "crashed"


class ProcessError(Exception):
    """进程操作异常基类"""
    pass


class PortInUseError(ProcessError):
    """端口被占用异常"""
    def __init__(self, port: int):
        self.port = port
        super().__init__(f"端口 {port} 已被占用，请更换端口")


class ProcessSupervisor:
    """llama-server 进程生命周期管理器"""

    _LOG_BUFFER_SIZE = 50      # 崩溃诊断保留的日志行数
    _POLL_INTERVAL = 1.0       # 轮询间隔（秒）
    _STOP_GRACE_PERIOD = 3     # SIGTERM 优雅终止等待时间

    def __init__(self, event_bus: EventBus):
        """初始化进程管理器

        Args:
            event_bus: 事件总线，用于通知 UI 状态变化
        """
        self._event_bus = event_bus
        self._pid: int | None = None
        self._status = ProcessStatus.STOPPED
        self._process: subprocess.Popen | None = None
        self._poll_thread: threading.Thread | None = None
        self._poll_stop = threading.Event()
        self._last_logs: deque[str] = deque(maxlen=self._LOG_BUFFER_SIZE)
        atexit.register(self._force_kill_on_exit)

    def status(self) -> ProcessStatus:
        """获取当前进程状态"""
        return self._status

    @property
    def pid(self) -> int | None:
        """获取当前管理的 PID"""
        return self._pid

    def start(self, params: dict) -> int:
        """启动 llama-server 进程

        Args:
            params: 参数字典，包含 model_path, port, host 等

        Returns:
            子进程 PID

        Raises:
            ProcessError: 服务器已在运行
            PortInUseError: 端口被占用
            ProcessError: 启动失败（文件不存在、权限不足等）
        """
        if self._status in (ProcessStatus.STARTING, ProcessStatus.RUNNING):
            raise ProcessError("服务器已在运行中，请先停止")

        port = params.get("port", 8080)
        self._check_port(port)

        cmd = self._build_command(params)
        logger.info("启动命令: %s", " ".join(cmd))
        self._event_bus.emit(EVENT_LOG_LINE, line=">>> 启动命令:")
        for arg in cmd:
            self._event_bus.emit(EVENT_LOG_LINE, line=f"    {arg}")

        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
            )
        except FileNotFoundError:
            raise ProcessError(
                f"找不到 {params.get('server_path', 'llama-server')}，"
                f"请确认 llama.cpp 已安装且路径正确"
            )
        except PermissionError:
            raise ProcessError("没有权限执行 llama-server.exe，请检查文件权限")

        self._pid = self._process.pid
        self._set_status(ProcessStatus.STARTING)
        self._last_logs.clear()

        self._poll_stop.clear()
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

        return self._pid

    def stop(self) -> None:
        """停止 llama-server 进程

        优雅终止（SIGTERM）→ 等待 → 强杀（SIGKILL）
        """
        if self._pid is None:
            return

        # 先通知轮询线程停止
        self._poll_stop.set()

        try:
            proc = psutil.Process(self._pid)
            if proc.is_running():
                proc.terminate()
                try:
                    proc.wait(timeout=self._STOP_GRACE_PERIOD)
                except psutil.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        finally:
            self._pid = None
            self._process = None
            self._set_status(ProcessStatus.STOPPED)

    def _force_kill_on_exit(self) -> None:
        """atexit 回调：Python 退出时强杀子进程，防止孤儿进程占用端口"""
        if self._process is not None:
            try:
                self._process.kill()
            except Exception:
                pass

    def _check_port(self, port: int) -> None:
        """检查端口是否可用（socket bind 探测）

        Args:
            port: 要检查的端口号

        Raises:
            PortInUseError: 端口已被占用
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        try:
            result = sock.connect_ex(("127.0.0.1", port))
            if result == 0:
                raise PortInUseError(port)
        finally:
            sock.close()

    def _build_command(self, params: dict) -> list[str]:
        """根据参数构建 llama-server 命令行

        Windows 下路径中的反斜杠 + 中文字符在 subprocess 传参时可能被错误转码，
        统一转为正斜杠格式以兼容。
        """
        from pathlib import Path

        def _safe_path(p: str) -> str:
            """将路径转为正斜杠格式，避免 Windows 编码问题"""
            if not p:
                return p
            return Path(p).as_posix()

        server_path = _safe_path(params.get("server_path", "llama-server"))
        router_mode = params.get("router_mode", False)

        cmd = [server_path]

        if router_mode:
            # 路由模式：用 --models-dir 替代 -m，服务器自动扫描目录中的 GGUF
            models_dir = _safe_path(params.get("models_dir", ""))
            if models_dir:
                cmd.extend(["--models-dir", models_dir])
        else:
            # 单模型模式
            model_path = _safe_path(params["model_path"])
            cmd.extend(["-m", model_path])
            mmproj = params.get("mmproj_path", "")
            if mmproj and os.path.isfile(mmproj):
                cmd.extend(["--mmproj", _safe_path(mmproj)])

        cmd.extend([
            "--host", str(params.get("host", "127.0.0.1")),
            "--port", str(params.get("port", 8080)),
            "-c", str(params.get("context_size", 4096)),
            "--n-gpu-layers", str(params.get("n_gpu_layers", 0)),
            "-np", str(params.get("parallel", 1)),
        ])

        # Phase 2 - KV Cache 与显存
        if params.get("cache_type_k", "f16") != "f16":
            cmd.extend(["-ctk", params["cache_type_k"]])
        if params.get("cache_type_v", "f16") != "f16":
            cmd.extend(["-ctv", params["cache_type_v"]])
        if not params.get("kv_unified", True):
            cmd.append("--no-kv-unified")
        if params.get("no_kv_offload", False):
            cmd.append("--no-kv-offload")
        fa = params.get("flash_attn", "auto")
        if isinstance(fa, bool):
            fa = "on" if fa else "off"
        if fa != "auto":
            cmd.extend(["-fa", str(fa)])
        if not params.get("cache_prompt", True):
            cmd.append("--no-cache-prompt")
        if not params.get("cache_idle_slots", True):
            cmd.append("--no-cache-idle-slots")
        if params.get("cache_ram", 8192) != 8192:
            cmd.extend(["--cache-ram", str(params["cache_ram"])])

        # Phase 2 - 推理速度
        if params.get("threads", -1) != -1:
            cmd.extend(["-t", str(params["threads"])])
        if params.get("threads_batch", -1) != -1:
            cmd.extend(["-tb", str(params["threads_batch"])])
        if params.get("batch_size", 2048) != 2048:
            cmd.extend(["-b", str(params["batch_size"])])
        if params.get("ubatch_size", 512) != 512:
            cmd.extend(["-ub", str(params["ubatch_size"])])
        if params.get("threads_http", -1) != -1:
            cmd.extend(["--threads-http", str(params["threads_http"])])
        if params.get("no_warmup", False):
            cmd.append("--no-warmup")
        if not params.get("jinja", True):
            cmd.append("--no-jinja")
        if params.get("context_shift", False):
            cmd.append("--context-shift")
        if params.get("keep", 0) > 0:
            cmd.extend(["--keep", str(params["keep"])])
        if params.get("poll") is not None and params["poll"] != 50:
            cmd.extend(["--poll", str(params["poll"])])

        # Phase 2 - 采样参数
        if abs(params.get("temp", 0.60) - 0.60) > 0.001:
            cmd.extend(["--temp", str(params["temp"])])
        if params.get("top_k", 40) != 40:
            cmd.extend(["--top-k", str(params["top_k"])])
        if abs(params.get("top_p", 0.90) - 0.90) > 0.001:
            cmd.extend(["--top-p", str(params["top_p"])])
        if abs(params.get("min_p", 0.05) - 0.05) > 0.001:
            cmd.extend(["--min-p", str(params["min_p"])])
        if abs(params.get("repeat_penalty", 1.10) - 1.10) > 0.001:
            cmd.extend(["--repeat-penalty", str(params["repeat_penalty"])])
        if params.get("seed", -1) != -1:
            cmd.extend(["-s", str(params["seed"])])
        if params.get("n_predict", -1) != -1:
            cmd.extend(["-n", str(params["n_predict"])])
        if params.get("ignore_eos", False):
            cmd.append("--ignore-eos")

        # Phase 2 - 思考模式
        if params.get("reasoning", "auto") != "auto":
            cmd.extend(["-rea", params["reasoning"]])
        if params.get("reasoning_format") and params["reasoning_format"] != "auto":
            cmd.extend(["--reasoning-format", params["reasoning_format"]])
        if params.get("reasoning_budget", -1) != -1:
            cmd.extend(["--reasoning-budget", str(params["reasoning_budget"])])

        # Phase 2 - 多模态
        if not params.get("mmproj_offload", True):
            cmd.append("--no-mmproj-offload")
        if (params.get("image_min_tokens") or 0) > 0:
            cmd.extend(["--image-min-tokens", str(params["image_min_tokens"])])
        if (params.get("image_max_tokens") or 0) > 0:
            cmd.extend(["--image-max-tokens", str(params["image_max_tokens"])])

        # Phase 2 - 安全与访问控制
        if params.get("api_key", ""):
            cmd.extend(["--api-key", params["api_key"]])
        if params.get("timeout", 1200) != 1200:
            cmd.extend(["--timeout", str(params["timeout"])])
        if params.get("metrics", False):
            cmd.append("--metrics")
        if not params.get("slots", True):
            cmd.append("--no-slots")
        if params.get("tools", False):
            cmd.extend(["--tools", "all"])

        # 投机解码
        if params.get("spec_type", "none") != "none":
            cmd.extend(["--spec-type", params["spec_type"]])
        if params.get("spec_draft_n_max", 3) != 3:
            cmd.extend(["--spec-draft-n-max", str(params["spec_draft_n_max"])])
        if params.get("spec_draft_n_min", 0) != 0:
            cmd.extend(["--spec-draft-n-min", str(params["spec_draft_n_min"])])
        if abs(params.get("spec_draft_p_split", 0.1) - 0.1) > 0.001:
            cmd.extend(["--spec-draft-p-split", str(params["spec_draft_p_split"])])
        if abs(params.get("spec_draft_p_min", 0.0) - 0.0) > 0.001:
            cmd.extend(["--spec-draft-p-min", str(params["spec_draft_p_min"])])

        return cmd

    def _poll_loop(self) -> None:
        """后台轮询线程：读取 stdout + 定期检测进程存活

        使用 Queue + 专用读线程实现跨平台非阻塞 IO。
        主循环每 POLL_INTERVAL 秒检查一次进程状态。
        """
        line_queue: Queue = Queue()

        def reader():
            """专用读线程：逐行读取 stdout 放入队列"""
            try:
                for line in self._process.stdout:
                    if self._poll_stop.is_set():
                        break
                    line_queue.put(line)
            except (ValueError, OSError):
                pass  # pipe 已关闭

        reader_thread = threading.Thread(target=reader, daemon=True)
        reader_thread.start()

        while not self._poll_stop.is_set():
            # 从队列中取出所有待处理的行（非阻塞）
            while True:
                try:
                    line = line_queue.get_nowait()
                except Empty:
                    break  # 队列已空

                line = line.rstrip()
                self._last_logs.append(line)

                self._event_bus.emit(EVENT_LOG_LINE, line=line)

                # 检测启动完成标志
                if self._status == ProcessStatus.STARTING and "server is listening" in line.lower():
                    self._set_status(ProcessStatus.RUNNING, pid=self._pid)

            # 检测子进程是否已退出
            poll_result = self._process.poll()
            if poll_result is not None:
                # 队列中可能还有残留行，全部读取
                while True:
                    try:
                        line = line_queue.get_nowait()
                        line = line.rstrip()
                        self._last_logs.append(line)
                        self._event_bus.emit(EVENT_LOG_LINE, line=line)
                    except Empty:
                        break

                if self._status == ProcessStatus.RUNNING:
                    self._set_status(
                        ProcessStatus.CRASHED,
                        exit_code=poll_result,
                        last_logs=list(self._last_logs),
                    )
                break

            # 定期检测进程存活（处理外部 kill 的情况）
            self._check_process()
            if self._status == ProcessStatus.CRASHED:
                break

            # 等待 POLL_INTERVAL 秒后继续下一轮
            self._poll_stop.wait(timeout=self._POLL_INTERVAL)

        reader_thread.join(timeout=1)

    def _check_process(self) -> None:
        """单次 PID 存活检查

        当进程被外部 kill（任务管理器等）时，poll() 可能不会立即返回，
        此方法通过 PID 检查提供额外的检测手段。
        """
        if self._pid is None:
            return
        if self._status == ProcessStatus.RUNNING and not psutil.pid_exists(self._pid):
            self._set_status(
                ProcessStatus.CRASHED,
                exit_code=-1,
                last_logs=list(self._last_logs),
            )

    def _set_status(self, status: ProcessStatus, **extra) -> None:
        """设置状态并发送事件

        Args:
            status: 新状态
            **extra: 额外事件数据（如 exit_code）
        """
        old_status = self._status
        self._status = status
        event_data = {"old_status": old_status.value, "status": status.value}
        event_data.update(extra)
        self._event_bus.emit(EVENT_STATUS_CHANGED, **event_data)
