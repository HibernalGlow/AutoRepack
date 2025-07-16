@echo off
chcp 65001 >nul
echo ========================================
echo    compress_entire_folder 功能测试
echo ========================================
echo.

echo 运行基本功能测试...
python test_compress.py

echo.
echo ========================================
echo.

echo 是否运行 pytest 测试? (需要安装 pytest)
echo 1. 是
echo 2. 否
echo.
set /p choice="请选择 (1/2): "

if "%choice%"=="1" (
    echo.
    echo 检查 pytest 是否已安装...
    python -c "import pytest" 2>nul
    if errorlevel 1 (
        echo pytest 未安装，正在安装...
        pip install pytest
    )
    
    echo.
    echo 运行 pytest 测试...
    python test_compress_pytest.py
) else (
    echo 跳过 pytest 测试
)

echo.
echo 测试完成！
pause
