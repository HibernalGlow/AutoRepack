"""
压缩处理器模块 - 简化版

封装核心压缩操作，包括从JSON配置文件读取、两种压缩模式实现
"""

import os
import shutil
import subprocess
import logging
import json
import re
import time
from pathlib import Path
from typing import List, Dict, Union, Any, Optional, Tuple
from datetime import datetime

# 导入Rich库
from repacku.config.config import get_compression_level
from rich.console import Console
from rich.tree import Tree
from rich.panel import Panel
from rich.logging import RichHandler
from rich.text import Text
from rich.progress import Progress, TextColumn, BarColumn, TaskID, SpinnerColumn
from rich.progress import TimeElapsedColumn, TimeRemainingColumn, FileSizeColumn, ProgressColumn
from rich.live import Live
from repacku.core.folder_analyzer import FolderInfo

# 导入folder_analyzer模块中的显示函数
from repacku.core.folder_analyzer import display_folder_structure

# 设置Rich日志记录器
console = Console()

# 压缩模式常量
COMPRESSION_LEVEL = 7
# 压缩模式常量
COMPRESS_MODE_ENTIRE = "entire"      # 整体压缩
COMPRESS_MODE_SELECTIVE = "selective" # 选择性压缩
COMPRESS_MODE_SKIP = "skip"          # 跳过压缩

# 进度模式常量
PROGRESS_MODE_FILES = "files"        # 按文件数量统计进度
PROGRESS_MODE_SIZE = "size"          # 按文件大小统计进度

class PercentageColumn(ProgressColumn):
    """自定义进度列，显示百分比"""
    def render(self, task):
        if task.total == 0:
            return Text("0%")
        return Text(f"{task.completed / task.total:.0%}")


class CompressionResult:
    """压缩结果类"""
    def __init__(self, success: bool, original_size: int = 0, compressed_size: int = 0, error_message: str = ""):
        self.success = success
        self.original_size = original_size
        self.compressed_size = compressed_size
        self.error_message = error_message

class ZipCompressor:
    """压缩处理类，封装核心压缩操作"""
    def __init__(self, compression_level: int = None, threads: int = 16):
        """
        初始化压缩处理器
        
        Args:
            compression_level: 压缩级别 (0-9)
            threads: 压缩线程数，默认16
        """
        if compression_level is None:
            self.compression_level = get_compression_level()
        else:
            self.compression_level = compression_level
        self.threads = threads
        # 不再需要检查文件是否存在，因为我们使用的是系统命令
    
    def compress_files(self, source_path: Path, target_zip: Path, file_extensions: List[str] = None, delete_source: bool = False) -> CompressionResult:
        """压缩文件到目标路径，使用通配符匹配特定扩展名的文件
        
        Args:
            source_path: 源文件夹路径
            target_zip: 目标压缩包路径
            file_extensions: 要压缩的文件扩展名列表，例如['.jpg', '.png']
            delete_source: 是否删除源文件
            
        Returns:
            CompressionResult: 压缩结果
        """
        logging.info(f"[#process]🔄 开始选择性压缩文件: {source_path}")
        
        # 确保source_path和target_zip是Path对象
        if isinstance(source_path, str):
            source_path = Path(source_path)
        if isinstance(target_zip, str):
            target_zip = Path(target_zip)
        
        # 获取文件夹名称和父目录
        folder_name = source_path.name
        parent_dir = source_path.parent
        
        # 确保目录存在
        if not source_path.exists() or not source_path.is_dir():
            error_msg = f"源文件夹不存在或不是目录: {source_path}"
            logging.error(f"[#process]❌ {error_msg}")
            return CompressionResult(False, error_message=error_msg)
            
        # 将路径转换为字符串，避免UNC路径问题
        source_path_str = str(source_path)
        target_zip_str = str(target_zip)
        
        # 统计匹配的文件
        total_files = 0
        total_size = 0
        matched_extensions = set()
        
        # 统计文件夹中的文件类型分布
        for file_path in source_path.glob('*'):  # 这里从rglob改为glob，不递归查找子文件夹
            if file_path.is_file():
                ext = file_path.suffix.lower()
                # 如果没有指定扩展名列表，或者文件扩展名在列表中
                if not file_extensions or ext in file_extensions:
                    matched_extensions.add(ext)
                    total_files += 1
                    total_size += file_path.stat().st_size
        
        # 如果没有匹配的文件，返回错误
        if total_files == 0:
            error_msg = "没有找到匹配的文件，不执行压缩"
            logging.warning(f"[#process]⚠️ {error_msg}")
            return CompressionResult(False, error_message=error_msg)
        
        # 生成通配符参数
        wildcard_patterns = []
        
        # 如果有匹配的扩展名
        if matched_extensions:
            for ext in matched_extensions:
                if ext and ext.startswith('.'):
                    # 使用"*.ext"格式，移除.前缀
                    wildcard_patterns.append(f"\"*.{ext[1:]}\"")
            
            # 显示匹配的文件类型
            console.print(f"[cyan]📁 匹配的文件类型:[/]")
            for ext in sorted(matched_extensions):
                console.print(f"  • [green]{ext}[/]")
                
            wildcard_str = " ".join(wildcard_patterns)
            logging.info(f"[#process]📦 使用通配符匹配文件: {wildcard_str}")
        else:
            # 如果没有匹配文件但total_files > 0，可能是文件没有扩展名
            wildcard_str = "\"*\""
            logging.info(f"[#process]📦 没有指定文件类型，使用通配符 {wildcard_str}")
        
        # 构建压缩命令
        # 切换到源文件夹，使用绝对路径指定目标zip文件
        cmd = f'cd /d "{source_path_str}" && "7z" a -tzip "{target_zip_str}" {wildcard_str} -aou -mx={self.compression_level} -mmt={self.threads}'
        
        # 如果需要删除源文件，添加-sdel参数
        if delete_source:
            cmd += " -sdel"
        
        # 执行压缩
        logging.info(f"[#process]🔄 执行压缩: {folder_name}")
        
        process = subprocess.Popen(
            cmd, 
            shell=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True
        )
        
        stdout, stderr = process.communicate()
        result_code = process.returncode
        
        # 如果删除了源文件，删除空文件夹
        if delete_source and result_code == 0:
            self._remove_empty_dirs(source_path)
        
        # 处理结果
        if result_code == 0:
            original_size = total_size
            compressed_size = target_zip.stat().st_size if target_zip.exists() else 0
            return CompressionResult(True, original_size, compressed_size)
        else:
            return CompressionResult(False, error_message=stderr)

    def compress_entire_folder(self, folder_path: Path, target_zip: Path, delete_source: bool = False, keep_folder_structure: bool = True) -> CompressionResult:
        """压缩整个文件夹
        
        Args:
            folder_path: 源文件夹路径
            target_zip: 目标压缩包路径
            delete_source: 是否删除源文件
            keep_folder_structure: 是否保留最外层文件夹结构
        """
        logging.info(f"[#process]🔄 开始压缩整个文件夹: {folder_path}")
        
        # 确保folder_path是Path对象
        if isinstance(folder_path, str):
            folder_path = Path(folder_path)
        
        # 获取文件夹名称和父目录
        folder_name = folder_path.name
        parent_dir = folder_path.parent
        
        # 如果未提供target_zip或target_zip为默认值，则重新构造一个完整的目标名称
        if target_zip == folder_path.with_suffix(".zip"):
            # 使用文件夹完整名称作为压缩包名
            target_zip = parent_dir / f"{folder_name}.zip"
        
        # 确保压缩包路径在父目录或源文件夹内部，保持target_zip的位置不变
        # 只有当路径既不在父目录又不在文件夹内时才调整
        if target_zip.parent != folder_path and target_zip.parent != parent_dir:
            logging.info(f"[#process]⚠️ 调整目标路径到父目录")
            target_zip = parent_dir / f"{folder_name}.zip"
        
        # 记录实际使用的压缩包位置
        if target_zip.parent == parent_dir:
            logging.info(f"[#process]📁 压缩包位置: 父目录")
        else:
            logging.info(f"[#process]📁 压缩包位置: 文件夹内部")
        
        # 计算要处理的文件总数和总大小
        total_files = 0
        total_size = 0
        
        # 统计文件夹中的所有文件
        for file_path in folder_path.rglob('*'):
            if file_path.is_file():
                total_files += 1
                total_size += file_path.stat().st_size
        
        # 使用完整路径进行压缩
        target_zip_str = str(target_zip)
        folder_path_str = str(folder_path)
        parent_dir_str = str(parent_dir)
        
        # 根据keep_folder_structure参数构建不同的命令
        if keep_folder_structure:
            cmd = f'cd /d "{parent_dir_str}" && "7z" a -tzip "{target_zip_str}" "{folder_name}\\" -r -mx={self.compression_level} -mmt={self.threads} -aou'
        else:
            cmd = f'cd /d "{folder_path_str}" && "7z" a -tzip "{target_zip_str}" * -r -mx={self.compression_level} -mmt={self.threads} -aou'
        
        # 如果需要删除源文件，添加-sdel参数
        if delete_source:
            cmd += " -sdel"
        
        logging.info(f"[#process]�  执行压缩: {folder_name}")
        
        # 执行压缩
        process = subprocess.Popen(
            cmd, 
            shell=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True
        )
        
        stdout, stderr = process.communicate()
        result_code = process.returncode
        
        # 如果压缩成功且需要删除源文件夹但未使用-sdel
        if delete_source and result_code == 0 and not "-sdel" in cmd:
            try:
                # 删除整个文件夹
                shutil.rmtree(folder_path)
                logging.info(f"[#file_ops]🗑️ 已删除源文件夹: {folder_path}")
            except Exception as e:
                logging.info(f"[#file_ops]⚠️ 删除源文件夹失败: {e}")
        
        # 处理结果
        if result_code == 0:
            original_size = total_size
            compressed_size = target_zip.stat().st_size if target_zip.exists() else 0
            return CompressionResult(True, original_size, compressed_size)
        else:
            return CompressionResult(False, error_message=stderr)
    
    def _remove_empty_dirs(self, path: Path) -> None:
        """递归删除空文件夹"""
        if not path.is_dir():
            return
            
        # 检查目录是否为空
        has_content = False
        for item in path.iterdir():
            if item.is_file():
                has_content = True
                break
            if item.is_dir():
                self._remove_empty_dirs(item)  # 递归处理子目录
                # 检查子目录在处理后是否仍然存在
                if item.exists():
                    has_content = True
        
        # 如果目录为空，删除它
        if not has_content and path.exists():
            try:
                path.rmdir()
                logging.info(f"[#file_ops]🗑️ 已删除空文件夹: {path}")
            except Exception as e:
                logging.info(f"[#file_ops]⚠️ 删除空文件夹失败: {e}")
    
    def compress_from_json(self, config_path: Path, delete_after_success: bool = False) -> List[CompressionResult]:
        """
        根据JSON配置文件进行压缩
        
        Args:
            config_path: 配置文件路径
            delete_after_success: 是否删除源文件
            
        Returns:
            List[CompressionResult]: 压缩结果列表
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            # 显示文件夹树结构 - 使用folder_analyzer模块中的函数
            logging.info("📂 文件夹分析结果:")
            
            # 导入folder_analyzer中的FolderInfo来构建树状结构
            from repacku.core.folder_analyzer import FolderInfo
            
            # 从配置转换为FolderInfo结构
            def config_to_folder_info(config_data):
                if "folder_tree" in config_data:
                    folder_data = config_data["folder_tree"]
                else:
                    folder_data = config_data
                
                # 创建根文件夹信息
                root_info = FolderInfo(
                    path=folder_data.get("path", ""),
                    name=folder_data.get("name", "未知文件夹"),
                    depth=0
                )
                root_info.compress_mode = folder_data.get("compress_mode", "skip")
                root_info.total_files = folder_data.get("total_files", 0)
                root_info.file_types = folder_data.get("file_types", {})
                root_info.file_extensions = folder_data.get("file_extensions", {})  # 获取文件扩展名统计
                root_info.size_mb = folder_data.get("size_mb", 0)
                root_info.recommendation = folder_data.get("recommendation", "")
                
                # 递归处理子文件夹
                if "children" in folder_data and folder_data["children"]:
                    for child_data in folder_data["children"]:
                        child_info = _create_folder_info(child_data, root_info.path, root_info.depth + 1)
                        if child_info:
                            root_info.children.append(child_info)
                
                return root_info
            
            # 创建单个文件夹信息
            def _create_folder_info(folder_data, parent_path, depth):
                folder_info = FolderInfo(
                    path=folder_data.get("path", ""),
                    name=folder_data.get("name", "未知文件夹"),
                    parent_path=parent_path,
                    depth=depth
                )
                folder_info.compress_mode = folder_data.get("compress_mode", "skip")
                folder_info.total_files = folder_data.get("total_files", 0)
                folder_info.file_types = folder_data.get("file_types", {})
                folder_info.file_extensions = folder_data.get("file_extensions", {})  # 获取文件扩展名统计
                folder_info.size_mb = folder_data.get("size_mb", 0)
                folder_info.recommendation = folder_data.get("recommendation", "")
                
                # 递归处理子文件夹
                if "children" in folder_data and folder_data["children"]:
                    for child_data in folder_data["children"]:
                        child_info = _create_folder_info(child_data, folder_info.path, depth + 1)
                        if child_info:
                            folder_info.children.append(child_info)
                
                return folder_info
            
            # 将配置转换为FolderInfo结构并显示
            root_info = config_to_folder_info(config)
            display_folder_structure(root_info)
            
            # 在控制台显示压缩配置文件
            console.print(f"[bold cyan]📄 使用配置文件:[/] {config_path.name}")
                
        except Exception as e:
            return [CompressionResult(False, error_message=f"读取配置文件失败: {str(e)}")]
        
        # 获取配置信息 - 根据test_config.json的结构进行调整
        folder_tree = config.get("folder_tree", {})
        root_path = folder_tree.get("path", "")
        target_file_types = config.get("config", {}).get("target_file_types", [])
        
        # 收集要处理的所有文件夹
        folders_to_process = []
        
        # 递归收集文件夹信息
        def collect_folders(folder_data):
            if not folder_data:
                return
                
            # 添加当前文件夹
            folders_to_process.append(folder_data)
            
            # 递归处理子文件夹
            for child in folder_data.get("children", []):
                collect_folders(child)
        
        # 从根节点开始收集
        collect_folders(folder_tree)
        
        # 过滤出需要处理的文件夹
        folders_to_compress = [
            f for f in folders_to_process 
            if f.get("compress_mode") in [COMPRESS_MODE_ENTIRE, COMPRESS_MODE_SELECTIVE]
        ]
        total_folders = len(folders_to_compress)
        
        if total_folders == 0:
            console.print("[yellow]没有需要压缩的文件夹[/yellow]")
            return []
        
        results = []
        
        # 创建全局进度条
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=40),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("•"),
            TimeElapsedColumn(),
            TextColumn("•"),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            task = progress.add_task(f"[cyan]压缩进度: 0/{total_folders}", total=total_folders)
            
            for idx, folder_info in enumerate(folders_to_compress):
                folder_path = Path(folder_info.get("path", ""))
                compress_mode = folder_info.get("compress_mode", COMPRESS_MODE_SKIP)
                folder_name = folder_info.get("name", folder_path.name)
                
                # 更新进度描述
                progress.update(task, description=f"[cyan]压缩: {folder_name[:30]}...")
                
                if compress_mode == COMPRESS_MODE_ENTIRE:
                    keep_structure = folder_info.get("keep_folder_structure", True)
                    result = self.compress_entire_folder(
                        folder_path, 
                        folder_path.with_suffix(".zip"), 
                        delete_after_success,
                        keep_structure
                    )
                elif compress_mode == COMPRESS_MODE_SELECTIVE:
                    file_extensions = folder_info.get("file_extensions", {})
                    
                    if file_extensions:
                        extensions_list = list(file_extensions.keys())
                    else:
                        file_types = folder_info.get("file_types", {})
                        target_types = list(file_types.keys()) or target_file_types
                        extensions_list = []
                        for file_type in target_types:
                            if file_type == "image":
                                extensions_list.extend(['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'])
                            elif file_type == "video":
                                extensions_list.extend(['.mp4', '.avi', '.mov', '.wmv', '.mkv', '.flv'])
                            elif file_type == "document":
                                extensions_list.extend(['.pdf', '.doc', '.docx', '.txt', '.md'])
                    
                    archive_path = folder_path / f"{folder_path.name}.zip"
                    result = self.compress_files(
                        folder_path, 
                        archive_path,
                        extensions_list,
                        delete_after_success
                    )
                else:
                    continue
                
                results.append(result)
                
                # 显示单个文件夹压缩结果
                if result.success:
                    ratio = (1 - result.compressed_size / result.original_size) * 100 if result.original_size > 0 else 0
                    progress.console.print(
                        f"  [green]✓[/green] {folder_name} | "
                        f"{result.original_size/1024/1024:.1f}MB → {result.compressed_size/1024/1024:.1f}MB "
                        f"([cyan]{ratio:.0f}%[/cyan])"
                    )
                else:
                    progress.console.print(f"  [red]✗[/red] {folder_name} | {result.error_message[:50]}")
                
                # 更新进度
                progress.update(task, completed=idx + 1, 
                              description=f"[cyan]压缩进度: {idx + 1}/{total_folders}")
        
        # 显示结果摘要
        success_count = sum(1 for r in results if r.success)
        fail_count = len(results) - success_count
        total_original = sum(r.original_size for r in results if r.success)
        total_compressed = sum(r.compressed_size for r in results if r.success)
        total_ratio = (1 - total_compressed / total_original) * 100 if total_original > 0 else 0
        
        console.print(f"\n[green]✓ 完成[/green] {success_count}/{len(results)} | "
                     f"总计 {total_original/1024/1024:.1f}MB → {total_compressed/1024/1024:.1f}MB "
                     f"([cyan]{total_ratio:.0f}%[/cyan])")
        
        return results
    
    def visualize_compression_results(self, results: List[CompressionResult]) -> None:
        """可视化压缩结果"""
        if not results:
            logging.info("没有压缩结果可显示")
            return
            
        console.print(Panel("[bold]压缩结果摘要[/]", style="blue"))
        
        total_original = sum(r.original_size for r in results if r.success)
        total_compressed = sum(r.compressed_size for r in results if r.success)
        success_count = sum(1 for r in results if r.success)
        fail_count = len(results) - success_count
        
        if total_original > 0:
            ratio = (1 - total_compressed / total_original) * 100
            console.print(f"总压缩率: [green]{ratio:.1f}%[/]")
        
        console.print(f"成功: [green]{success_count}[/], 失败: [red]{fail_count}[/]")
        
        if fail_count > 0:
            console.print("[yellow]失败列表:[/]")
            for i, result in enumerate(results):
                if not result.success:
                    console.print(f"  [red]{i+1}. {result.error_message}[/]")

def get_folder_size(folder_path: Path) -> int:
    """计算文件夹大小"""
    return sum(f.stat().st_size for f in folder_path.rglob('*') if f.is_file())