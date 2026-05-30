import subprocess, logging
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame, QProgressBar
from PySide6.QtCore import QThread, Signal, QTimer
import psutil

logger = logging.getLogger(__name__)


def _format_bytes(n: int) -> str:
    """将字节数格式化为人类可读字符串。"""
    if n >= 1024 ** 3:
        return f"{n / 1024 ** 3:.2f} GB"
    if n >= 1024 ** 2:
        return f"{n / 1024 ** 2:.2f} MB"
    if n >= 1024:
        return f"{n / 1024:.2f} KB"
    return f"{n} B"

class _MonitorWorker(QThread):
    stats_ready = Signal(dict)

    def __init__(self, pid_getter):
        super().__init__()
        self._pid_getter = pid_getter
        self._running = False

    def run(self):
        self._running = True
        while self._running:
            self.stats_ready.emit(self._collect())
            self.msleep(1000)

    def stop(self):
        self._running = False
        self.wait(2000)

    def _collect(self) -> dict:
        stats = {}
        # CPU
        stats["cpu_sys"] = psutil.cpu_percent(interval=None)
        pid = self._pid_getter()
        if pid:
            try:
                proc = psutil.Process(pid)
                stats["cpu_proc"] = proc.cpu_percent(interval=None) / psutil.cpu_count()
                stats["mem_proc_mb"] = proc.memory_info().rss / 1024 / 1024
            except psutil.NoSuchProcess:
                pass
        # RAM
        vm = psutil.virtual_memory()
        stats["mem_used_gb"] = vm.used / 1024**3
        stats["mem_total_gb"] = vm.total / 1024**3
        stats["mem_pct"] = vm.percent
        # GPU
        try:
            _flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                timeout=2, stderr=subprocess.DEVNULL,
                creationflags=_flags,
            ).decode().strip()
            parts = out.split(",")
            stats["gpu_util"] = int(parts[0].strip())
            stats["vram_used_mb"] = int(parts[1].strip())
            stats["vram_total_mb"] = int(parts[2].strip())
        except Exception:
            pass
        return stats


class _StatCard(QFrame):
    def __init__(self, label: str, unit: str = ""):
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)
        self._lbl = QLabel(label.upper())
        self._lbl.setStyleSheet("font-size:10px;font-weight:600;color:#718096;")
        self._val = QLabel("—")
        self._val.setStyleSheet("font-family:'DM Mono',Consolas;font-size:18px;font-weight:600;")
        self._sub = QLabel("")
        self._sub.setStyleSheet("font-size:11px;color:#4a5568;font-family:'DM Mono',Consolas;font-weight:500;")
        self._unit = unit
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(5)
        layout.addWidget(self._lbl)
        layout.addWidget(self._val)
        layout.addWidget(self._sub)
        layout.addWidget(self._bar)

    def update(self, value_str: str, pct: int, sub: str = ""):
        self._val.setText(value_str)
        pct = max(0, min(100, pct))
        self._bar.setValue(pct)
        bar_color = "#e53e3e" if pct >= 80 else "#1a9e6e"
        self._bar.setStyleSheet(
            f"QProgressBar{{background:#e2e8f0;border-radius:2px;}}"
            f"QProgressBar::chunk{{background:{bar_color};border-radius:2px;}}"
        )
        self._sub.setText(sub)
        self._sub.setVisible(bool(sub))


class MonitorPanel(QWidget):
    def __init__(self, supervisor):
        super().__init__()
        self._supervisor = supervisor
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        self._cpu_card = _StatCard("CPU", "%")
        self._ram_card = _StatCard("RAM", "GB")
        self._gpu_card = _StatCard("GPU", "%")
        self._vram_card = _StatCard("VRAM", "GB")
        for c in [self._cpu_card, self._ram_card, self._gpu_card, self._vram_card]:
            layout.addWidget(c)

        self._worker = _MonitorWorker(lambda: self._supervisor.pid)
        self._worker.stats_ready.connect(self._update)
        self._worker.start()

    def _update(self, stats: dict):
        cpu_sys = stats.get("cpu_sys", 0)
        cpu_proc = stats.get("cpu_proc")
        cpu_sub = f"进程 {cpu_proc:.1f}%" if cpu_proc is not None else ""
        self._cpu_card.update(f"{cpu_sys:.0f}%", int(cpu_sys), cpu_sub)

        mem_used = stats.get("mem_used_gb", 0)
        mem_total = stats.get("mem_total_gb", 1)
        mem_pct = int(stats.get("mem_pct", 0))
        mem_proc_mb = stats.get("mem_proc_mb")
        ram_sub = f"进程 {mem_proc_mb:.0f}MB" if mem_proc_mb is not None else ""
        self._ram_card.update(f"{mem_used:.1f}/{mem_total:.1f}GB", mem_pct, ram_sub)

        gpu_util = stats.get("gpu_util", 0)
        self._gpu_card.update(f"{gpu_util}%", gpu_util)

        vram_used = stats.get("vram_used_mb", 0) / 1024
        vram_total = stats.get("vram_total_mb", 1) / 1024
        vram_pct = int(vram_used / vram_total * 100) if vram_total > 0 else 0
        self._vram_card.update(f"{vram_used:.1f}/{vram_total:.1f}GB", vram_pct)

    def closeEvent(self, event):
        self._worker.stop()
        super().closeEvent(event)
