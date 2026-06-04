# tests/test_updater.py
"""updater 单元测试

不联网测试：只覆盖纯函数（版本解析）和离线/错误场景。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.updater import _parse_version, check_update, check_update_async, UpdateInfo


def test_解析_标准三段():
    assert _parse_version("1.0.0") == (1, 0, 0)
    assert _parse_version("v1.2.3") == (1, 2, 3)


def test_解析_两段补零():
    assert _parse_version("v2.0") == (2, 0, 0)


def test_解析_rc后缀():
    """'1.0.0-rc1' 数字部分为 1"""
    assert _parse_version("1.0.0-rc1") == (1, 0, 0)


def test_解析_带前缀空白():
    assert _parse_version("  v1.0.0  ") == (1, 0, 0)


def test_比较_旧版小():
    assert _parse_version("0.1.0") < _parse_version("1.0.0")


def test_比较_次版本大():
    assert _parse_version("1.0.0") < _parse_version("1.0.1")


def test_比较_主版本大():
    assert _parse_version("1.9.9") < _parse_version("2.0.0")


def test_比较_相等():
    assert _parse_version("1.0.0") == _parse_version("v1.0.0")


def test_不存在的仓库应返回错误_不崩溃():
    """离线/404 不应抛异常，应填充 error 字段"""
    info = check_update(repo="this-org-does-not-exist-xyz/none", current="0.1.0")
    assert isinstance(info, UpdateInfo)
    assert info.has_update is False
    assert info.error is not None  # 错误信息存在
    assert info.release_url == ""  # 无 url


def test_异步版本能返回线程句柄():
    """check_update_async 返回 Thread 对象"""
    captured = {}

    def cb(info):
        captured["info"] = info

    t = check_update_async(cb, repo="this-org-does-not-exist-xyz/none", current="0.1.0")
    t.join(timeout=10)
    assert not t.is_alive()
    assert "info" in captured
    assert captured["info"].error is not None


def test_异步回调异常不杀死线程():
    """即使回调抛异常，也不应影响其他测试"""
    def bad_cb(_info):
        raise RuntimeError("boom")

    t = check_update_async(bad_cb, repo="this-org-does-not-exist-xyz/none", current="0.1.0")
    t.join(timeout=10)
    # 线程已结束（未崩溃）
    assert not t.is_alive()
