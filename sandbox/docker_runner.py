"""
Docker 沙盒验证模块

在隔离的 Docker 容器中编译和测试 Go 代码，确保修复后的代码：
- 编译通过
- 测试通过
- 没有运行时错误

特点：
- 自动创建临时容器
- 挂载项目目录
- 执行编译和测试
- 清理资源
- 支持自定义命令

示例：
    ```python
    runner = DockerRunner()
    
    result = runner.run_compilation(
        project_path="/home/project/myservice",
        go_version="1.21"
    )
    
    if result.success:
        print(f"✓ 编译成功 ({result.duration:.2f}s)")
    else:
        print(f"✗ 编译失败: {result.error_output}")
    ```
"""

import subprocess
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from datetime import datetime
import tempfile
import shutil


class SandboxType(Enum):
    """沙盒类型"""
    COMPILATION = "compilation"     # 编译验证
    TESTING = "testing"             # 单元测试
    LINTING = "linting"             # 代码检查
    BENCHMARKING = "benchmarking"   # 性能基准测试


@dataclass
class SandboxConfig:
    """沙盒配置"""
    go_version: str = "1.21"
    docker_image: Optional[str] = None
    timeout_seconds: int = 300
    memory_limit: str = "2g"
    cpu_limit: str = "1"
    environment: Dict[str, str] = field(default_factory=dict)
    
    def get_image(self) -> str:
        """获取 Docker 镜像"""
        if self.docker_image:
            return self.docker_image
        return f"golang:{self.go_version}-alpine"


@dataclass
class SandboxResult:
    """沙盒执行结果"""
    success: bool
    sandbox_type: SandboxType
    output: str = ""
    error_output: str = ""
    exit_code: int = 0
    duration: float = 0.0
    container_id: Optional[str] = None
    
    # 详细信息
    compilation_errors: List[Dict[str, Any]] = field(default_factory=list)
    test_results: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """转为字典"""
        return {
            "success": self.success,
            "sandbox_type": self.sandbox_type.value,
            "output": self.output,
            "error_output": self.error_output,
            "exit_code": self.exit_code,
            "duration": self.duration,
            "compilation_errors": len(self.compilation_errors),
            "test_passed": self.test_results.get("passed", 0) if self.test_results else 0,
            "created_at": self.created_at,
        }


class DockerRunner:
    """
    Docker 沙盒运行器
    
    在隔离的 Docker 容器中执行 Go 项目的编译、测试、检查等操作。
    
    特点：
    - 使用官方 Go Docker 镜像
    - 自动清理容器
    - 支持自定义环境变量
    - 超时保护
    - 详细的错误输出
    
    示例：
        ```python
        runner = DockerRunner()
        
        # 编译验证
        result = runner.run_compilation(
            project_path="/home/project",
            go_version="1.21"
        )
        
        # 运行测试
        result = runner.run_tests(
            project_path="/home/project",
            test_timeout="30s"
        )
        
        # 代码检查
        result = runner.run_linting(
            project_path="/home/project"
        )
        ```
    """
    
    def __init__(self, docker_client_cmd: str = "docker"):
        """初始化 Docker 运行器
        
        Args:
            docker_client_cmd: Docker 命令（默认 "docker"）
        """
        self.docker_cmd = docker_client_cmd
        self._verify_docker()

    @classmethod
    def try_create(
        cls,
        docker_client_cmd: str = "docker",
    ) -> Tuple[Optional["DockerRunner"], str]:
        """尝试创建运行器，失败时返回空对象和原因。"""
        try:
            return cls(docker_client_cmd=docker_client_cmd), ""
        except RuntimeError as e:
            return None, str(e)
    
    def _verify_docker(self) -> bool:
        """验证 Docker 是否可用"""
        try:
            result = subprocess.run(
                [self.docker_cmd, "--version"],
                capture_output=True,
                timeout=5,
                text=True
            )
            if result.returncode != 0:
                raise RuntimeError("Docker 不可用")
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            raise RuntimeError(f"Docker 初始化失败: {e}")
    
    def run_compilation(
        self,
        project_path: str,
        go_version: str = "1.21",
        module_path: Optional[str] = None,
        config: Optional[SandboxConfig] = None,
    ) -> SandboxResult:
        """
        运行编译验证
        
        Args:
            project_path: 项目路径
            go_version: Go 版本
            module_path: 模块路径（可选）
            config: 沙盒配置
        
        Returns:
            SandboxResult: 编译结果
        
        示例：
            ```python
            result = runner.run_compilation("/home/project")
            print(f"编译状态: {'✓' if result.success else '✗'}")
            ```
        """
        if config is None:
            config = SandboxConfig(go_version=go_version)
        
        commands = []
        if module_path:
            commands.extend([
                f"cd /workspace && go mod tidy",
                f"cd /workspace && go build -v ./...",
            ])
        else:
            commands.extend([
                f"cd /workspace && go build -v ./...",
            ])
        
        return self._run_in_container(
            project_path=project_path,
            commands=commands,
            sandbox_type=SandboxType.COMPILATION,
            config=config,
        )
    
    def run_tests(
        self,
        project_path: str,
        test_timeout: str = "120s",
        coverage: bool = True,
        config: Optional[SandboxConfig] = None,
    ) -> SandboxResult:
        """
        运行单元测试
        
        Args:
            project_path: 项目路径
            test_timeout: 测试超时时间
            coverage: 是否生成覆盖率报告
            config: 沙盒配置
        
        Returns:
            SandboxResult: 测试结果
        
        示例：
            ```python
            result = runner.run_tests(
                "/home/project",
                test_timeout="60s",
                coverage=True
            )
            if result.success:
                print(f"✓ 所有测试通过")
            ```
        """
        if config is None:
            config = SandboxConfig()
        
        commands = ["cd /workspace && go mod tidy"]
        
        if coverage:
            commands.append(
                f"cd /workspace && go test -v -timeout {test_timeout} -coverprofile=coverage.out ./... && go tool cover -func=coverage.out"
            )
        else:
            commands.append(
                f"cd /workspace && go test -v -timeout {test_timeout} ./..."
            )
        
        return self._run_in_container(
            project_path=project_path,
            commands=commands,
            sandbox_type=SandboxType.TESTING,
            config=config,
        )
    
    def run_linting(
        self,
        project_path: str,
        linters: Optional[List[str]] = None,
        config: Optional[SandboxConfig] = None,
    ) -> SandboxResult:
        """
        运行代码检查
        
        Args:
            project_path: 项目路径
            linters: 检查工具列表（未指定则使用默认 gofmt 和 go vet）
            config: 沙盒配置
        
        Returns:
            SandboxResult: 检查结果
        
        示例：
            ```python
            result = runner.run_linting("/home/project")
            ```
        """
        if config is None:
            config = SandboxConfig()
        
        if linters is None:
            linters = ["gofmt", "go vet"]
        
        commands = ["cd /workspace && go mod tidy"]
        
        for linter in linters:
            if linter == "gofmt":
                commands.append("cd /workspace && gofmt -l .")
            elif linter == "go vet":
                commands.append("cd /workspace && go vet ./...")
            elif linter == "golangci-lint":
                commands.append(
                    "cd /workspace && "
                    "apt-get update && apt-get install -y golangci-lint && "
                    "golangci-lint run ./..."
                )
        
        return self._run_in_container(
            project_path=project_path,
            commands=commands,
            sandbox_type=SandboxType.LINTING,
            config=config,
        )
    
    def run_custom(
        self,
        project_path: str,
        commands: List[str],
        config: Optional[SandboxConfig] = None,
    ) -> SandboxResult:
        """
        运行自定义命令
        
        Args:
            project_path: 项目路径
            commands: 要执行的命令列表
            config: 沙盒配置
        
        Returns:
            SandboxResult: 执行结果
        """
        if config is None:
            config = SandboxConfig()
        
        return self._run_in_container(
            project_path=project_path,
            commands=commands,
            sandbox_type=SandboxType.BENCHMARKING,
            config=config,
        )
    
    def _run_in_container(
        self,
        project_path: str,
        commands: List[str],
        sandbox_type: SandboxType,
        config: SandboxConfig,
    ) -> SandboxResult:
        """在容器中执行命令（内部方法）"""
        
        import time
        start_time = time.time()
        
        # 验证项目路径
        if not os.path.isdir(project_path):
            return SandboxResult(
                success=False,
                sandbox_type=sandbox_type,
                error_output=f"项目路径不存在: {project_path}",
                exit_code=1,
            )
        
        # 准备容器命令
        container_cmd = f"set -e\n" + "\n".join(commands)
        
        # 构建 Docker 运行命令
        docker_run_cmd = [
            self.docker_cmd, "run", "--rm",
            f"--memory={config.memory_limit}",
            f"--cpus={config.cpu_limit}",
            "-v", f"{os.path.abspath(project_path)}:/workspace",
            config.get_image(),
            "sh", "-c", container_cmd,
        ]
        
        # 添加环境变量
        for key, value in config.environment.items():
            docker_run_cmd.insert(docker_run_cmd.index("--rm") + 1, "-e")
            docker_run_cmd.insert(docker_run_cmd.index("--rm") + 2, f"{key}={value}")
        
        try:
            # 执行容器
            process = subprocess.Popen(
                docker_run_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            
            try:
                stdout, stderr = process.communicate(timeout=config.timeout_seconds)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                duration = time.time() - start_time
                return SandboxResult(
                    success=False,
                    sandbox_type=sandbox_type,
                    output=stdout,
                    error_output=f"执行超时 (>{config.timeout_seconds}s)\n{stderr}",
                    exit_code=-1,
                    duration=duration,
                )
            
            duration = time.time() - start_time
            success = process.returncode == 0
            
            return SandboxResult(
                success=success,
                sandbox_type=sandbox_type,
                output=stdout,
                error_output=stderr,
                exit_code=process.returncode,
                duration=duration,
            )
        
        except Exception as e:
            duration = time.time() - start_time
            return SandboxResult(
                success=False,
                sandbox_type=sandbox_type,
                error_output=f"Docker 执行异常: {str(e)}",
                exit_code=-1,
                duration=duration,
            )


def verify_sandbox_environment() -> Tuple[bool, str]:
    """
    验证沙盒环境（检查 Docker 是否可用）
    
    Returns:
        (是否可用, 错误消息)
    
    示例：
        ```python
        available, error = verify_sandbox_environment()
        if not available:
            print(f"沙盒不可用: {error}")
        ```
    """
    runner, error = DockerRunner.try_create()
    return runner is not None, error
