"""Gateway router package.

Keep this package lightweight: importing one router for tests should not eagerly
import every router and its optional runtime dependencies.
"""

__all__ = [
    "agents",
    "anchored_branch",
    "artifacts",
    "assistants_compat",
    "auth",
    "channel_connections",
    "channels",
    "code_change",
    "features",
    "feedback",
    "mcp",
    "memory",
    "models",
    "runs",
    "skills",
    "suggestions",
    "thread_runs",
    "threads",
    "uploads",
]
