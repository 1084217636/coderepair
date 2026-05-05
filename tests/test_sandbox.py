"""
Docker 沙盒测试
"""

import pytest
import tempfile
import os
import shutil

from sandbox import DockerRunner, SandboxResult, SandboxConfig


def _docker_available() -> bool:
    """检查 Docker 是否可用"""
    import subprocess
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except:
        return False


class TestSandboxConfig:
    """沙盒配置测试"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = SandboxConfig()
        
        assert config.go_version == "1.21"
        assert config.timeout_seconds == 300
        assert config.memory_limit == "2g"
        assert config.cpu_limit == "1"
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = SandboxConfig(
            go_version="1.20",
            timeout_seconds=120,
            memory_limit="4g"
        )
        
        assert config.go_version == "1.20"
        assert config.timeout_seconds == 120
        assert config.memory_limit == "4g"
    
    def test_get_image(self):
        """测试获取 Docker 镜像"""
        config1 = SandboxConfig(go_version="1.21")
        assert config1.get_image() == "golang:1.21-alpine"
        
        config2 = SandboxConfig(docker_image="custom/go:latest")
        assert config2.get_image() == "custom/go:latest"


class TestSandboxResult:
    """沙盒结果测试"""
    
    def test_result_initialization(self):
        """测试结果初始化"""
        from sandbox.docker_runner import SandboxType
        
        result = SandboxResult(
            success=True,
            sandbox_type=SandboxType.COMPILATION
        )
        
        assert result.success
        assert result.exit_code == 0
    
    def test_result_to_dict(self):
        """测试结果转字典"""
        from sandbox.docker_runner import SandboxType
        
        result = SandboxResult(
            success=True,
            sandbox_type=SandboxType.COMPILATION,
            output="Build successful",
            duration=2.5
        )
        
        result_dict = result.to_dict()
        
        assert "success" in result_dict
        assert result_dict["success"]
        assert "duration" in result_dict


class TestDockerRunner:
    """Docker 运行器测试（可选，需要 Docker）"""

    def test_try_create_returns_reason_when_docker_missing(self, monkeypatch):
        """try_create 在 Docker 缺失时返回错误原因，而不是直接抛异常。"""
        import subprocess

        def fake_run(*args, **kwargs):
            raise FileNotFoundError("docker missing")

        monkeypatch.setattr(subprocess, "run", fake_run)

        runner, error = DockerRunner.try_create()

        assert runner is None
        assert "docker missing" in error
    
    @pytest.fixture
    def temp_go_project(self):
        """创建临时 Go 项目"""
        temp_dir = tempfile.mkdtemp(prefix="test_sandbox_")
        
        # 创建 go.mod
        with open(os.path.join(temp_dir, "go.mod"), "w") as f:
            f.write("module github.com/test/sandbox\n\ngo 1.21\n")
        
        # 创建简单的 Go 文件
        with open(os.path.join(temp_dir, "main.go"), "w") as f:
            f.write("""package main

import "fmt"

func main() {
    fmt.Println("Hello, World!")
}
""")
        
        yield temp_dir
        
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    @pytest.mark.skipif(
        not _docker_available(),
        reason="Docker not available"
    )
    def test_docker_runner_initialization(self):
        """测试 Docker 运行器初始化（可选）"""
        try:
            runner = DockerRunner()
            assert runner.docker_cmd == "docker"
        except RuntimeError:
            pytest.skip("Docker not available")
    
    @pytest.mark.skipif(
        not _docker_available(),
        reason="Docker not available"
    )
    def test_compilation_valid_code(self, temp_go_project):
        """测试编译有效代码（可选）"""
        try:
            runner = DockerRunner()
            result = runner.run_compilation(
                temp_go_project,
                go_version="1.21"
            )
            
            # 简单的有效代码应该能编译
            assert isinstance(result, SandboxResult)
        except RuntimeError:
            pytest.skip("Docker not available")
    
    @pytest.mark.skipif(
        not _docker_available(),
        reason="Docker not available"
    )
    def test_sandbox_result_is_valid(self, temp_go_project):
        """测试沙盒结果有效性（可选）"""
        try:
            runner = DockerRunner()
            result = runner.run_compilation(temp_go_project)
            
            # 检查结果结构
            assert hasattr(result, "success")
            assert hasattr(result, "output")
            assert hasattr(result, "error_output")
            assert hasattr(result, "duration")
        except RuntimeError:
            pytest.skip("Docker not available")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
