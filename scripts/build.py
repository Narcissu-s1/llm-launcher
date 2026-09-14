"""通过当前项目解释器调用 Nuitka，编译器来自同一环境。"""

import argparse
import os
from pathlib import Path
import subprocess
import sys

import ziglang


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="dist")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PATH"] = str(Path(ziglang.__file__).parent) + os.pathsep + env.get("PATH", "")
    env.setdefault("PROCESSOR_ARCHITECTURE", "AMD64")
    env.setdefault("NUITKA_CACHE_DIR", str(root / "dist" / "nuitka-cache"))
    return subprocess.call(
        [
            sys.executable, "-m", "nuitka",
            "--zig", "--standalone", "--assume-yes-for-downloads",
            "--windows-console-mode=disable", "--enable-plugin=pyside6",
            "--include-data-dir=assets=assets",
            "--windows-icon-from-ico=assets/icon.ico",
            f"--output-dir={args.output_dir}",
            "--output-filename=llm-launcher.exe", "main.py",
        ],
        cwd=root,
        env=env,
    )


if __name__ == "__main__":
    sys.exit(main())
