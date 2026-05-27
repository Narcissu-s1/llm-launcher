@echo off
pip install pyinstaller
pyinstaller --noconfirm --onedir --windowed ^
  --name "llm-launcher" ^
  --add-data "assets;assets" ^
  --add-data "config.yaml;." ^
  --hidden-import "PySide6.QtSvg" ^
  --hidden-import "PySide6.QtXml" ^
  main.py
echo.
echo 打包完成，输出目录：dist\llm-launcher\
pause
