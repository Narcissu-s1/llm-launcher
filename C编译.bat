@echo off
set "PATH=C:\Python314\Lib\site-packages\ziglang;%PATH%"

python -m nuitka ^
  --zig ^
  --standalone ^
  --windows-console-mode=disable ^
  --enable-plugin=pyside6 ^
  --include-data-dir=assets=assets ^
  --include-data-file=config.yaml=config.yaml ^
  --windows-icon-from-ico=assets/icon.ico ^
  --output-dir=dist ^
  --output-filename=llm-launcher.exe ^
  main.py

pause
