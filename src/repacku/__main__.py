"""
自动重新打包工具 - 简单版

负责处理命令行参数并调用相应的分析和压缩功能。
"""

import sys
import os
import argparse
import logging
from pathlib import Path
from typing import List, Optional, Union, Dict, Any
# 导入Rich库用于美化输出
from rich.console import Console
from rich.prompt import Confirm
from rich.panel import Panel
from rich.logging import RichHandler
# 将原来的textual_preset导入修改为rich_preset
# from textual_preset import create_config_app
from rich_preset import create_config_app
console = Console()

# 导入当前包内的模块
try:
    from repacku.core.folder_analyzer import analyze_folder as analyzer
except ImportError as e:
    console.print(f"[red]无法导入folder_analyzer模块: {str(e)}[/red]")
try:
    from repacku.core.zip_compressor import ZipCompressor as compressor
except ImportError as e:
    compressor = None
    console.print(f"[red]zip_compressor: {str(e)}[/red]")

# 导入剪贴板模块（如果可用）
try:
    import pyperclip
except ImportError:
    pyperclip = None
    console.print("[yellow]提示: 未安装pyperclip库，剪贴板功能将不可用[/yellow]")
    console.print("[yellow]请使用: pip install pyperclip[/yellow]")

# 配置常量
SEVEN_ZIP_PATH = "C:\\Program Files\\7-Zip\\7z.exe"  # 默认7z路径
from repacku.config.config import get_compression_level
USE_RICH = True

from loguru import logger
from datetime import datetime

def setup_logger(app_name="app", project_root=None):
    """配置 Loguru 日志系统
    
    Args:
        app_name: 应用名称，用于日志目录
        project_root: 项目根目录，默认为当前文件所在目录
        
    Returns:
        tuple: (logger, config_info)
            - logger: 配置好的 logger 实例
            - config_info: 包含日志配置信息的字典
    """
    # 获取项目根目录
    if project_root is None:
        project_root = Path(__file__).parent.parent.resolve()
    
    # 清除默认处理器
    logger.remove()
    
    # 添加控制台处理器（简洁版格式）
    logger.add(
        sys.stdout,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <blue>{elapsed}</blue> | <level>{level.icon} {level: <8}</level> | <cyan>{name}:{function}:{line}</cyan> - <level>{message}</level>"
    )
    
    # 使用 datetime 构建日志路径
    current_time = datetime.now()
    date_str = current_time.strftime("%Y-%m-%d")
    hour_str = current_time.strftime("%H")
    minute_str = current_time.strftime("%M%S")
    
    # 构建日志目录和文件路径
    log_dir = os.path.join(project_root, "logs", app_name, date_str, hour_str)
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{minute_str}.log")
    
    # 添加文件处理器
    logger.add(
        log_file,
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {elapsed} | {level.icon} {level: <8} | {name}:{function}:{line} - {message}",
        enqueue=True,     )
    
    # 创建配置信息字典
    config_info = {
        'log_file': log_file,
    }
    
    logger.info(f"日志系统已初始化，应用名称: {app_name}")
    return logger, config_info

logger, _ = setup_logger(app_name="auto_repack")

def find_7zip_path():
    """尝试找到7-Zip的安装路径"""
    common_paths = [
        "C:\\Program Files\\7-Zip\\7z.exe",
        "C:\\Program Files (x86)\\7-Zip\\7z.exe",
        "D:\\Program Files\\7-Zip\\7z.exe"
    ]
    
    # 检查环境变量
    import shutil
    path_7z = shutil.which("7z")
    if path_7z:
        return path_7z
    
    # 检查常见位置
    for path in common_paths:
        if os.path.exists(path):
            return path
    
    return SEVEN_ZIP_PATH

def create_arg_parser():
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(description='文件自动压缩工具')
    
    # 文件类型选项
    parser.add_argument('--types', '-t', type=str, 
                       help='指定要处理的文件类型，用逗号分隔。可用类型: text,image,video,audio,document,code,archive')
    
    # 压缩选项
    parser.add_argument('--delete-after', '-d', action='store_true', 
                       help='压缩成功后删除源文件')
    
    # 路径选项
    parser.add_argument('--clipboard', '-c', action='store_true', 
                       help='从剪贴板读取路径')
    parser.add_argument('--path', '-p', type=str, 
                       help='指定处理路径')
    
    # TUI选项
    parser.add_argument('--tui', action='store_true',
                       help='启用TUI图形配置界面')
    
    # 单层打包选项
    parser.add_argument('--single', '-s', action='store_true',
                       help='启用单层打包模式，将目录下每个子文件夹打包为单独的压缩包')
    
    # 画集模式
    parser.add_argument('--gallery', '-g', action='store_true',
                       help='画集模式：自动查找并处理输入目录下所有名为".画集"的文件夹')
    
    return parser

def get_path_from_clipboard():
    """从剪贴板获取路径，支持多行路径，返回第一个有效路径"""
    try:
        if pyperclip is None:
            console.print("[red]未安装pyperclip模块，请安装: pip install pyperclip[/red]")
            return ""
            
        clipboard_content = pyperclip.paste().strip()
        
        if not clipboard_content:
            console.print("[yellow]剪贴板内容为空[/yellow]")
            return ""
            
        # 处理多行路径，取第一个有效路径
        lines = clipboard_content.splitlines()
        valid_paths = []
        
        for line in lines:
            path = line.strip().strip('"').strip("'")
            if path and os.path.exists(path):
                valid_paths.append(path)
        
        if valid_paths:
            if len(valid_paths) > 1:
                console.print(f"[yellow]剪贴板包含多个路径，使用第一个有效路径: {valid_paths[0]}[/yellow]")
            return valid_paths[0]
        else:
            console.print("[yellow]剪贴板内容不包含有效路径[/yellow]")
            return ""
    except Exception as e:
        console.print(f"[red]从剪贴板获取路径时出错: {str(e)}[/red]")
        return ""

def get_file_types_from_args(args) -> List[str]:
    """从命令行参数获取文件类型"""
    if hasattr(args, 'types') and args.types:
        return args.types.split(',')
    
    # 默认处理所有类型
    return ['text', 'image','document']

def analyze_folder(folder_path: Union[str, Path], target_file_types: List[str] = None) -> Optional[str]:
    """分析文件夹并生成配置文件"""
    try:
        # 确保路径是Path对象
        folder_path = Path(folder_path) if isinstance(folder_path, str) else folder_path
        
        # 检查路径是否存在
        if not folder_path.exists() or not folder_path.is_dir():
            console.print(f"[red]错误: 路径不存在或不是文件夹: {folder_path}[/red]")
            return None
        
        # 显示分析信息
        console.print(f"[blue]正在分析文件夹: {folder_path}[/blue]")
        
        # 调用分析器
        config_path = analyzer(folder_path, target_file_types=target_file_types, display=True)
        
        return config_path
        
    except Exception as e:
        console.print(f"[red]分析文件夹时出错: {str(e)}[/red]")
        import traceback
        console.print(traceback.format_exc())
        return None

def compress_folder(config_path: Union[str, Path], delete_after: bool = False) -> bool:
    if compressor is None:
        console.print("[red]错误: 未能导入zip_compressor模块，无法进行压缩操作[/red]")
        return False
    """根据配置文件压缩文件夹"""
    try:
        # 确保路径是Path对象
        config_path = Path(config_path) if isinstance(config_path, str) else config_path
        
        # 检查配置文件是否存在
        if not config_path.exists():
            console.print(f"[red]错误: 配置文件不存在: {config_path}[/red]")
            return False
        
        # 显示压缩信息
        console.print(f"[blue]开始压缩文件夹...[/blue]")
        
        # 创建ZipCompressor类的实例
        zip_compressor = compressor()
        
        # 调用压缩器，直接使用"7z"，不再指定路径
        results = zip_compressor.compress_from_json(
            config_path=config_path, 
            delete_after_success=delete_after
        )
        
        # 统计成功和失败数量
        success_count = sum(1 for r in results if r.success)
        fail_count = len(results) - success_count
        
        # 显示结果
        if success_count > 0:
            console.print(f"[green]✓ 成功压缩 {success_count} 个文件夹[/green]")
        
        if fail_count > 0:
            console.print(f"[red]✗ {fail_count} 个压缩操作失败[/red]")
        
        return success_count > 0 and fail_count == 0
        
    except Exception as e:
        console.print(f"[red]压缩文件夹时出错: {str(e)}[/red]")
        import traceback
        console.print(traceback.format_exc())
        return False

def run_with_params(params: Dict[str, Any]) -> int:
    """使用TUI或命令行参数运行程序"""
    try:
        # 清屏，防止TUI界面残留
        
        # 从参数中提取值
        delete_after = params['options'].get('--delete-after', False)
        folder_path = params['inputs'].get('--path', '')
        types = params['inputs'].get('--types', '')
        use_clipboard = params['options'].get('--clipboard', False)
        single_mode = params['options'].get('--single', False)
        gallery_mode = params['options'].get('--gallery', False)
          # 获取处理路径
        if use_clipboard:
            logger.info("从剪贴板获取路径")
            folder_path = get_path_from_clipboard()
        
        # 如果路径为空，提示用户交互式输入
        if not folder_path:
            console.print("[yellow]提示: 未指定有效的处理路径[/yellow]")
            from rich.prompt import Prompt
            folder_path = Prompt.ask("[blue]请输入要处理的路径[/blue]")
            
            # 验证输入的路径是否有效
            if not folder_path or not os.path.exists(folder_path):
                console.print("[red]错误: 输入的路径不存在或无效[/red]")
                return 1
            
            logger.info(f"用户输入路径: {folder_path}")
        
        # 如果是单层打包模式或画集模式，使用SinglePacker
        if single_mode or gallery_mode:
            from repacku.core.single_packer import SinglePacker
            
            packer = SinglePacker()
            
            if gallery_mode:
                logger.info(f"画集模式: 扫描并处理目录 '{folder_path}' 下的所有.画集文件夹")
                console.print(f"[blue]画集模式: 扫描并处理目录 '{folder_path}' 下的所有.画集文件夹[/blue]")
                packer.process_gallery_folders(folder_path, delete_after=delete_after)
            else:
                logger.info(f"单层打包模式: 处理目录 '{folder_path}' 下的子文件夹")
                console.print(f"[blue]单层打包模式: 处理目录 '{folder_path}' 下的子文件夹[/blue]")
                packer.pack_directory(folder_path, delete_after=delete_after)
            
            logger.info("处理完成")
            console.print("[green]✓ 处理完成！[/green]")
            return 0
            
        # 标准模式 - 获取文件类型
        target_file_types = types.split(',') if types else ['text', 'image', 'document']
        logger.info(f"目标文件类型: {target_file_types}")
        
        # 分析文件夹
        logger.info(f"开始分析文件夹: {folder_path}")
        config_path = analyze_folder(folder_path, target_file_types)
        
        if not config_path:
            logger.error("文件夹分析失败")
            return 1
          # 询问用户是否继续压缩
        if Confirm.ask("[yellow]是否继续进行压缩操作?[/yellow]", default=True):            # 压缩文件夹
            logger.info(f"开始压缩文件夹，配置文件: {config_path}")
            success = compress_folder(config_path, delete_after=delete_after)
            
            if success:
                logger.info("压缩操作成功完成")
                console.print("[green]✓ 压缩操作成功完成！[/green]")
                return 0
            else:
                logger.error("压缩操作失败")
                console.print("[red]✗ 压缩操作失败[/red]")
                return 1
        else:
            logger.info("用户取消了压缩操作")
            console.print("[yellow]已取消压缩操作[/yellow]")
            return 0
            
    except KeyboardInterrupt:
        console.print("\n[yellow]程序被用户中断[/yellow]")
        return 0  # 标准的 SIGINT 退出码
    except Exception as e:
        console.print(f"[red]程序运行时出错: {str(e)}[/red]")
        import traceback
        console.print(traceback.format_exc())
        return 1

def launch_tui_mode(parser: argparse.ArgumentParser) -> int:
    """启动基于rich的配置界面"""
    try:
        # 注册一些默认值以提高用户体验
        preset_configs = {
            "图片处理": {
                "description": "仅处理图片文件(从剪贴板读取路径)",
                "checkbox_options": ["delete_after","clipboard"],
                "input_values": {
                    "path": "",
                    "types": "image"
                }
            },
            "画集处理": {
                "description": "扫描并处理目录下所有.画集文件夹",
                "checkbox_options": ["delete_after", "clipboard", "gallery", "single"],
                "input_values": {
                    "path": "",
                    "types": ""
                }
            },
        }
        
        # 使用rich_preset版本的create_config_app
        # rich版本直接返回参数，不需要使用app.run()
        result = create_config_app(
            program=sys.argv[0],
            title="自动重新打包工具",
            parser=parser,  # 使用命令行解析器自动生成选项
            rich_mode=USE_RICH,
            preset_configs=preset_configs,  # 添加预设配置
        )        # 如果结果不为空，处理参数
        if USE_RICH:
            return run_with_params(result)
        else:
            result.run()
            return 0  # 默认返回成功
    except KeyboardInterrupt:
        console.print("\n[yellow]程序被用户中断[/yellow]")
        return 0  # 标准的 SIGINT 退出码
    except Exception as e:
        console.print(f"[red]启动配置界面时出错: {str(e)}[/red]")
        import traceback
        console.print(traceback.format_exc())
        return 1
    
def main():
    """主函数"""
    try:
        # 创建命令行参数解析器
        parser = create_arg_parser()
        
        # 先检查是否明确请求TUI模式
        # 如果命令行参数为空，也默认启动TUI
        if len(sys.argv) == 1 or '--tui' in sys.argv or '-t' in sys.argv:
            return launch_tui_mode(parser)
        
        
        # 解析命令行参数
        args = parser.parse_args()
        
        # 命令行模式 - 构建参数字典
        params = {
            'options': {
                '--delete-after': args.delete_after,
                '--clipboard': args.clipboard,
                '--single': args.single,
                '--gallery': args.gallery
            },
            'inputs': {
                '--path': args.path or '',
                '--types': args.types or ''
            }
        }
          # 使用统一的处理函数
        return run_with_params(params)
        
    except KeyboardInterrupt:
        console.print("\n[yellow]程序被用户中断[/yellow]")
        return 0  # 标准的 SIGINT 退出码
    except Exception as e:
        console.print(f"[red]程序运行时出错: {str(e)}[/red]")
        import traceback
        console.print(traceback.format_exc())
        return 1
    
if __name__ == "__main__":
    sys.exit(main())