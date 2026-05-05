#!/usr/bin/env python3
"""CodeRepair LLM 快速配置工具"""

import os
from pathlib import Path

def main():
    print("\n" + "="*70)
    print("  🚀 CodeRepair LLM 快速配置".center(70))
    print("="*70 + "\n")
    
    project_root = Path(__file__).parent
    env_file = project_root / ".env"
    
    print("选择 LLM 提供商：\n")
    print("  1️⃣  Groq       (推荐！快速 + 免费)")
    print("  2️⃣  OpenAI     (功能完整)")
    print("  3️⃣  Ollama     (本地运行)")
    print("  4️⃣  退出\n")
    
    choice = input("请选择 (1-4): ").strip()
    
    if choice == "1":
        print("\n📝 Groq 配置步骤：")
        print("  1. 访问 https://console.groq.com/keys")
        print("  2. 创建 API Key")
        print("  3. 复制 API Key (以 gsk_ 开头)\n")
        
        api_key = input("请输入 Groq API Key: ").strip()
        if api_key:
            config = f"""LLM_PROVIDER=groq
GROQ_API_KEY={api_key}
GROQ_API_BASE=https://api.groq.com/openai/v1
GROQ_MODEL=llama-3.3-70b-versatile
"""
            env_file.write_text(config)
            print(f"\n✅ 配置已保存到 .env")
            print(f"🚀 现在可以运行: python3 examples/demo.py")
        else:
            print("❌ API Key 不能为空")
            
    elif choice == "2":
        print("\n📝 OpenAI 配置步骤：")
        print("  1. 访问 https://platform.openai.com/api-keys")
        print("  2. 创建 API Key")
        print("  3. 复制 API Key (以 sk- 开头)\n")
        
        api_key = input("请输入 OpenAI API Key: ").strip()
        if api_key:
            config = f"""LLM_PROVIDER=openai
OPENAI_API_KEY={api_key}
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_MODEL=gpt-4
"""
            env_file.write_text(config)
            print(f"\n✅ 配置已保存到 .env")
            print(f"🚀 现在可以运行: python3 examples/demo.py")
        else:
            print("❌ API Key 不能为空")
            
    elif choice == "3":
        print("\n📝 Ollama 配置步骤：")
        print("  1. 安装 Ollama: https://ollama.ai")
        print("  2. 启动: ollama serve")
        print("  3. 下载模型: ollama pull llama2\n")
        
        config = """LLM_PROVIDER=ollama
OLLAMA_API_BASE=http://localhost:11434/v1
OLLAMA_MODEL=llama2
"""
        env_file.write_text(config)
        print(f"✅ 配置已保存到 .env")
        print(f"🚀 确保 Ollama 已启动，然后运行: python3 examples/demo.py")
    
    elif choice == "4":
        print("👋 再见！")
        return
    else:
        print("❌ 无效选择")

if __name__ == "__main__":
    main()
