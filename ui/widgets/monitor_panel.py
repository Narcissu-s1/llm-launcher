"""运行时监控面板：GPU/内存/请求状态"""

import json
import logging
import subprocess
import threading
import urllib.request
from typing import Any

import psutil
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

logger = logging.getLogger(__name__)


class MonitorPanel(Horizontal):
    """运行时监控面板"""

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self._gpu_available: bool | None = None  # None = 未检测
        self._monitoring_active = False
        self._thread: threading.Thread | None = None
        self._pid: int | None = None
        self._port: int = 8080
        self._proc: psutil.Process | None = None

    def compose(self) -> ComposeResult:
        yield Static("GPU: --", id="mon_gpu")
        yield Static("CPU: --", id="mon_cpu")
        yield Static("内存: --", id="mon_ram")
        yield Static("Slots: --/--", id="mon_slots")

    def _detect_gpu(self) -> None:
        """检测 nvidia-smi 是否可用"""
        try:
            subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, timeout=2, check=True,
            )
            self._gpu_available = True
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
            self._gpu_available = False

    def start_monitoring(self, pid: int, port: int) -> None:
        """启动监控轮询"""
        self._pid = pid
        self._port = port
        try:
            self._proc = psutil.Process(pid)
            self._proc.cpu_percent()
        except psutil.NoSuchProcess:
            self._proc = None

        if self._gpu_available is None:
            self._detect_gpu()
            if not self._gpu_available:
                self.query_one("#mon_gpu", Static).display = False

        if not self._monitoring_active:
            self._monitoring_active = True
            self._thread = threading.Thread(target=self._poll_loop, daemon=True)
            self._thread.start()

    def stop_monitoring(self) -> None:
        """停止监控轮询"""
        self._monitoring_active = False
        if self._thread is not None:
            self._thread.join(timeout=3)

    def _poll_loop(self) -> None:
        """后台轮询线程"""
        while self._monitoring_active:
            try:
                self._collect_and_update()
            except Exception:
                logger.debug("监控采集异常", exc_info=True)
            threading.Event().wait(2.0)

    def _collect_and_update(self) -> None:
        """采集数据并更新 UI"""
        gpu_text = self._collect_gpu()
        cpu_text = self._collect_cpu()
        ram_text = self._collect_ram()
        slots_text = self._collect_slots()

        def update():
            try:
                if gpu_text:
                    self.query_one("#mon_gpu", Static).update(gpu_text)
                self.query_one("#mon_cpu", Static).update(cpu_text)
                self.query_one("#mon_ram", Static).update(ram_text)
                self.query_one("#mon_slots", Static).update(slots_text)
            except Exception:
                logger.debug("监控更新失败（控件可能已销毁）")

        self.app.call_from_thread(update)

    def _collect_gpu(self) -> str:
        """采集 GPU 信息"""
        if not self._gpu_available:
            return ""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2,
            )
            parts = result.stdout.strip().split(", ")
            util = parts[0].strip()
            used = self._format_bytes(int(parts[1].strip()) * 1024 * 1024)
            total = self._format_bytes(int(parts[2].strip()) * 1024 * 1024)
            return f"GPU: {util}%  {used}/{total}"
        except Exception:
            return "GPU: --"

    def _collect_cpu(self) -> str:
        """采集系统 CPU 和进程 CPU"""
        sys_cpu = psutil.cpu_percent(interval=0)
        proc_cpu = 0.0
        if self._proc:
            try:
                proc_cpu = self._proc.cpu_percent()
            except psutil.NoSuchProcess:
                self._proc = None
        return f"CPU: {sys_cpu:.0f}%({proc_cpu:.0f}%)"

    def _collect_ram(self) -> str:
        """采集系统内存和进程内存"""
        vm = psutil.virtual_memory()
        sys_used = self._format_bytes(vm.used)
        sys_total = self._format_bytes(vm.total)
        proc_text = ""
        if self._proc:
            try:
                rss = self._proc.memory_info().rss
                proc_text = f"({self._format_bytes(rss)})"
            except psutil.NoSuchProcess:
                self._proc = None
        return f"内存: {sys_used}/{sys_total}{proc_text}"

    def _collect_slots(self) -> str:
        """采集 Slots 信息"""
        try:
            url = f"http://127.0.0.1:{self._port}/slots"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=1) as resp:
                data = json.loads(resp.read())
                active = sum(
                    1 for s in data
                    if s.get("state") not in (0, "idle")
                )
                total = len(data)
                return f"Slots: {active}/{total}"
        except Exception:
            return "Slots: --/--"

    @staticmethod
    def _format_bytes(n: int) -> str:
        """格式化字节数"""
        value = float(n)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if value < 1024:
                return f"{value:.2f} {unit}"
            value /= 1024
        return f"{value:.2f} PB"
