# LLM 配置指南

CodeRepair 支持多个 LLM 提供商。本指南说明如何配置不同的提供商。

## 支持的提供商

- ✅ **OpenAI** - 官方商用，功能最完整
- ✅ **Groq** - 快速免费（推荐快速测试）
- ✅ **Ollama** - 本地运行，完全隐私
- ✅ **模拟模式** - 测试用，无需 API Key

---

## 快速开始（5 分钟）

### 方案 1：使用 Groq（推荐，最简单）

**为什么选 Groq？**
- ✅ 完全免费
- ✅ 速度超快（比 OpenAI 块 10 倍以上）
- ✅ 无需信用卡
- ✅ 无流量限制（免费层）

**步骤：**

1️⃣ 获取 API Key
```bash
# 访问 https://console.groq.com/keys
# 在网页上创建新的 API Key
# 复制 API Key（格式: gsk_xxxxxxx）
```

2️⃣ 配置环境
```bash
# 创建 .env 文件
cp .env.example .env

# 编辑 .env 文件，配置如下：
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_api_key_here    # 粘贴您的 API Key
GROQ_MODEL=llama-3.3-70b-versatile     # 推荐模型
LLM_TIMEOUT=90                          # 建议的 HTTP 超时
```

3️⃣ 测试
```bash
./.venv/bin/python examples/demo.py

# 或运行主流程 smoke test
./.venv/bin/python app.py --workspace examples/sample_go_project --query "分析 Calculate 函数" --provider groq --no-validate
```

✅ 完成！现在 CodeRepair 默认会使用真实的 Groq API。

---

### 方案 2：使用 OpenAI

**为什么选 OpenAI？**
- ✅ 功能最完整
- ✅ 模型最新（GPT-4, GPT-4 Turbo）
- ✅ 生产环境推荐
- ⚠️ 需要付费，有月度上限

**步骤：**

1️⃣ 获取 API Key
```bash
# 访问 https://platform.openai.com/api-keys
# 创建新的 API Key
# 复制 API Key（格式: sk-xxxxxxx）
```

2️⃣ 配置环境
```bash
# 编辑 .env 文件
LLM_PROVIDER=openai
OPENAI_API_KEY=sk_your_api_key_here          # 粘贴您的 API Key
OPENAI_MODEL=gpt-4                            # 推荐模型，或用 gpt-3.5-turbo 更便宜
```

3️⃣ 推荐模型
```
GPT-4（功能最完整）
gpt-4-turbo-preview（平衡性能和成本）
gpt-3.5-turbo（最便宜）
```

---

### 方案 3：使用 Ollama（本地运行）

**为什么选 Ollama？**
- ✅ 完全免费
- ✅ 完全隐私（数据不离开本机）
- ✅ 无需 API Key
- ✅ 离线可用
- ⚠️ 需要本地计算资源

**步骤：**

1️⃣ 安装 Ollama
```bash
# macOS / Linux / Windows
# 访问 https://ollama.ai 下载安装

# 或 Linux 命令行安装
curl https://ollama.ai/install.sh | sh
```

2️⃣ 启动 Ollama 服务
```bash
# 启动 ollama 服务（保持运行）
ollama serve

# 在另一个终端窗口运行 CodeRepair
```

3️⃣ 下载模型
```bash
# 在新终端中，下载你想使用的模型
ollama pull llama2              # 7B 模型，轻量级
ollama pull mistral             # 7B 模型，快速
ollama pull neural-chat         # 优化的聊天模型
```

4️⃣ 配置环境
```bash
# 编辑 .env 文件
LLM_PROVIDER=ollama
OLLAMA_API_BASE=http://localhost:11434/v1
OLLAMA_MODEL=llama2            # 使用刚才下载的模型名称
```

5️⃣ 测试
```bash
python3 examples/demo.py
```

---

## 高级配置

### 自定义 API Base URL

如果您使用的是 OpenAI 兼容的第三方服务，可以自定义 API Base：

```bash
# .env 文件
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key_here
OPENAI_API_BASE=https://your-custom-api.com/v1    # 自定义 URL
```

### 调整模型参数

```bash
# 温度参数（创意度）
LLM_TEMPERATURE=0.7    # 0.0 = 确定，1.0 = 创意，2.0 = 疯狂

# 最大令牌数
# （在 config.py 中修改 LLM_MAX_TOKENS）
```

### 不同提供商的模型对比

| 提供商 | 模型 | 速度 | 质量 | 成本 | 推荐 |
|--------|------|------|------|------|------|
| Groq | mixtral-8x7b | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 免费 | 快速测试 ✅ |
| Groq | llama2-70b | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 免费 | 推荐 |
| OpenAI | gpt-4 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | $$ | 生产 |
| OpenAI | gpt-3.5-turbo | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | $ | 性价比 |
| Ollama | llama2 | ⭐⭐⭐ | ⭐⭐ | 免费 | 本地测试 |

---

## 常见问题

### Q1: 我没有 API Key，能否运行？

**A:** 可以！系统会自动进入**模拟模式**，使用内置的示例回复。对于测试和演示足够了。

```bash
# 不需要配置任何 API Key
python3 examples/demo.py    # 会使用模拟回复
python3 app.py --workspace examples/sample_go_project \
  --query "修复 Calculate 函数返回值错误" --no-validate
```

### Q2: Groq 是否真的免费？

**A:** 是的。Groq 免费层提供：
- 无限制的 API 请求
- 30 万元/月的免费请求限额
- 免费层模型：mixtral-8x7b, llama2-70b

足以进行大量的开发和测试。

### Q3: 如何在 Groq 和 OpenAI 之间切换？

**A:** 很简单！只需修改 .env 文件：

```bash
# 切换到 Groq
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_xxxxx

# 或切换到 OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=sk_xxxxx
```

无需修改任何代码，系统会自动使用正确的提供商。

### Q4: 如何检查当前使用的是哪个提供商？

**A:** 运行演示脚本时会看到日志输出：

```
[LLM] 初始化完成 | provider=groq | model=llama-3.3-70b-versatile | api_base=https://api.groq.com/openai/v1
```

### Q5: Ollama 的性能如何？

**A:**
- 需要特定的硬件（GPU 最优）
- 比 OpenAI/Groq 慢（本地运行）
- 但完全免费，隐私最好
- 适合离线开发、测试和演示

### Q6: 可否同时配置多个提供商？

**A:** 可以。所有配置都在 .env 文件中：

```bash
# 配置所有提供商的 API Key
OPENAI_API_KEY=sk_xxxxx
GROQ_API_KEY=gsk_xxxxx
OLLAMA_API_BASE=http://localhost:11434/v1

# 通过 LLM_PROVIDER 选择当前使用的提供商
LLM_PROVIDER=groq    # 切换为 groq
```

---

## 性能对比

### 响应速度

```
Groq        ████████████████ (最快，~0.5s)
OpenAI      ████████ (快，~2-3s)
Ollama      ██ (取决于硬件)
模拟模式    ████████████████ (即时)
```

### 代码质量

```
GPT-4       ████████████████ (最好)
GPT-3.5     ████████████ (很好)
Llama2-70B  ██████████ (不错)
Mixtral-8x7 ████████ (可以)
Llama2-7B   ██ (基础的)
```

### 成本

```
Groq        ✅ 免费
Ollama      ✅ 免费
GPT-3.5-T   💰 $0.0015/1K tokens
GPT-4       💰💰 $0.03/1K tokens
```

---

## 故障排查

### 问题 1：`GROQ_API_KEY 错误`

```
错误消息:
Authentication Error: verify-token-failed

解决方案:
1. 检查 API Key 是否完整（应该以 gsk_ 开头）
2. 重新复制 API Key（可能复制错了）
3. 检查 API Key 是否已激活（在 Groq 控制台刷新页面）
4. 确保没有空格或特殊字符
```

### 问题 2：`Ollama 连接错误`

```
错误消息:
Connection refused at http://localhost:11434/v1

解决方案:
1. 确保 Ollama 已启动: ollama serve
2. 确保没有改变默认端口
3. 检查防火墙设置
4. 尝试: curl http://localhost:11434/v1/models
```

### 问题 3：`模型不支持`

```
错误消息:
Model not found: some-model

解决方案:
1. 确保模型名称正确
2. 对于 Ollama，确保已下载: ollama pull model_name
3. 查看可用模型:
   - Groq: https://console.groq.com/docs/models
   - OpenAI: https://platform.openai.com/docs/models
   - Ollama: ollama list
```

---

## 生产环境建议

### 选择标准

| 场景 | 推荐 | 原因 |
|------|------|------|
| 快速测试 | Groq | 快速、免费 |
| 本地开发 | Ollama | 隐私、离线 |
| 生产环境 | OpenAI | 稳定、可靠 |
| 演示/演讲 | 模拟模式 | 稳定、无依赖 |

### API Key 管理

```bash
# ❌ 不要
vim .env                           # 不要把 API Key 存在版本控制中
git add .env                       # 不要提交 .env 到 Git

# ✅ 应该
echo ".env" >> .gitignore          # 忽略 .env 文件
cp .env.example .env               # 使用 .env.example 作为模板
# 在本地配置 .env 中填入 API Key
```

---

## 快速命令参考

```bash
# 使用 Groq（最简单）
echo 'LLM_PROVIDER=groq' > .env
echo 'GROQ_API_KEY=gsk_xxxxx' >> .env
./.venv/bin/python examples/demo.py

# 使用 OpenAI
echo 'LLM_PROVIDER=openai' > .env
echo 'OPENAI_API_KEY=sk_xxxxx' >> .env
./.venv/bin/python examples/demo.py

# 使用 Ollama
echo 'LLM_PROVIDER=ollama' > .env
ollama serve &                 # 后台启动
ollama pull llama2
./.venv/bin/python examples/demo.py

# 查看当前配置
grep "LLM_PROVIDER\|API_KEY\|API_BASE\|MODEL" .env | grep -v "^#"
```

---

## 总结

| 优先级 | 用途 | 提供商 | 配置难度 | 成本 |
|--------|------|--------|---------|------|
| 🥇 | 快速测试 | **Groq** | 简单 | 免费 |
| 🥈 | 本地开发 | **Ollama** | 中等 | 免费 |
| 🥉 | 生产环境 | **OpenAI** | 简单 | 付费 |
| 🎯 | 无需配置 | **模拟模式** | 内置 | 免费 |

**立即开始:** 选择 Groq，获得 API Key，配置 .env，5 分钟内开始使用！

---

需要帮助？查看 README.md、SIMPLE_USAGE.md，或运行 `./.venv/bin/python examples/demo.py`
