"""
统一日志模块（使用标准库 logging）
"""
import sys
import logging
from pathlib import Path
from config import settings


class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        if record.levelname in self.COLORS:
            color = self.COLORS[record.levelname]
            record.levelname = f"{color}{record.levelname:8}{self.RESET}"
        
        # 自定义格式
        fmt = "[{asctime}] {levelname} | {name}:{funcName}:{lineno} - {message}"
        formatter = logging.Formatter(fmt, datefmt="%H:%M:%S", style="{")
        return formatter.format(record)


_loggers = {}


def setup_logger(log_file: Path = None) -> None:
    """
    配置日志系统
    
    Args:
        log_file: 日志文件路径
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL)
    
    # 移除现有处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 终端处理器（彩色）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(settings.LOG_LEVEL)
    console_handler.setFormatter(ColoredFormatter())
    root_logger.addHandler(console_handler)
    
    # 文件处理器
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
        file_handler.setLevel(settings.LOG_LEVEL)
        fmt = "[{asctime}] {levelname:8} | {name}:{funcName}:{lineno} - {message}"
        formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S", style="{")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def get_logger(name: str):
    """
    获取 logger 实例
    
    Args:
        name: Logger 名字
    
    Returns:
        配置好的 logger
    """
    if name not in _loggers:
        logger = logging.getLogger(name)
        logger.setLevel(settings.LOG_LEVEL)
        _loggers[name] = logger
    return _loggers[name]


# 初始化默认 logger（仅终端）
setup_logger()
