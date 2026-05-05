"""
项目模板定义

提供预设的 Go 项目模板，支持：
  • Web Service
  • CLI Tool
  • Go Library
  • gRPC Service
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Optional


class TemplateType(Enum):
    """项目模板类型"""
    WEB = "web"           # Web 服务
    CLI = "cli"           # 命令行工具
    LIBRARY = "library"   # Go 库
    GRPC = "grpc"         # gRPC 服务


@dataclass
class Dependency:
    """依赖包"""
    name: str
    version: str = ""      # 空表示最新版本


@dataclass
class ProjectTemplate:
    """项目模板"""
    type: TemplateType
    name: str
    description: str
    
    # 目录结构
    directories: List[str]
    
    # 初始文件
    files: Dict[str, str]  # 文件路径 -> 内容
    
    # 依赖包
    dependencies: List[Dependency]
    
    # 可选：go.mod 初始配置
    module_path: str = ""
    
    # 可选：Makefile 命令
    makefile_targets: Dict[str, str] = None


# ==================== 项目模板库 ====================

TEMPLATES = {
    TemplateType.WEB: ProjectTemplate(
        type=TemplateType.WEB,
        name="Simple Web Service",
        description="HTTP Web 服务（带路由、中间件、优雅关闭）",
        
        directories=[
            ".",
            "./cmd/server",
            "./internal/handler",
            "./internal/middleware",
            "./internal/config",
            "./pkg/logger",
            "./pkg/response",
            "./tests",
        ],
        
        files={
            "go.mod": "module {module_path}\n\ngo 1.21",
            
            "go.sum": "",
            
            "main.go": '''package main

import "fmt"

func main() {
    fmt.Println("Welcome to {project_name}!")
    fmt.Println("Start the server with: make run")
}
''',
            
            "cmd/server/main.go": '''package main

import (
    "context"
    "fmt"
    "log"
    "net/http"
    "os"
    "os/signal"
    "syscall"
    "time"

    "github.com/gorilla/mux"
    "{module_path}/internal/handler"
    "{module_path}/pkg/logger"
)

func main() {
    // 初始化日志
    logger.Init()
    defer logger.Close()

    // 创建路由
    router := mux.NewRouter()
    
    // 注册处理器
    router.HandleFunc("/health", handler.Health).Methods("GET")
    router.HandleFunc("/api/hello", handler.Hello).Methods("GET")

    // 创建服务器
    srv := &http.Server{
        Addr:         ":8080",
        Handler:      router,
        ReadTimeout:  15 * time.Second,
        WriteTimeout: 15 * time.Second,
        IdleTimeout:  60 * time.Second,
    }

    // 启动服务器（在 goroutine 中）
    go func() {
        logger.Info("Starting server on %s", srv.Addr)
        if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
            logger.Error("Server error: %v", err)
            os.Exit(1)
        }
    }()

    // 等待中断信号
    sigChan := make(chan os.Signal, 1)
    signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
    <-sigChan

    // 优雅关闭
    logger.Info("Shutting down server...")
    ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    defer cancel()
    
    if err := srv.Shutdown(ctx); err != nil {
        logger.Error("Server shutdown error: %v", err)
        os.Exit(1)
    }
    
    logger.Info("Server stopped")
}
''',
            
            "internal/handler/handler.go": '''package handler

import (
    "encoding/json"
    "net/http"
)

type Response struct {
    Code    int         `json:"code"`
    Message string      `json:"message"`
    Data    interface{} `json:"data,omitempty"`
}

// Health 健康检查处理器
func Health(w http.ResponseWriter, r *http.Request) {
    resp := Response{
        Code:    200,
        Message: "ok",
    }
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(resp)
}

// Hello 示例处理器
func Hello(w http.ResponseWriter, r *http.Request) {
    name := r.URL.Query().Get("name")
    if name == "" {
        name = "World"
    }
    
    resp := Response{
        Code:    200,
        Message: "success",
        Data: map[string]string{
            "greeting": "Hello, " + name + "!",
        },
    }
    
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(resp)
}
''',
            
            "pkg/logger/logger.go": '''package logger

import (
    "fmt"
    "os"
    "time"
)

var (
    infoLog    *os.File
    errorLog   *os.File
)

func Init() {
    // 初始化日志文件
    var err error
    infoLog, err = os.OpenFile("logs/info.log", os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0666)
    if err != nil {
        fmt.Printf("Failed to open info log: %v\\n", err)
    }
    
    errorLog, err = os.OpenFile("logs/error.log", os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0666)
    if err != nil {
        fmt.Printf("Failed to open error log: %v\\n", err)
    }
}

func Close() {
    if infoLog != nil {
        infoLog.Close()
    }
    if errorLog != nil {
        errorLog.Close()
    }
}

func Info(format string, args ...interface{}) {
    msg := fmt.Sprintf(format, args...)
    timestamp := time.Now().Format("2006-01-02 15:04:05")
    fmt.Printf("[%s] INFO: %s\\n", timestamp, msg)
    if infoLog != nil {
        fmt.Fprintf(infoLog, "[%s] INFO: %s\\n", timestamp, msg)
    }
}

func Error(format string, args ...interface{}) {
    msg := fmt.Sprintf(format, args...)
    timestamp := time.Now().Format("2006-01-02 15:04:05")
    fmt.Printf("[%s] ERROR: %s\\n", timestamp, msg)
    if errorLog != nil {
        fmt.Fprintf(errorLog, "[%s] ERROR: %s\\n", timestamp, msg)
    }
}
''',
            
            "Makefile": '''
.PHONY: build run test clean

help:
\t@echo "Available targets:"
\t@echo "  build   - Build the server"
\t@echo "  run     - Run the server"
\t@echo "  test    - Run tests"
\t@echo "  clean   - Clean build artifacts"

build:
\tgo build -o bin/server ./cmd/server

run:
\t./bin/server

test:
\tgo test -v ./...

clean:
\trm -rf bin/ logs/
''',
            
            ".gitignore": '''# Binaries
bin/
dist/
*.o
*.a
*.so

# Test binaries
*.test
*.out

# Dependencies
vendor/

# IDE
.idea/
.vscode/
*.swp
*.swo

# OS
.DS_Store
.env
.env.local

# Logs
logs/
*.log
''',
        },
        
        dependencies=[
            Dependency("github.com/gorilla/mux", "v1.8.0"),
        ],
    ),
    
    TemplateType.CLI: ProjectTemplate(
        type=TemplateType.CLI,
        name="Simple CLI Tool",
        description="命令行工具（使用 cobra）",
        
        directories=[
            ".",
            "./cmd",
            "./internal",
            "./pkg",
        ],
        
        files={
            "go.mod": "module {module_path}\n\ngo 1.21",
            
            "go.sum": "",
            
            "main.go": '''package main

import (
    "fmt"
    "os"

    "github.com/spf13/cobra"
)

var (
    verbose bool
)

var rootCmd = &cobra.Command{
    Use:   "myapp",
    Short: "A simple CLI tool",
    Long:  `A simple CLI tool built with Cobra`,
    Run: func(cmd *cobra.Command, args []string) {
        fmt.Println("Hello from myapp!")
    },
}

var versionCmd = &cobra.Command{
    Use:   "version",
    Short: "Show version",
    Run: func(cmd *cobra.Command, args []string) {
        fmt.Println("myapp version 1.0.0")
    },
}

func init() {
    rootCmd.PersistentFlags().BoolVarP(&verbose, "verbose", "v", false, "verbose output")
    rootCmd.AddCommand(versionCmd)
}

func main() {
    if err := rootCmd.Execute(); err != nil {
        fmt.Println(err)
        os.Exit(1)
    }
}
''',
            
            "Makefile": '''
.PHONY: build run test clean

build:
\tgo build -o myapp .

run:
\t./myapp

test:
\tgo test -v ./...

clean:
\trm -f myapp
''',
            
            ".gitignore": '''myapp
*.log
.env
vendor/
.idea/
.vscode/
''',
        },
        
        dependencies=[
            Dependency("github.com/spf13/cobra", "v1.7.0"),
        ],
    ),
    
    TemplateType.LIBRARY: ProjectTemplate(
        type=TemplateType.LIBRARY,
        name="Go Library",
        description="可复用的 Go 库",
        
        directories=[
            ".",
            "./example",
            "./tests",
        ],
        
        files={
            "go.mod": "module {module_path}\n\ngo 1.21",
            
            "go.sum": "",
            
            "lib.go": '''package {package_name}

// MyFunc 示例函数
func MyFunc(value string) string {
    return "Result: " + value
}
''',
            
            "lib_test.go": '''package {package_name}

import "testing"

func TestMyFunc(t *testing.T) {
    result := MyFunc("test")
    expected := "Result: test"
    if result != expected {
        t.Errorf("Expected %s, got %s", expected, result)
    }
}
''',
            
            "README.md": '''# {module_path}

## Description
Add library description here

## Installation
\`\`\`bash
go get {module_path}
\`\`\`

## Usage
\`\`\`go
import "{module_path}"

// Use the library
\`\`\`

## License
MIT
''',
        },
        
        dependencies=[],
    ),
}


def get_template(template_type: TemplateType) -> ProjectTemplate:
    """获取指定类型的模板"""
    if template_type not in TEMPLATES:
        raise ValueError(f"Unknown template type: {template_type}")
    return TEMPLATES[template_type]
