"""
TUI接口 - 提供文本用户界面
"""
import sys
import logging
from typing import Dict, Any, List, Tuple

from ..config.constants import (
    CHECKBOX_OPTIONS, INPUT_OPTIONS, 
    PRESET_CONFIGS, TOOL_DESCRIPTION
)
from ..tasks.task_manager import TaskManager
from .cli import get_directories_from_args, get_options_from_args

logger = logging.getLogger(__name__)

def create_and_run_tui():
    """
    创建并运行TUI界面
    """
    try:
        # 导入TUI相关模块
        from nodes.tui.textual_preset import create_config_app
        
        # 创建配置界面
        app = create_config_app(
            program=__file__,
            checkbox_options=CHECKBOX_OPTIONS,
            input_options=INPUT_OPTIONS,
            title="文件整理压缩配置",
            preset_configs=PRESET_CONFIGS
        )
        
        # 运行界面
        app.run()
        
    except ImportError:
        logger.info("[#process]❌ 未找到TUI所需的模块，请使用命令行方式运行")
        print("未找到TUI所需的模块，请使用命令行方式运行")
        sys.exit(1)
    except Exception as e:
        logger.info(f"[#process]❌ 运行TUI界面时出错: {str(e)}")
        print(f"运行TUI界面时出错: {str(e)}")
        sys.exit(1)

def run_with_tui_config(config: Dict[str, Any]):
    """
    使用TUI配置运行任务
    
    Args:
        config: TUI生成的配置
    """
    # 转换配置为命令行参数格式
    class Args:
        pass
    
    args = Args()
    
    # 设置参数
    for option_name, option_arg, _, _ in CHECKBOX_OPTIONS:
        option_key = option_arg.lstrip('-')
        setattr(args, option_key.replace('-', '_'), option_key in config.get('checkbox_options', []))
    
    # 设置输入值
    for option_name, option_key, _, _, _ in INPUT_OPTIONS:
        setattr(args, option_key, config.get('input_values', {}).get(option_key, ''))
    
    # 获取目录和选项
    directories = get_directories_from_args(args)
    if not directories:
        logger.info("[#process]❌ 未输入有效路径，程序退出")
        return
    
    options = get_options_from_args(args)
    
    # 运行任务
    task_manager = TaskManager()
    task_manager.run_tasks(directories, options)