"""
全局配置管理模块
"""
import os
import warnings
from pathlib import Path

# 项目根目录
PLATFORM_ROOT = Path(__file__).resolve().parent

# 尝试加载环境变量文件（可选）
try:
    from dotenv import load_dotenv
    env_path = PLATFORM_ROOT / ".env"
    env_example_path = PLATFORM_ROOT / ".env.example"

    if env_path.exists():
        load_dotenv(env_path)
    elif env_example_path.exists():
        load_dotenv(env_example_path)
        warnings.warn(
            "检测到仅存在 .env.example，已作为本地回退配置加载。"
            "建议将其复制为 .env，并避免在 .env.example 中保存真实密钥。",
            RuntimeWarning,
        )
except ImportError:
    pass  # dotenv 不可用，使用环境变量


class Settings:
    """应用配置类"""
    
    # 平台路径
    PLATFORM_ROOT: Path = PLATFORM_ROOT
    ARTIFACTS_ROOT: Path = PLATFORM_ROOT / "artifacts"
    ARTIFACT_AUTO_CLEANUP: bool = os.getenv("ARTIFACT_AUTO_CLEANUP", "true").lower() == "true"
    ARTIFACT_RETENTION_SESSIONS: int = int(os.getenv("ARTIFACT_RETENTION_SESSIONS", "20"))
    ARTIFACT_RETENTION_DAYS: int = int(os.getenv("ARTIFACT_RETENTION_DAYS", "14"))
    
    # LLM 提供商选择 (openai, groq, ollama, aicanapi)
    # 默认使用 Groq，便于快速测试；未配置 Key 时会自动回退到 mock 模式。
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "groq").lower()
    
    # ==================== OpenAI 配置 ====================
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_API_BASE: str = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4")
    
    # ==================== Groq 配置 ====================
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_API_BASE: str = os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    
    # ==================== Ollama 配置 ====================
    OLLAMA_API_BASE: str = os.getenv("OLLAMA_API_BASE", "http://localhost:11434/v1")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama2")
    
    # ==================== AiCanAPI 配置 ====================
    AICANAPI_API_KEY: str = os.getenv("AICANAPI_API_KEY", "")
    AICANAPI_API_BASE: str = os.getenv("AICANAPI_API_BASE", "https://aicanapi.com/v1")
    AICANAPI_MODEL: str = os.getenv("AICANAPI_MODEL", "claude-opus-4-6")
    
    # ==================== 通用 LLM 配置 ====================
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    LLM_MAX_TOKENS: int = 4096
    LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "90"))
    LLM_CONNECT_TIMEOUT: int = int(os.getenv("LLM_CONNECT_TIMEOUT", "10"))
    LLM_READ_TIMEOUT: int = int(os.getenv("LLM_READ_TIMEOUT", str(LLM_TIMEOUT)))
    LLM_RETRY_ATTEMPTS: int = int(os.getenv("LLM_RETRY_ATTEMPTS", "1"))
    LLM_ALLOW_MOCK: bool = os.getenv("LLM_ALLOW_MOCK", "true").lower() == "true"
    
    @property
    def LLM_MODEL(self) -> str:
        """根据提供商返回对应的模型"""
        if self.LLM_PROVIDER == "groq":
            return self.GROQ_MODEL
        elif self.LLM_PROVIDER == "ollama":
            return self.OLLAMA_MODEL
        elif self.LLM_PROVIDER == "aicanapi":
            return self.AICANAPI_MODEL
        else:  # openai
            return self.OPENAI_MODEL
    
    @property
    def LLM_API_KEY(self) -> str:
        """根据提供商返回对应的 API Key"""
        if self.LLM_PROVIDER == "groq":
            return self.GROQ_API_KEY
        elif self.LLM_PROVIDER == "openai":
            return self.OPENAI_API_KEY
        elif self.LLM_PROVIDER == "aicanapi":
            return self.AICANAPI_API_KEY
        else:  # ollama 通常不需要 API Key
            return ""
    
    @property
    def LLM_API_BASE(self) -> str:
        """根据提供商返回对应的 API Base URL"""
        if self.LLM_PROVIDER == "groq":
            return self.GROQ_API_BASE
        elif self.LLM_PROVIDER == "ollama":
            return self.OLLAMA_API_BASE
        elif self.LLM_PROVIDER == "aicanapi":
            return self.AICANAPI_API_BASE
        else:  # openai
            return self.OPENAI_API_BASE
    
    # 日志配置
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # 检索配置
    RAG_BACKEND: str = os.getenv("RAG_BACKEND", "hybrid").lower()
    RETRIEVAL_TOP_K: int = 5
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 100
    ANALYSIS_MAX_FILES: int = int(os.getenv("ANALYSIS_MAX_FILES", "80"))
    RETRIEVAL_MAX_FILES: int = int(os.getenv("RETRIEVAL_MAX_FILES", "200"))
    LEXICAL_BACKEND: str = os.getenv("LEXICAL_BACKEND", "bm25").lower()
    BM25_K1: float = float(os.getenv("BM25_K1", "1.5"))
    BM25_B: float = float(os.getenv("BM25_B", "0.75"))
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "ollama").lower()
    VECTOR_EMBEDDING_DIM: int = int(os.getenv("VECTOR_EMBEDDING_DIM", "384"))
    VECTOR_RETRIEVAL_CANDIDATES: int = int(os.getenv("VECTOR_RETRIEVAL_CANDIDATES", "20"))
    RERANK_ENABLED: bool = os.getenv("RERANK_ENABLED", "true").lower() == "true"
    RERANK_TOP_N: int = int(os.getenv("RERANK_TOP_N", "10"))
    VECTOR_DB_ROOT: Path = PLATFORM_ROOT / ".coderepair_vector_db"
    VECTOR_DB_PATH: Path = VECTOR_DB_ROOT / "vectors.sqlite3"
    OLLAMA_EMBED_MODEL: str = os.getenv("OLLAMA_EMBED_MODEL", "embeddinggemma")
    OLLAMA_EMBED_TIMEOUT: int = int(os.getenv("OLLAMA_EMBED_TIMEOUT", "30"))
    
    # 验证配置
    VALIDATION_TIMEOUT: int = 30
    
    # 文件过滤规则
    EXCLUDE_PATTERNS: list = [
        ".git", ".venv", "venv", "__pycache__", ".pytest_cache",
        "node_modules", ".idea", ".vscode", ".DS_Store",
        "*.pyc", "*.pyo", "*.pyd", ".Python",
        "build", "dist", "*.egg-info", ".coverage",
        "artifacts",
    ]
    
    # 仓库扫描配置
    INCLUDE_EXTENSIONS: dict = {
        "go": [".go", ".mod", ".sum", ".md", ".yaml", ".yml", ".json", ".toml", ".sh"],
        "python": [".py", ".md", ".yaml", ".yml", ".json", ".toml", ".sh"],
    }
    INCLUDE_FILENAMES: dict = {
        "go": ["Dockerfile", "Makefile", ".dockerignore"],
        "python": ["Dockerfile", "Makefile", ".dockerignore", "requirements.txt", "pyproject.toml"],
    }
    
    def ensure_artifacts_root(self):
        """确保 artifacts 目录存在"""
        self.ARTIFACTS_ROOT.mkdir(parents=True, exist_ok=True)


# 全局配置实例
settings = Settings()
settings.ensure_artifacts_root()
