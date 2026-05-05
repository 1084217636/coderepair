#!/usr/bin/env python3
"""
使用 AiCanAPI 的快速示例脚本
"""
import os
import sys

def example_1_basic_setup():
    """示例 1：基本设置"""
    print("\n" + "="*60)
    print("示例 1：基本设置 AiCanAPI")
    print("="*60)
    
    print("""
# 方式 A：通过命令行环境变量
export LLM_PROVIDER=aicanapi
export AICANAPI_API_KEY=sk-your-aicanapi-api-key-here
export AICANAPI_MODEL=claude-opus-4-6

# 方式 B：创建 .env 文件
cat > .env << EOF
LLM_PROVIDER=aicanapi
AICANAPI_API_KEY=sk-your-aicanapi-api-key-here
AICANAPI_MODEL=claude-opus-4-6
EOF

# 方式 C：Python 代码中设置
import os
os.environ['LLM_PROVIDER'] = 'aicanapi'
os.environ['AICANAPI_API_KEY'] = 'sk-your-aicanapi-api-key-here'
os.environ['AICANAPI_MODEL'] = 'claude-opus-4-6'
    """)


def example_2_config_verification():
    """示例 2：验证配置"""
    print("\n" + "="*60)
    print("示例 2：验证配置")
    print("="*60)
    
    print("""
# 运行环境检查
python verify_environment.py

# 或在 Python 中验证
from config import settings

print(f"Provider: {settings.LLM_PROVIDER}")  # aicanapi
print(f"Model: {settings.LLM_MODEL}")  # claude-opus-4-6
print(f"API Base: {settings.LLM_API_BASE}")  # https://aicanapi.com/v1
    """)


def example_3_main_usage():
    """示例 3：主程序使用"""
    print("\n" + "="*60)
    print("示例 3：运行主平台")
    print("="*60)
    
    print("""
# 修复 Go 项目中的 bug
python app.py \\
  --workspace ./my_go_project \\
  --query "修复并发访问导致的 race condition" \\
  --provider aicanapi

# 实现新功能
python app.py \\
  --workspace ./my_go_project \\
  --query "添加缓存层提升性能" \\
  --provider aicanapi

# 优化代码
python app.py \\
  --workspace ./my_go_project \\
  --query "重构 database 连接池" \\
  --provider aicanapi
    """)


def example_4_model_switching():
    """示例 4：切换模型"""
    print("\n" + "="*60)
    print("示例 4：切换 Claude 模型")
    print("="*60)
    
    print("""
# 使用 claude-opus-4-6（最强能力）
export AICANAPI_MODEL=claude-opus-4-6
python app.py --workspace ./project --query "修复 bug" --provider aicanapi

# 使用 claude-sonnet-4-6（更快、更便宜）
export AICANAPI_MODEL=claude-sonnet-4-6
python app.py --workspace ./project --query "修复 bug" --provider aicanapi

# Python 代码中动态切换
import os
os.environ['AICANAPI_MODEL'] = 'claude-sonnet-4-6'

from llm.client import LLMClient
client = LLMClient()
result = client.call(
    system_prompt="You are a Go expert",
    user_message="Fix this bug: ..."
)
    """)


def example_5_complete_workflow():
    """示例 5：完整工作流"""
    print("\n" + "="*60)
    print("示例 5：完整工作流示例")
    print("="*60)
    
    print("""
#!/bin/bash
set -e

# 1. 配置 AiCanAPI
export LLM_PROVIDER=aicanapi
export AICANAPI_API_KEY=sk-your-aicanapi-api-key-here
export AICANAPI_MODEL=claude-opus-4-6

# 2. 初始化和诊断
echo "验证配置..."
python verify_environment.py

# 3. 分析 Go 项目
PROJECT_PATH=./my_go_project
echo "分析 Go 项目..."

# 4. 运行第一轮分析（高复杂度，用强模型）
echo "执行 bug 分析..."
python app.py \\
  --workspace "$PROJECT_PATH" \\
  --query "找出并修复 goroutine leak" \\
  --provider aicanapi \\
  | tee analysis_result.json

# 5. 如果需要跟进，切换到快速模型
export AICANAPI_MODEL=claude-sonnet-4-6
echo "执行后续优化（使用 sonnet）..."
python app.py \\
  --workspace "$PROJECT_PATH" \\
  --query "优化第一步的建议" \\
  --provider aicanapi \\
  | tee optimization_result.md

echo "完成！"
    """)


def example_6_environment_setup():
    """示例 6：环境设置完整脚本"""
    print("\n" + "="*60)
    print("示例 6：一键环境设置脚本")
    print("="*60)
    
    print("""
# setup_aicanapi.sh
#!/bin/bash

# 1. 创建 .env 文件
cat > .env << 'EOF'
# LLM 配置
LLM_PROVIDER=aicanapi
AICANAPI_API_KEY=sk-your-aicanapi-api-key-here
AICANAPI_MODEL=claude-opus-4-6

# 通用配置
LLM_TEMPERATURE=0.7
RETRIEVAL_TOP_K=5
LOG_LEVEL=INFO
EOF

echo "✓ .env 文件已创建"

# 2. 验证配置
python verify_environment.py
if [ $? -eq 0 ]; then
    echo "✓ AiCanAPI 配置验证成功"
else
    echo "✗ AiCanAPI 配置验证失败"
    exit 1
fi

echo "✓ 环境设置完成，可以开始使用！"
echo ""
echo "下一步："
echo "  python app.py --workspace ./my_project --query '修复 bug' --provider aicanapi"
    """)


def example_7_troubleshooting():
    """示例 7：故障排查"""
    print("\n" + "="*60)
    print("示例 7：常见问题与排查")
    print("="*60)
    
    print("""
问题 1：未配置 AICANAPI API Key，使用模拟回复
解决方案：
  export AICANAPI_API_KEY=sk-your-aicanapi-api-key-here
  python app.py --workspace ./project --query "修复 bug" --provider aicanapi

问题 2：模型不存在
解决方案：
  确认使用支持的模型：claude-opus-4-6 或 claude-sonnet-4-6
  export AICANAPI_MODEL=claude-opus-4-6

问题 3：网络连接失败
解决方案：
  检查网络连接
  ping aicanapi.com
  curl https://aicanapi.com/v1/chat/completions

问题 4：API 密钥无效
解决方案：
  访问 https://aicanapi.com 重新生成 API 密钥
  更新 AICANAPI_API_KEY 环境变量

问题 5：进程卡住
解决方案：
  检查 LLM_MAX_TOKENS 设置
  export LLM_MAX_TOKENS=2048
  尝试重新运行
    """)


def example_8_comparison():
    """示例 8：提供商对比"""
    print("\n" + "="*60)
    print("示例 8：提供商功能对比")
    print("="*60)
    
    print("""
提供商 | 模型系列 | 成本 | 速度 | 工具调用 | 设置难度
--------|---------|------|------|---------|----------
OpenAI | GPT-4 | 最高 | 中等 | ✓ | 简单
Groq | Llama 3.3 | 低 | 最快 | ✗ | 简单
Ollama | 本地 | 无 | 取决于硬件 | × | 复杂
AiCanAPI | Claude | 中等 | 中等 | ✓ | 简单

推荐场景：
- 快速测试：使用 Groq（免费且快）
- 生产环境：使用 OpenAI 或 AiCanAPI（能力强）
- 本地部署：使用 Ollama（隐私好）
- Claude 任务：使用 AiCanAPI（是唯一的 Claude 来源）

切换提供商：
  export LLM_PROVIDER=openai
  python app.py --workspace ./project --query "修复 bug" --provider openai
    """)


def showcase():
    """展示所有示例"""
    print("""
╔═══════════════════════════════════════════════════════════╗
║         AiCanAPI 快速开始指南 - 完整示例集                    ║
╚═══════════════════════════════════════════════════════════╝
    """)
    
    example_1_basic_setup()
    example_2_config_verification()
    example_3_main_usage()
    example_4_model_switching()
    example_5_complete_workflow()
    example_6_environment_setup()
    example_7_troubleshooting()
    example_8_comparison()
    
    print("\n" + "="*60)
    print("📚 详细文档")
    print("="*60)
    print("""
主文档：        SIMPLE_USAGE.md
项目说明：      README.md
LLM 配置：      docs/LLM_SETUP.md
配置示例：      .env.example
测试指南：      TESTING_GUIDE.md
    """)


if __name__ == "__main__":
    import platform
    print(f"\n系统信息: {platform.system()} {platform.release()}")
    print(f"Python: {platform.python_version()}\n")
    
    showcase()
    
    print("\n✅ 快速开始指南完成")
    print("🚀 现在可以运行: python app.py --help")
