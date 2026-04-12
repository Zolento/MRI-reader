#!/bin/bash
# MRI Reader 打包脚本
# 用于生成可执行文件

set -e

echo "========================================="
echo "MRI Reader - 打包工具"
echo "========================================="

# 检查uv是否安装
if ! command -v uv &> /dev/null; then
    echo "错误: 未找到uv命令，请先安装uv"
    exit 1
fi

# 安装PyInstaller
echo ""
echo "[1/4] 安装PyInstaller..."
uv pip install pyinstaller

# 清理旧的构建文件
echo ""
echo "[2/4] 清理旧的构建文件..."
if [ -d "build" ]; then
    rm -rf build
    echo "  已删除 build/ 目录"
fi
if [ -d "dist" ]; then
    rm -rf dist
    echo "  已删除 dist/ 目录"
fi

# 执行打包
echo ""
echo "[3/4] 开始打包..."
uv run pyinstaller build.spec --clean

# 检查结果
echo ""
echo "[4/4] 检查打包结果..."
if [ -d "dist/MRI-Reader" ]; then
    echo ""
    echo "========================================="
    echo "✓ 打包成功!"
    echo "========================================="
    echo ""
    echo "可执行文件位置: dist/MRI-Reader/"
    echo ""
    echo "目录结构:"
    ls -lh dist/MRI-Reader/ | head -20
    echo ""
    echo "测试运行:"
    echo "  ./dist/MRI-Reader/MRI-Reader.exe  (Windows)"
    echo "  ./dist/MRI-Reader/MRI-Reader      (Linux)"
    echo ""
else
    echo "✗ 打包失败! 请检查错误信息"
    exit 1
fi
