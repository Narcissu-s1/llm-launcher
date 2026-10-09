"""依据用户提供的 HTTP Server 快照检查参数覆盖与实际命令。"""

import ast
import html as html_module
import inspect
import re
import textwrap
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def guide_cards():
    guide = ROOT / "docs" / "llama-server-参数指南.html"
    if not guide.exists():
        pytest.skip("本地 HTML 参数指南未随仓库提供")
    html = guide.read_text(encoding="utf-8")
    return re.findall(r'<div class="(param(?: [^"]*)?)" data-keys="([^"]+)">([\s\S]*?)(?=<div class="param(?: [^"]*)?" data-keys=|$)', html)


@pytest.fixture
def source_rows():
    source = ROOT / "docs" / "LLaMA.cpp HTTP Server.md"
    if not source.exists():
        pytest.skip("本地 HTTP Server 参考快照未随仓库提供")
    help_text = source.read_text(encoding="utf-8").split("<!-- HELP_START -->", 1)[1].split("<!-- HELP_END -->", 1)[0]
    return [(set(re.findall(r"(?<![\w-])--?[A-Za-z][\w.-]*", argument)), explanation)
            for argument, explanation in re.findall(r"^\| `([^`]+)` \| (.+) \|$", help_text, re.M)]


def test_当前生成命令仅使用来源有效参数(source_rows):
    from core.process_manager import ProcessSupervisor

    valid = set().union(*(flags for flags, desc in source_rows
                          if "DEPRECATED" not in desc and "argument has been removed" not in desc))
    tree = ast.parse(textwrap.dedent(inspect.getsource(ProcessSupervisor._build_command)))
    emitted = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant)
               and isinstance(node.value, str) and re.fullmatch(r"--?[A-Za-z][\w-]*", node.value)}
    assert emitted <= valid, sorted(emitted - valid)


def test_HTML指南覆盖来源全部别名(source_rows, guide_cards):
    keys = set(" ".join(keys for _, keys, _ in guide_cards).split())
    expected = set().union(*(flags for flags, _ in source_rows))
    assert expected <= keys, sorted(expected - keys)


def test_HTML别名可见且包含来源环境变量(source_rows, guide_cards):
    for flags, desc in source_rows:
        bodies = [body for _, keys, body in guide_cards if flags.intersection(keys.split())]
        body = " ".join(bodies)
        visible = " ".join(html_module.unescape(re.sub(r"<[^>]+>", "", text))
                           for text in re.findall(r'<span class="flag(?: [^"]*)?">([\s\S]*?)</span>', body))
        for flag in flags:
            assert flag in visible, flag
        for env in re.findall(r"\(env: ([A-Z_0-9]+)\)", desc):
            assert env in body, (flags, env)


def test_HTML新增标记准确且弃用项保留删除线(guide_cards):
    expected_new = {"-ncffn", "--n-cpu-ffn", "-lzm", "--lazy-mode", "--moe-cache-mib",
                    "--kv-unified-per-slot", "--video-fps", "--video-timestamp-interval",
                    "--video-ffmpeg-dir", "--spec-synth-len", "--spec-synth-rates",
                    "--spec-draft-sampling", "--log-jsonl", "--no-log-jsonl"}
    marked = set()
    for _, _, body in guide_cards:
        for flags in re.findall(r'<span class="[^"]*\bflag-new\b[^"]*">([\s\S]*?)</span>', body):
            text = html_module.unescape(re.sub(r"<[^>]+>", "", flags))
            marked.add(text.split()[0])
    assert marked == expected_new
    assert sum("param-new" in classes for classes, _, _ in guide_cards) == 11
    deprecated = [(keys, body) for classes, keys, body in guide_cards if "param-deprecated" in classes]
    assert len(deprecated) == 9
    for keys, body in deprecated:
        assert "<s>" in body, keys
        if {"--mlock", "--mmap", "--direct-io"}.intersection(keys.split()):
            assert "来源未列出，支持状态待核实" in body
            assert "已移除（本地来源不再列出）" not in body
