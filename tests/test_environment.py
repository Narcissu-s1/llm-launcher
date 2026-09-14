"""验证项目使用 uv 管理的隔离环境和入口脚本。"""

from __future__ import annotations

import importlib
import importlib.util
import os
from pathlib import Path
import shutil
import site
import subprocess
import sys
import tempfile
import types

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_VENV = PROJECT_ROOT / ".venv"


def _is_inside(path: Path, root: Path) -> bool:
    """判断 path 是否位于 root 内，兼容 Windows 大小写和路径解析。"""
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _require_project_venv() -> None:
    """全局 Python 运行完整测试时跳过需要项目环境的断言。"""
    if Path(sys.prefix).resolve() != PROJECT_VENV.resolve():
        pytest.skip("当前不是通过 uv 使用项目 .venv 运行测试")


def test_解释器来自项目虚拟环境且与基础解释器分离():
    _require_project_venv()

    assert Path(sys.executable).resolve().is_relative_to(PROJECT_VENV.resolve())
    assert Path(sys.prefix).resolve() == PROJECT_VENV.resolve()
    assert Path(sys.prefix).resolve() != Path(sys.base_prefix).resolve()


def test_site路径不包含项目外的第三方安装目录():
    _require_project_venv()

    site_packages = [Path(path).resolve() for path in site.getsitepackages()]
    assert site_packages
    assert all(_is_inside(path, PROJECT_VENV) for path in site_packages)

    external_package_paths = [
        Path(path).resolve()
        for path in sys.path
        if path
        and Path(path).name.casefold() in {"site-packages", "dist-packages"}
        and not _is_inside(Path(path), PROJECT_VENV)
    ]
    assert external_package_paths == []


@pytest.mark.parametrize(
    "module_name",
    ["psutil", "yaml", "requests", "huggingface_hub", "PySide6"],
)
def test_运行依赖来自项目虚拟环境(module_name: str):
    _require_project_venv()

    spec = importlib.util.find_spec(module_name)
    assert spec is not None, f"未找到运行依赖 {module_name}"

    locations = list(spec.submodule_search_locations or [])
    if spec.origin and spec.origin not in {"built-in", "frozen"}:
        locations.append(spec.origin)
    assert locations, f"无法确定 {module_name} 的安装位置"
    assert all(
        _is_inside(Path(location), PROJECT_VENV) for location in locations
    ), f"{module_name} 未从项目 .venv 加载: {locations}"


def _write_mock_commands(
    command_dir: Path, log_dir: Path, *, uv_exit_code: int = 0
) -> tuple[Path, Path]:
    """创建只记录参数的 uv/python 命令，防止批处理触发真实程序。"""
    uv_log = log_dir / "uv-args.txt"
    python_log = log_dir / "python-fallback.txt"
    uv_command = command_dir / "uv.cmd"
    python_command = command_dir / "python.cmd"

    uv_command.write_text(
        "@echo off\n"
        "echo MOCK_UV_CALLED\n"
        ">>\"%UV_TEST_LOG%\" echo %*\n"
        f"exit /b {uv_exit_code}\n",
        encoding="ascii",
    )
    python_command.write_text(
        "@echo off\n"
        ">>\"%PYTHON_FALLBACK_LOG%\" echo %*\n"
        "exit /b 0\n",
        encoding="ascii",
    )
    return uv_log, python_log


def _run_batch(
    script_name: str,
    temp_dir: Path,
    *,
    uv_exit_code: int = 0,
    input_data: str = "\r\n",
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    command_dir = Path(tempfile.mkdtemp(prefix=".uv-test-", dir=PROJECT_ROOT))
    try:
        uv_log, python_log = _write_mock_commands(
            command_dir, temp_dir, uv_exit_code=uv_exit_code
        )
        environment = os.environ.copy()
        # 保留 where.exe 所在目录，同时让它优先发现项目目录下的测试桩。
        environment["PATH"] = os.pathsep.join(
            [str(command_dir), str(Path(os.environ["SystemRoot"]) / "System32")]
        )
        environment["UV_TEST_LOG"] = str(uv_log)
        environment["PYTHON_FALLBACK_LOG"] = str(python_log)

        result = subprocess.run(
            [
                environment.get("COMSPEC", r"C:\Windows\System32\cmd.exe"),
                "/d",
                "/c",
                str(PROJECT_ROOT / script_name),
            ],
            cwd=PROJECT_ROOT,
            env=environment,
            input=input_data,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
        return result, uv_log, python_log
    finally:
        if command_dir.parent == PROJECT_ROOT:
            shutil.rmtree(command_dir, ignore_errors=True)


def _run_start_without_uv(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
    environment["USERPROFILE"] = str(tmp_path / "profile-without-uv")
    return subprocess.run(
        [
            environment.get("COMSPEC", r"C:\Windows\System32\cmd.exe"),
            "/d",
            "/c",
            str(PROJECT_ROOT / "start.cmd"),
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        input="\r\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )


@pytest.mark.skipif(os.name != "nt", reason="入口脚本是 Windows 批处理文件")
def test_start脚本通过uv运行项目入口(tmp_path):
    result, uv_log, python_log = _run_batch(
        "start.cmd", tmp_path, input_data=""
    )

    assert result.returncode == 0
    assert uv_log.read_text(encoding="utf-8").splitlines() == [
        "run --locked main.py"
    ]
    assert not python_log.exists()


@pytest.mark.skipif(os.name != "nt", reason="入口脚本是 Windows 批处理文件")
def test_start脚本执行uv失败时不回退到python(tmp_path):
    result, uv_log, python_log = _run_batch(
        "start.cmd", tmp_path, uv_exit_code=23
    )

    assert result.returncode == 23
    assert "MOCK_UV_CALLED" in result.stdout
    assert uv_log.read_text(encoding="utf-8").splitlines() == [
        "run --locked main.py"
    ]
    assert not python_log.exists()


@pytest.mark.skipif(os.name != "nt", reason="入口脚本是 Windows 批处理文件")
def test_start脚本找不到uv时提示安装且暂停(tmp_path):
    result = _run_start_without_uv(tmp_path)

    assert result.returncode == 1
    assert "uv is not installed" in result.stdout


@pytest.mark.skipif(os.name != "nt", reason="入口脚本是 Windows 批处理文件")
def test_编译脚本通过uv调用构建入口(tmp_path):
    result, uv_log, _ = _run_batch("C编译.bat", tmp_path)

    assert result.returncode == 0
    assert uv_log.read_text(encoding="utf-8").splitlines() == [
        "run --locked --group build python scripts/build.py"
    ]


def test_构建helper使用当前解释器和项目内zig并传递退出码(
    monkeypatch, tmp_path
):
    zig_root = tmp_path / "ziglang"
    zig_root.mkdir()
    zig_module = types.ModuleType("ziglang")
    zig_module.__file__ = str(zig_root / "__init__.py")
    monkeypatch.setitem(sys.modules, "ziglang", zig_module)
    monkeypatch.delitem(sys.modules, "scripts.build", raising=False)
    build_module = importlib.import_module("scripts.build")

    output_dir = tmp_path / "release-dist"
    captured = {}

    def fake_call(command, *, cwd, env):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["env"] = env
        return 17

    monkeypatch.setattr(build_module.subprocess, "call", fake_call)
    monkeypatch.setattr(
        sys,
        "argv",
        ["scripts/build.py", "--output-dir", str(output_dir)],
    )
    monkeypatch.setenv("PATH", "base-path")
    monkeypatch.delenv("NUITKA_CACHE_DIR", raising=False)

    assert build_module.main() == 17
    assert captured["command"] == [
        sys.executable,
        "-m",
        "nuitka",
        "--zig",
        "--standalone",
        "--assume-yes-for-downloads",
        "--windows-console-mode=disable",
        "--enable-plugin=pyside6",
        "--include-data-dir=assets=assets",
        "--windows-icon-from-ico=assets/icon.ico",
        f"--output-dir={output_dir}",
        "--output-filename=llm-launcher.exe",
        "main.py",
    ]
    assert captured["cwd"] == PROJECT_ROOT
    assert captured["env"]["PATH"].split(os.pathsep) == [
        str(zig_root),
        "base-path",
    ]
    assert captured["env"]["NUITKA_CACHE_DIR"] == str(
        PROJECT_ROOT / "dist" / "nuitka-cache"
    )
