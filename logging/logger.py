"""
日志配置模块 - 处理日志配置和管理
"""
import os
import logging
from pathlib import Path
from typing import Dict, Any, Tuple
import sys

from ..config.config import LOG_CONFIG, TEXTUAL_LAYOUT

def setup_logger(
    config: Dict[str, Any] = None, 
    console_enabled: bool = None
) -> Tuple[logging.Logger, Dict[str, Any]]:
    """
    设置日志记录器
    
    Args:
        config: 日志配置字典
        console_enabled: 是否启用控制台输出，如果为None则使用config中的设置
        
    Returns:
        配置好的日志记录器和配置信息的元组
    """
    if config is None:
        config = LOG_CONFIG.copy()
    
    if console_enabled is not None:
        config['console_enabled'] = console_enabled
    
    # 获取脚本名称
    script_name = config.get('script_name', 'auto_repack')
    
    # 创建日志目录
    log_dir = Path(os.path.expanduser('~')) / '.logs' / script_name
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建日志文件路径
    log_file = log_dir / f"{script_name}.log"
    
    # 配置根日志记录器
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # 文件处理器
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)
    
    # 控制台处理器（可选）
    if config.get('console_enabled', True):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter('%(message)s')
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)
    
    # 将日志文件路径添加到配置中
    config_info = {'log_file': str(log_file), **config}
    
    return logger, config_info

def init_textual_logger():
    """
    初始化Textual日志面板
    
    Returns:
        配置好的日志管理器
    """
    try:
        from nodes.tui.textual_logger import TextualLoggerManager
        logger, config_info = setup_logger()
        TextualLoggerManager.set_layout(TEXTUAL_LAYOUT, config_info['log_file'])
        return logger
    except ImportError:
        print("警告: Textual日志模块不可用，使用标准日志")
        return setup_logger(console_enabled=True)[0] 