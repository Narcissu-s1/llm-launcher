import subprocess, logging
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame, QProgressBar
from PySide6.QtCore import QThread, Signal, QTimer
import psutil

logger = logging.getLogger(__name__)

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
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                timeout=2, stderr=subprocess.DEVNULL
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
        self._lbl = QLabel(label.upper())
        self._lbl.setStyleSheet("font-size:10px;font-weight:600;color:#718096;")
        self._val = QLabel("—")
        self._val.setStyleSheet("font-family:'DM Mono',Consolas;font-size:20px;font-weight:500;")
        self._unit = unit
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(3)
        layout.addWidget(self._lbl)
        layout.addWidget(self._val)
        layout.addWidget(self._bar)

    def update(self, value_str: str, pct: int):
        self._val.setText(value_str)
        self._bar.setValue(max(0, min(100, pct)))


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
        self._cpu_card.update(f"{stats.get('cpu_sys', 0):.0f}%", int(stats.get('cpu_sys', 0)))
        mem_used = stats.get('mem_used_gb', 0)
        mem_total = stats.get('mem_total_gb', 1)
        self._ram_card.update(f"{mem_used:.1f}GB", int(stats.get('mem_pct', 0)))
        gpu_util = stats.get('gpu_util', 0)
        self._gpu_card.update(f"{gpu_util}%", gpu_util)
        vram_used = stats.get('vram_used_mb', 0) / 1024
        vram_total = stats.get('vram_total_mb', 1) / 1024
        vram_pct = int(vram_used / vram_total * 100) if vram_total > 0 else 0
        self._vram_card.update(f"{vram_used:.1f}GB", vram_pct)

    def closeEvent(self, event):
        self._worker.stop()
        super().closeEvent(event)
