"""
Pytest 配置文件

提供测试 fixtures 和配置
"""

import pytest
import os
import sys

# 将项目根目录加入 Python 路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture(scope="session")
def project_root():
    """项目根目录"""
    return PROJECT_ROOT


@pytest.fixture
def sample_go_code():
    """示例 Go 代码"""
    return """package main

import (
    "fmt"
    "log"
)

func main() {
    GetUser()
}

func GetUser() {
    var data interface{}
    data = 123
    _ = data.(string)
}
"""


@pytest.fixture
def sample_go_module():
    """示例 go.mod"""
    return """module github.com/test/sample

go 1.21

require (
    github.com/gorilla/mux v1.8.0
)
"""


def pytest_configure(config):
    """Pytest 配置钩子"""
    # 添加自定义标记
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "docker: marks tests that require Docker"
    )


def pytest_collection_modifyitems(config, items):
    """修改收集的测试项"""
    # 自动标记某些测试
    for item in items:
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        if "docker" in item.nodeid or "sandbox" in item.nodeid:
            item.add_marker(pytest.mark.docker)
