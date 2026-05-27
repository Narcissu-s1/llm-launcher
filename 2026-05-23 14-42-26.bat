@echo off
:: 设置控制台为 UTF-8，避免中文输出乱码
chcp 65001 >nul

:: 切换到批处理文件所在的目录（自动处理空格和中文路径）
cd /d "%~dp0"

:: 检查 main.py 是否存在
if not exist "main.py" (
    echo ❌ 错误：当前目录下找不到 main.py！
    pause
    exit /b 1
)

:: 运行脚本
echo 🚀 正在运行 main.py ...
python main.py

:: 运行结束后暂停窗口，方便查看输出或报错信息
pause