"""
命令行接口 - 处理命令行参数和交互
"""
import argparse
import pyperclip
from pathlib import Path
from typing import List, Dict, Optional

from ..config.constants import DEFAULT_OPTIONS
from ..logging.logger import init_textual_logger

logger = init_textual_logger()

def parse_arguments():
    """
    解析命令行参数
    
    Returns:
        解析后的参数对象
    """
    parser = argparse.ArgumentParser(description='文件处理和压缩工具')
    parser.add_argument('--clipboard', '-c', action='store_true', help='从剪贴板读取路径')
    parser.add_argument('--organize-media', '-om', action='store_true', help='整理媒体文件')
    parser.add_argument('--move-unwanted', '-mu', action='store_true', help='移动不需要的文件')
    parser.add_argument('--compress', '-cm', action='store_true', help='压缩文件夹')
    parser.add_argument('--process-scattered', '-ps', action='store_true', help='处理散图')
    parser.add_argument('--images-only', '-io', action='store_true', help='只压缩图片文件(保留文件夹和其他文件)')
    parser.add_argument('--all', '-a', action='store_true', help='执行所有操作')
    parser.add_argument('--path', '-p', type=str, help='指定处理路径')
    
    return parser.parse_args()

def get_directories_from_args(args) -> List[Path]:
    """
    从命令行参数获取要处理的目录
    
    Args:
        args: 解析后的命令行参数
        
    Returns:
        要处理的目录路径列表
    """
    directories = []
    
    if args.clipboard:
        input_text = pyperclip.paste()
        logger.info("[#process]从剪贴板读取的路径:")
        logger.info(input_text)
        
        for path in input_text.strip().split('\n'):
            try:
                clean_path = path.strip().strip('"').strip("'").strip()
                # 使用 Path 对象的绝对路径来处理特殊字符
                path_obj = Path(clean_path).resolve()
                if path_obj.exists():
                    directories.append(path_obj)
                    logger.info(f"[#process]✅ 已添加路径: {path_obj}")
                else:
                    logger.info(f"[#process]⚠️ 路径不存在: {clean_path}")
            except Exception as e:
                logger.info(f"[#process]❌ 处理路径时出错: {clean_path} - {str(e)}")
    else:
        if args.path:
            try:
                path_obj = Path(args.path).resolve()
                if path_obj.exists():
                    directories.append(path_obj)
                    logger.info(f"[#process]✅ 使用指定路径: {path_obj}")
                else:
                    logger.info(f"[#process]❌ 路径不存在: {args.path}")
                    return []
            except Exception as e:
                logger.info(f"[#process]❌ 处理路径时出错: {args.path} - {str(e)}")
                return []
    
    return directories

def get_options_from_args(args) -> Dict[str, bool]:
    """
    从命令行参数获取选项
    
    Args:
        args: 解析后的命令行参数
        
    Returns:
        选项字典
    """
    # 创建选项字典
    options = {
        "organize_media": args.all or args.organize_media,
        "move_unwanted": args.all or args.move_unwanted,
        "compress": args.all or args.compress,
        "process_scattered": args.all or args.process_scattered,
        "images_only": args.images_only  # 添加images_only选项
    }
    
    # 如果没有指定任何选项，默认执行所有操作
    if not any(options.values()):
        options = DEFAULT_OPTIONS
    
    return options 