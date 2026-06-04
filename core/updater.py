# core/updater.py
"""在线更新检查

启动时后台调用 GitHub Releases API，比对最新版本与本地版本。
任何网络错误静默忽略——离线环境不应阻塞 UI。

设计原则：
- 不自动下载（避免损坏本地数据/触发杀毒）
- 不阻塞 UI（后台线程）
- 不在 release-info URL 中带 token
"""

import json
import logging
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass

from core._version import __version__

logger = logging.getLogger(__name__)

# 默认仓库（正式发布时改为真实仓库）
DEFAULT_REPO = "yourname/llm-launcher"
API_TIMEOUT = 5  # 秒


@dataclass
class UpdateInfo:
    """更新检查结果"""

    has_update: bool
    current: str
    latest: str
    release_url: str
    error: str | None = None  # 网络/解析失败时填充


def _parse_version(tag: str) -> tuple[int, ...]:
    """解析 'v1.2.3' / '1.2.3' / '1.2.3-rc1' 为可比较元组。

    非数字段降级为 0，例如 'v1.2' -> (1, 2, 0)。
    """
    s = tag.strip().lstrip("v")
    parts: list[int] = []
    for seg in s.split("."):
        # 取开头的数字（'3-rc1' -> '3'）
        num = ""
        for c in seg:
            if c.isdigit():
                num += c
            else:
                break
        parts.append(int(num) if num else 0)
    # 至少 3 段
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def check_update(repo: str = DEFAULT_REPO, current: str = __version__) -> UpdateInfo:
    """同步检查 GitHub Release（带超时），失败返回 error 信息

    适合在后台线程调用。
    """
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=API_TIMEOUT) as r:
            data = json.load(r)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
        logger.info("更新检查失败（忽略）: %s", e)
        return UpdateInfo(False, current, current, "", error=str(e))

    tag = data.get("tag_name") or ""
    html_url = data.get("html_url") or ""
    if not tag:
        return UpdateInfo(False, current, current, html_url, error="release 无 tag_name")

    latest = tag.lstrip("v")
    try:
        has_update = _parse_version(latest) > _parse_version(current)
    except ValueError as e:
        return UpdateInfo(False, current, latest, html_url, error=f"version 解析失败: {e}")

    return UpdateInfo(has_update, current, latest, html_url)


def check_update_async(
    callback, repo: str = DEFAULT_REPO, current: str = __version__
) -> threading.Thread:
    """异步检查更新，结果通过 callback(UpdateInfo) 回调

    callback 在后台线程触发，UI 层需自行切回主线程。
    返回 Thread 句柄方便测试 join。
    """

    def _worker():
        info = check_update(repo, current)
        try:
            callback(info)
        except Exception as e:  # UI 回调异常不应杀死线程
            logger.warning("update callback 异常: %s", e)

    t = threading.Thread(target=_worker, name="update-checker", daemon=True)
    t.start()
    return t
