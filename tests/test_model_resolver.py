# tests/test_model_resolver.py
"""ModelResolver 单元测试"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.model_resolver import ModelResolver


def test_指定目录中搜索():
    """config_path 应为 llama.cpp 目录，在其中搜索 llama-server.exe"""
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_exe = os.path.join(tmpdir, "llama-server.exe")
        with open(fake_exe, "w") as f:
            f.write("fake")

        resolver = ModelResolver(config_path=tmpdir)
        result = resolver.resolve()
        assert result == fake_exe


def test_目录不存在时回退搜索():
    """指定的目录不存在时，应回退到自动搜索而非直接报错"""
    resolver = ModelResolver(config_path="/nonexistent/path")
    # 应继续搜索其他位置（PATH 等），找不到才抛异常
    try:
        result = resolver.resolve()
        assert isinstance(result, str)
    except FileNotFoundError:
        pass  # 可以接受找不到的情况


def test_配置路径为空时自动搜索():
    """配置路径为空字符串时进行自动搜索"""
    resolver = ModelResolver(config_path="")
    try:
        result = resolver.resolve()
        assert isinstance(result, str)
    except FileNotFoundError:
        pass


def test_搜索目录优先于PATH():
    """search_dirs 中的目录优先于 PATH 环境变量"""
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_exe = os.path.join(tmpdir, "llama-server.exe")
        with open(fake_exe, "w") as f:
            f.write("fake")

        resolver = ModelResolver(config_path="", search_dirs=[tmpdir])
        result = resolver.resolve()
        assert result == fake_exe
