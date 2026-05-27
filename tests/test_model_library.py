# tests/test_model_library.py
import os
import struct
import tempfile

import pytest

from core.model_library import (
    ModelInfo, format_params, format_size, scan_directory, _quant_from_name,
)


def test_format_params():
    assert format_params(0) == "未知"
    assert format_params(7_000_000_000) == "7.0B"
    assert format_params(70_000_000) == "70M"


def test_format_size():
    assert "KB" in format_size(2048)
    assert "MB" in format_size(10 * 1024 * 1024)
    assert "GB" in format_size(4 * 1024 ** 3)


def test_quant_from_name():
    assert _quant_from_name("mistral-7b-Q4_K_M") == "Q4_K_M"
    assert _quant_from_name("model-Q8_0") == "Q8_0"
    assert _quant_from_name("model-unknown") == "未知"


def test_scan_empty_dir():
    with tempfile.TemporaryDirectory() as d:
        assert scan_directory(d) == []


def test_scan_nonexistent():
    assert scan_directory("/nonexistent/path/xyz") == []


def test_scan_finds_gguf(tmp_path):
    # 创建假 GGUF 文件（非法头，但能被扫描到）
    f = tmp_path / "model-Q4_K_M.gguf"
    f.write_bytes(b"\x00" * 64)
    results = scan_directory(str(tmp_path))
    assert len(results) == 1
    assert results[0].name == "model-Q4_K_M"
    assert results[0].quant_type == "Q4_K_M"
    assert results[0].file_size == 64


def test_scan_ignores_non_gguf(tmp_path):
    (tmp_path / "model.bin").write_bytes(b"\x00" * 16)
    (tmp_path / "model.gguf").write_bytes(b"\x00" * 16)
    results = scan_directory(str(tmp_path))
    assert len(results) == 1
