"""
验证执行模块 - 执行构建、测试和自定义命令
"""
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from core.logger import get_logger
from config import settings

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """统一的验证结果结构。"""

    success: bool
    source: str
    stage: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration: float = 0.0
    timed_out: bool = False
    skipped_reason: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "source": self.source,
            "stage": self.stage,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration": self.duration,
            "timed_out": self.timed_out,
            "skipped_reason": self.skipped_reason,
            "raw": self.raw,
        }

    @classmethod
    def skipped(cls, stage: str, reason: str) -> "ValidationResult":
        return cls(
            success=False,
            source="skipped",
            stage=stage,
            exit_code=-1,
            skipped_reason=reason,
        )

    @classmethod
    def from_sandbox_result(cls, sandbox_result: Any, stage: str) -> "ValidationResult":
        return cls(
            success=sandbox_result.success,
            source="docker",
            stage=stage,
            exit_code=sandbox_result.exit_code,
            stdout=sandbox_result.output,
            stderr=sandbox_result.error_output,
            duration=sandbox_result.duration,
            timed_out=sandbox_result.exit_code == -1 and "超时" in sandbox_result.error_output,
            raw=sandbox_result.to_dict(),
        )


class Validator:
    """
    验证执行器

    职责：
    1. 执行本地构建/测试/自定义命令
    2. 捕获输出和错误信息
    3. 返回统一的验证结果结构
    """

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.logger = get_logger(__name__)

    def run_command(
        self,
        cmd: str,
        timeout: Optional[int] = None,
        stage: str = "custom",
    ) -> ValidationResult:
        """
        执行本地验证命令。

        Args:
            cmd: 命令字符串
            timeout: 超时时间（秒）
            stage: 阶段标识，如 build / test / custom
        """
        self.logger.info(f"[Stage 9] 执行本地验证命令 | stage={stage} | cmd={cmd}")

        if timeout is None:
            timeout = settings.VALIDATION_TIMEOUT

        started_at = time.time()

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration = time.time() - started_at

            output = ValidationResult(
                success=result.returncode == 0,
                source="local",
                stage=stage,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration=duration,
                raw={
                    "cmd": cmd,
                    "cwd": str(self.workspace_root),
                },
            )

            if output.success:
                self.logger.info("[Stage 9] 本地验证成功 | exit_code=0")
            else:
                self.logger.warning(
                    f"[Stage 9] 本地验证失败 | stage={stage} | exit_code={result.returncode}"
                )

            self.logger.debug(f"[Validator] stdout 长度: {len(result.stdout)}")
            self.logger.debug(f"[Validator] stderr 长度: {len(result.stderr)}")

            return output

        except subprocess.TimeoutExpired:
            duration = time.time() - started_at
            self.logger.error(f"[Stage 9] 本地验证超时 | stage={stage} | timeout={timeout}s")
            return ValidationResult(
                success=False,
                source="local",
                stage=stage,
                exit_code=-1,
                stderr=f"Command timeout after {timeout}s",
                duration=duration,
                timed_out=True,
                raw={
                    "cmd": cmd,
                    "cwd": str(self.workspace_root),
                },
            )

        except Exception as e:
            duration = time.time() - started_at
            self.logger.error(f"[Stage 9] 本地验证异常 | stage={stage} | error={e}")
            return ValidationResult(
                success=False,
                source="local",
                stage=stage,
                exit_code=-1,
                stderr=str(e),
                duration=duration,
                raw={
                    "cmd": cmd,
                    "cwd": str(self.workspace_root),
                },
            )

    def run_go_tests(self) -> ValidationResult:
        return self.run_command("go test ./...", stage="test")

    def run_go_build(self) -> ValidationResult:
        return self.run_command("go build ./...", stage="build")

    def run_python_tests(self) -> ValidationResult:
        return self.run_command("python -m pytest .", stage="test")

    def run_custom(self, cmd: str, stage: str = "custom") -> ValidationResult:
        return self.run_command(cmd, stage=stage)
