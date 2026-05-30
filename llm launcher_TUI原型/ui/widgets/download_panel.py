# ui/widgets/download_panel.py
"""模型下载面板：支持 HuggingFace / HF镜像 / ModelScope"""

import os

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Checkbox, DataTable, Input, Label, ProgressBar, RichLog, Static

from core.hf_downloader import DownloadTask, HFDownloader, RemoteFile, HF_ENDPOINT, HF_MIRROR_ENDPOINT
from core.model_library import format_size


class DownloadPanel(Vertical):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._downloader = HFDownloader()
        self._plain_lines: list[str] = []
        self._scanned_files: list[RemoteFile] = []  # 扫描结果

    def compose(self) -> ComposeResult:
        yield Label("远程模型下载", id="dl-title")
        with Horizontal(classes="input-row"):
            yield Input(
                placeholder="Repo ID（用户名/仓库名），如 HF: bartowski/Qwen3-8B-GGUF  |  ModelScope: Qwen/Qwen3-8B-GGUF",
                id="dl_repo_id",
            )
        with Horizontal(classes="input-row"):
            yield Input(placeholder="保存目录...", id="dl_save_dir")
            yield Button("浏览", id="btn_dl_browse", variant="default")
        with Horizontal(classes="input-row"):
            yield Input(
                placeholder="Token（公开模型留空；HF Token 在 huggingface.co → Settings → Access Tokens 获取）",
                id="dl_token",
                password=True,
            )
        with Horizontal(id="dl-options-row"):
            yield Checkbox("HuggingFace", id="src_hf", value=True)
            yield Checkbox("HF 镜像", id="src_hf_mirror")
            yield Checkbox("ModelScope", id="src_ms")
            yield Checkbox("跳过 SSL 验证", id="dl_skip_ssl")
        with Horizontal(id="dl-action-row"):
            yield Button("扫描文件列表", id="btn_dl_scan", variant="primary")
            yield Button("下载选中", id="btn_dl_start", variant="success", disabled=True)
            yield Button("取消", id="btn_dl_cancel", variant="error", disabled=True)
        # 文件列表表格
        yield DataTable(id="dl_file_table", cursor_type="row", zebra_stripes=True)
        yield Static("", id="dl_current_file")
        yield ProgressBar(id="dl_progress", total=100, show_eta=False)
        with Horizontal(id="dl-log-toolbar"):
            yield Label("下载日志")
            yield Button("复制日志", id="btn_dl_copy_log", variant="default")
        yield RichLog(id="dl_log", max_lines=200, markup=True)

    def on_mount(self) -> None:
        table = self.query_one("#dl_file_table", DataTable)
        col_keys = table.add_columns("选择", "文件名", "大小")
        self._col_check = col_keys[0]

    _SOURCE_IDS = ("src_hf", "src_hf_mirror", "src_ms")

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id in self._SOURCE_IDS and event.value:
            for sid in self._SOURCE_IDS:
                if sid != event.checkbox.id:
                    self.query_one(f"#{sid}", Checkbox).value = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn_dl_browse":
            self._browse()
        elif bid == "btn_dl_scan":
            self._scan()
        elif bid == "btn_dl_start":
            self._start()
        elif bid == "btn_dl_cancel":
            self._downloader.cancel()
        elif bid == "btn_dl_copy_log":
            self._copy_log()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        table = self.query_one("#dl_file_table", DataTable)
        row_key = event.row_key
        current = table.get_cell(row_key, self._col_check)
        table.update_cell(row_key, self._col_check, "☑" if current == "☐" else "☐")

    def _browse(self) -> None:
        from ui.control_panel import DirPicker
        current = self.query_one("#dl_save_dir", Input).value.strip() or "."

        def on_selected(path: str | None) -> None:
            if path:
                self.query_one("#dl_save_dir", Input).value = path

        self.app.push_screen(DirPicker(start_dir=current, title="选择保存目录"), on_selected)

    def _get_source(self):
        source_id = "src_hf"
        for sid in self._SOURCE_IDS:
            if self.query_one(f"#{sid}", Checkbox).value:
                source_id = sid
                break
        if source_id == "src_ms":
            return "modelscope", ""
        elif source_id == "src_hf_mirror":
            return "hf", HF_MIRROR_ENDPOINT
        return "hf", HF_ENDPOINT

    def _scan(self) -> None:
        repo_id = self.query_one("#dl_repo_id", Input).value.strip()
        token = self.query_one("#dl_token", Input).value.strip()
        skip_ssl = self.query_one("#dl_skip_ssl", Checkbox).value
        source, endpoint = self._get_source()

        if not repo_id:
            self._log("[red]请输入 Repo ID[/red]")
            return

        self.query_one("#btn_dl_scan", Button).disabled = True
        self.query_one("#btn_dl_start", Button).disabled = True
        self._scanned_files = []

        # 清空表格
        table = self.query_one("#dl_file_table", DataTable)
        table.clear()

        src_label = {"src_hf": "HuggingFace", "src_hf_mirror": "HF镜像", "src_ms": "ModelScope"}.get(
            next((s for s in self._SOURCE_IDS if self.query_one(f"#{s}", Checkbox).value), "src_hf"), ""
        )
        self._log(f"扫描 [cyan]{repo_id}[/cyan]（{src_label}）...")

        self._downloader.scan(
            repo_id=repo_id,
            on_done=lambda result: self.app.call_from_thread(self._on_scan_done, result),
            on_log=lambda msg: self.app.call_from_thread(self._log, msg),
            hf_token=token,
            endpoint=endpoint,
            verify_ssl=not skip_ssl,
            source=source,
        )

    def _on_scan_done(self, result: list[RemoteFile] | Exception) -> None:
        self.query_one("#btn_dl_scan", Button).disabled = False

        if isinstance(result, Exception):
            self._log(f"[red]扫描失败: {result}[/red]")
            return

        self._scanned_files = result
        table = self.query_one("#dl_file_table", DataTable)
        for rf in result:
            table.add_row("☐", rf.name, format_size(rf.size) if rf.size else "未知", key=rf.path)

        self._log(f"[green]扫描完成，找到 {len(result)} 个文件，点击行可取消勾选[/green]")
        self.query_one("#btn_dl_start", Button).disabled = False

    def _start(self) -> None:
        save_dir = self.query_one("#dl_save_dir", Input).value.strip()
        token = self.query_one("#dl_token", Input).value.strip()
        skip_ssl = self.query_one("#dl_skip_ssl", Checkbox).value
        source, endpoint = self._get_source()

        if not save_dir:
            self._log("[red]请输入保存目录[/red]")
            return

        # 收集勾选的文件
        table = self.query_one("#dl_file_table", DataTable)
        selected: list[RemoteFile] = []
        for rf in self._scanned_files:
            try:
                checked = table.get_cell(rf.path, self._col_check)
                if checked == "☑":
                    selected.append(rf)
            except Exception:
                pass

        if not selected:
            self._log("[red]请至少勾选一个文件[/red]")
            return

        self.query_one("#btn_dl_start", Button).disabled = True
        self.query_one("#btn_dl_scan", Button).disabled = True
        self.query_one("#btn_dl_cancel", Button).disabled = False
        self.query_one("#dl_progress", ProgressBar).update(progress=0)

        repo_id = self.query_one("#dl_repo_id", Input).value.strip()
        self._log(f"开始下载 {len(selected)} 个文件 → {save_dir}")

        self._downloader.start(
            files=selected,
            repo_id=repo_id,
            save_dir=save_dir,
            on_progress=lambda t: self.app.call_from_thread(self._on_progress, t),
            on_done=lambda tasks: self.app.call_from_thread(self._on_done, tasks),
            on_log=lambda msg: self.app.call_from_thread(self._log, msg),
            hf_token=token,
            endpoint=endpoint,
            verify_ssl=not skip_ssl,
            source=source,
        )

    def _on_progress(self, task: DownloadTask) -> None:
        self.query_one("#dl_current_file", Static).update(
            f"{task.filename}  {format_size(task.downloaded)}"
            + (f" / {format_size(task.total)}" if task.total else "")
        )
        if task.total:
            pct = int(task.downloaded / task.total * 100)
            self.query_one("#dl_progress", ProgressBar).update(progress=pct)
        if task.status == "error":
            self._log(f"[red]错误 {task.filename}: {task.error}[/red]")
        elif task.status == "done":
            self._log(f"[green]完成 {task.filename}[/green]")

    def _on_done(self, tasks: list[DownloadTask]) -> None:
        self.query_one("#btn_dl_start", Button).disabled = False
        self.query_one("#btn_dl_scan", Button).disabled = False
        self.query_one("#btn_dl_cancel", Button).disabled = True
        errors = [t for t in tasks if t.status == "error"]
        if any(t.status == "cancelled" for t in tasks):
            self._log("[yellow]已取消[/yellow]")
        elif errors:
            self._log(f"[red]完成，{len(errors)} 个文件失败[/red]")
        else:
            self._log(f"[green]全部完成，共 {len([t for t in tasks if t.status == 'done'])} 个文件[/green]")
        self.query_one("#dl_current_file", Static).update("")

    def _log(self, text: str) -> None:
        self._plain_lines.append(text)
        self.query_one("#dl_log", RichLog).write(text)

    def _copy_log(self) -> None:
        import subprocess
        if not self._plain_lines:
            return
        try:
            subprocess.run(
                ["clip.exe"],
                input="\n".join(self._plain_lines),
                text=True, encoding="utf-8",
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=5,
            )
            self.app.notify("日志已复制到剪贴板")
        except (subprocess.TimeoutExpired, OSError):
            pass
