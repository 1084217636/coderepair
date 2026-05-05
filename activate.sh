#!/bin/bash

# CodeRepair 项目虚拟环境激活脚本

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "❌ 虚拟环境不存在: $VENV_DIR"
    echo "正在创建虚拟环境..."
    python3 -m venv "$VENV_DIR"
fi

echo "🚀 激活虚拟环境..."
source "$VENV_DIR/bin/activate"

echo "✅ 虚拟环境已激活"
echo "📦 Python 版本: $(python -V)"
echo "📍 虚拟环境路径: $VENV_DIR"
echo ""
echo "💡 快速命令:"
echo "   pytest tests/ -v              # 运行测试"
echo "   pytest tests/ --cov           # 带覆盖率的测试"
echo "   python3 -c '...'              # 运行 Python 代码"
echo ""
