# core/hf_downloader.py
"""模型下载，支持 HuggingFace / HF镜像 / ModelScope，断点续传"""

import json
import os
import ssl
import threading
import traceback
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable


HF_ENDPOINT = "https://huggingface.co"
HF_MIRROR_ENDPOINT = "https://hf-mirror.com"
MS_ENDPOINT = "https://www.modelscope.cn"


@dataclass
class SearchResult:
    """HuggingFace 模型搜索结果"""
    repo_id: str       # 如 "Qwen/Qwen2.5-7B-Instruct-GGUF"
    author: str = ""
    model_name: str = ""
    downloads: int = 0
    likes: int = 0
    last_modified: str = ""
    tags: list = field(default_factory=list)


@dataclass
class RemoteFile:
    path: str       # 仓库内路径（可含子目录）
    name: str       # 文件名
    size: int = 0   # 字节，0 表示未知


@dataclass
class DownloadTask:
    url: str
    dest: str
    filename: str
    total: int = 0
    downloaded: int = 0
    status: str = "pending"
    error: str = ""


class HFDownloader:

    def __init__(self):
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._cancel = threading.Event()

    def scan(
        self,
        repo_id: str,
        on_done: Callable[[list[RemoteFile] | Exception], None],
        on_log: Callable[[str], None] | None = None,
        hf_token: str = "",
        endpoint: str = HF_ENDPOINT,
        verify_ssl: bool = True,
        source: str = "hf",
    ) -> None:
        log = on_log or (lambda _: None)
        ssl_ctx = _make_ssl_ctx(verify_ssl)
        def _run():
            log(f"查询文件列表: {repo_id}")
            try:
                if source == "modelscope":
                    files = _ms_list_gguf_files(repo_id, hf_token, ssl_ctx, log)
                else:
                    files = _hf_list_gguf_files(repo_id, hf_token, endpoint, ssl_ctx, log)
                log(f"找到 {len(files)} 个文件")
                on_done(files)
            except Exception as e:
                log(f"查询失败:\n{traceback.format_exc()}")
                on_done(e)
        threading.Thread(target=_run, daemon=True).start()

    def start(
        self,
        files: list[RemoteFile],
        repo_id: str,
        save_dir: str,
        on_progress: Callable[[DownloadTask], None],
        on_done: Callable[[list[DownloadTask]], None],
        on_log: Callable[[str], None] | None = None,
        hf_token: str = "",
        endpoint: str = HF_ENDPOINT,
        verify_ssl: bool = True,
        source: str = "hf",
    ) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._cancel.clear()
            self._thread = threading.Thread(
                target=self._run,
                args=(files, repo_id, save_dir, on_progress, on_done,
                      on_log or (lambda _: None), hf_token, endpoint, verify_ssl, source),
                daemon=True,
            )
            self._thread.start()

    def cancel(self) -> None:
        self._cancel.set()

    def search(
        self,
        keyword: str,
        on_done: Callable[[list[SearchResult] | Exception], None],
        on_log: Callable[[str], None] | None = None,
        endpoint: str = HF_ENDPOINT,
        verify_ssl: bool = True,
        limit: int = 50,
        source: str = "hf",
    ) -> None:
        """搜索模型仓库

        Args:
            keyword: 搜索关键词
            on_done: 结果回调，接收 list[SearchResult] 或 Exception
            on_log: 日志回调
            endpoint: HF API 端点
            verify_ssl: 是否验证 SSL
            limit: 最大返回数量
            source: 数据源 ("hf" / "modelscope")
        """
        log = on_log or (lambda _: None)
        ssl_ctx = _make_ssl_ctx(verify_ssl)
        def _run():
            log(f"搜索模型: {keyword}")
            try:
                if source == "modelscope":
                    results = _ms_search_models(keyword, ssl_ctx, log, limit)
                else:
                    results = _hf_search_models(keyword, endpoint, ssl_ctx, log, limit)
                log(f"找到 {len(results)} 个仓库")
                on_done(results)
            except Exception as e:
                log(f"搜索失败:\n{traceback.format_exc()}")
                on_done(e)
        threading.Thread(target=_run, daemon=True).start()

    def _run(self, files, repo_id, save_dir, on_progress, on_done, on_log,
             hf_token, endpoint, verify_ssl, source):
        ssl_ctx = _make_ssl_ctx(verify_ssl)

        if source == "modelscope":
            url_fn = lambda fname: f"{MS_ENDPOINT}/models/{repo_id}/resolve/master/{fname}"
        else:
            url_fn = lambda fname: f"{endpoint}/{repo_id}/resolve/main/{fname}"

        os.makedirs(save_dir, exist_ok=True)
        tasks = []
        for rf in files:
            if self._cancel.is_set():
                break
            url = url_fn(rf.path)
            dest = os.path.join(save_dir, rf.name)
            task = DownloadTask(url=url, dest=dest, filename=rf.name, total=rf.size)
            tasks.append(task)
            on_log(f"开始下载: {url}")
            _download_file(task, hf_token if source != "modelscope" else "",
                           ssl_ctx, self._cancel, on_progress, on_log)

        on_done(tasks)


def _make_ssl_ctx(verify: bool):
    if verify:
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _open(req, ssl_ctx, timeout):
    if ssl_ctx:
        return urllib.request.urlopen(req, timeout=timeout, context=ssl_ctx)
    return urllib.request.urlopen(req, timeout=timeout)


def _hf_list_gguf_files(repo_id, token, endpoint, ssl_ctx, on_log) -> list[RemoteFile]:
    api_url = f"{endpoint}/api/models/{repo_id}"
    req = urllib.request.Request(api_url)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    on_log(f"API: {api_url}")
    try:
        with _open(req, ssl_ctx, 30) as resp:
            on_log(f"HTTP {resp.status}")
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} {e.reason}\n{body}") from e

    siblings = data.get("siblings", [])
    files = [
        RemoteFile(path=s["rfilename"], name=os.path.basename(s["rfilename"]), size=s.get("size", 0))
        for s in siblings
        if s["rfilename"].lower().endswith(".gguf") and "mmproj" not in s["rfilename"].lower()
    ]
    if not files:
        all_names = [s["rfilename"] for s in siblings]
        raise ValueError(
            f"仓库 {repo_id} 中未找到 GGUF 文件。\n"
            f"所有文件: {all_names}\n"
            f"提示：GGUF 量化模型通常在独立仓库，尝试搜索「{repo_id.split('/')[-1]}-GGUF」"
        )
    return files


def _hf_search_models(keyword: str, endpoint: str, ssl_ctx, on_log, limit: int = 50) -> list[SearchResult]:
    """调用 HuggingFace API 搜索模型仓库（只返回含 GGUF 文件的结果）"""
    import urllib.parse
    params = urllib.parse.urlencode({
        "search": keyword,
        "limit": limit,
        "filter": "gguf",
        "sort": "downloads",
        "direction": "-1",
    })
    api_url = f"{endpoint}/api/models?{params}"
    req = urllib.request.Request(api_url)
    on_log(f"API: {api_url}")
    try:
        with _open(req, ssl_ctx, 30) as resp:
            on_log(f"HTTP {resp.status}")
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} {e.reason}\n{body}") from e

    results = []
    for item in data:
        repo_id = item.get("id", "")
        if not repo_id:
            continue
        results.append(SearchResult(
            repo_id=repo_id,
            author=item.get("author", ""),
            model_name=repo_id.split("/")[-1] if "/" in repo_id else repo_id,
            downloads=item.get("downloads", 0),
            likes=item.get("likes", 0),
            last_modified=item.get("lastModified", ""),
            tags=item.get("tags", []),
        ))
    return results


def _ms_search_models(keyword: str, ssl_ctx, on_log, limit: int = 50) -> list[SearchResult]:
    """调用 ModelScope 旧版 API 搜索模型仓库"""
    body = json.dumps({
        "Name": keyword,
        "PageNumber": 1,
        "PageSize": limit,
    }).encode("utf-8")
    api_url = f"{MS_ENDPOINT}/api/v1/models"
    req = urllib.request.Request(api_url, data=body, method="PUT")
    req.add_header("Content-Type", "application/json")
    on_log(f"API: {api_url}")
    try:
        with _open(req, ssl_ctx, 30) as resp:
            on_log(f"HTTP {resp.status}")
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} {e.reason}\n{body_text}") from e

    if not data.get("Success"):
        raise RuntimeError(f"ModelScope API 错误: {data.get('Message', '未知错误')}")

    models = data.get("Data", {}).get("Models", [])
    results = []
    for item in models:
        path = item.get("Path", "")
        name = item.get("Name", "")
        if not path or not name:
            continue
        results.append(SearchResult(
            repo_id=f"{path}/{name}",
            author=item.get("CreatedBy", path),
            model_name=item.get("ChineseName") or name,
            downloads=item.get("Downloads", 0),
            likes=item.get("Stars", 0),
        ))
    return results


def _ms_list_gguf_files(repo_id, token, ssl_ctx, on_log) -> list[RemoteFile]:
    api_url = f"{MS_ENDPOINT}/api/v1/models/{repo_id}/repo/files?Recursive=true"
    req = urllib.request.Request(api_url)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    on_log(f"API: {api_url}")
    try:
        with _open(req, ssl_ctx, 30) as resp:
            on_log(f"HTTP {resp.status}")
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} {e.reason}\n{body}") from e

    files_data = data.get("Data", {}).get("Files", [])
    files = [
        RemoteFile(path=f["Path"], name=os.path.basename(f["Path"]), size=f.get("Size", 0))
        for f in files_data
        if f["Path"].lower().endswith(".gguf") and "mmproj" not in f["Path"].lower()
    ]
    if not files:
        all_names = [f["Path"] for f in files_data]
        raise ValueError(
            f"仓库 {repo_id} 中未找到 GGUF 文件。\n"
            f"所有文件: {all_names}\n"
            f"提示：尝试搜索「{repo_id.split('/')[-1]}-GGUF」"
        )
    return files


def _download_file(task, token, ssl_ctx, cancel, on_progress, on_log) -> None:
    CHUNK = 1024 * 256

    req = urllib.request.Request(task.url)
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    existing = os.path.getsize(task.dest) if os.path.exists(task.dest) else 0
    resume_requested = bool(existing)
    if resume_requested:
        req.add_header("Range", f"bytes={existing}-")
        on_log(f"断点续传请求：已有 {existing} 字节，发送 Range: bytes={existing}-")

    task.status = "downloading"
    task.downloaded = existing
    on_progress(task)

    try:
        with _open(req, ssl_ctx, 60) as resp:
            on_log(f"连接成功: HTTP {resp.status}，Content-Length={resp.headers.get('Content-Length')}")
            content_length = resp.headers.get("Content-Length")
            content_range = resp.headers.get("Content-Range")

            if resume_requested:
                if resp.status == 206:
                    on_log("✓ 服务器支持断点续传（HTTP 206 Partial Content），将从断点继续下载")
                    mode = "ab"
                elif resp.status == 200:
                    on_log("✗ 服务器不支持断点续传（返回 HTTP 200），将重新下载整个文件")
                    existing = 0
                    task.downloaded = 0
                    mode = "wb"
                else:
                    mode = "ab"
            else:
                on_log("首次下载（无断点续传）")
                mode = "wb"

            if content_range:
                total_str = content_range.split("/")[-1]
                task.total = int(total_str) if total_str.isdigit() else 0
            elif content_length:
                task.total = int(content_length) + existing
            else:
                task.total = task.total or 0

            with open(task.dest, mode) as f:
                while not cancel.is_set():
                    chunk = resp.read(CHUNK)
                    if not chunk:
                        break
                    f.write(chunk)
                    task.downloaded += len(chunk)
                    on_progress(task)

        if cancel.is_set():
            task.status = "cancelled"
        else:
            task.status = "done"
            task.downloaded = task.total or task.downloaded

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        task.status = "error"
        task.error = f"HTTP {e.code} {e.reason}"
        on_log(f"下载失败: HTTP {e.code} {e.reason}\n{body}")
    except Exception:
        tb = traceback.format_exc()
        task.status = "error"
        task.error = tb.strip().splitlines()[-1]
        on_log(f"下载失败:\n{tb}")

    on_progress(task)
