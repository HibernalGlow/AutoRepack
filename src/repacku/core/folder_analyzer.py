#!/usr/bin/env python
"""
文件夹分析器 - 独立版本

分析文件夹结构，识别文件类型分布，并生成压缩配置JSON
"""

import os
import sys
import json
import logging
import argparse
import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Optional, Union
from dataclasses import dataclass, field, asdict
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

# 导入Rich库
from rich.console import Console
from rich.tree import Tree
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.logging import RichHandler


# 从通用工具模块导入共用功能
from repacku.core.common_utils import (
    DEFAULT_FILE_TYPES, COMPRESS_MODE_ENTIRE, COMPRESS_MODE_SELECTIVE, COMPRESS_MODE_SKIP,
    FileTypeManager, get_file_type, is_file_in_types, is_blacklisted_path, get_folder_size,try_extended_media_match
)

# 导入配置函数
from repacku.config.config import get_single_image_compress_rule


# 设置Rich日志记录
console = Console()

@dataclass
class FolderInfo:
    """单个文件夹的信息，用于树状结构输出"""
    path: str
    name: str
    parent_path: str = ""  # 父文件夹路径
    depth: int = 0  # 文件夹深度
    weight: float = 0.0
    total_files: int = 0
    total_size: int = 0
    size_mb: float = 0.0
    compress_mode: str = None  # 初始为None，让分析器来决定
    recommendation: str = ""
    file_types: Dict[str, int] = field(default_factory=dict)
    file_extensions: Dict[str, int] = field(default_factory=dict)
    dominant_types: List[str] = field(default_factory=list)  # 修正为list
    children: List["FolderInfo"] = field(default_factory=list)  # 子文件夹列表，用于树状结构
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，便于JSON序列化"""
        result = asdict(self)
        # 确保不重复输出相似信息
        # 如果file_types为空，用file_extensions生成file_types
        if not result["file_types"] and result["file_extensions"]:
            # 将扩展名映射到类型
            mapped_types = {}
            for ext, count in result["file_extensions"].items():
                file_type = None
                for type_name, extensions in DEFAULT_FILE_TYPES.items():
                    if ext in extensions:
                        file_type = type_name
                        break
                
                if file_type:
                    if file_type not in mapped_types:
                        mapped_types[file_type] = 0
                    mapped_types[file_type] += count
            
            if mapped_types:
                result["file_types"] = mapped_types
        return result
    
    def to_tree_dict(self) -> Dict[str, Any]:
        """转换为树结构的字典表示"""
        result = self.to_dict()
        # 替换children字段为实际的子文件夹字典
        if self.children:
            result["children"] = [child.to_tree_dict() for child in self.children]
        else:
            # 如果没有子文件夹，可以省略children字段
            result.pop("children", None)
        
        # 移除一些在树结构中不需要的字段
        result.pop("parent_path", None)  # 树结构中通过嵌套表示父子关系，不需要parent_path
        
        return result

def get_mime_category(file_path: Path) -> Optional[str]:
    """根据文件的MIME类型判断其所属类别"""
    # 直接使用通用工具模块中的get_file_type函数
    return get_file_type(file_path)


class FolderAnalyzer:
    """文件夹分析器类，分析文件夹结构并生成配置"""
    
    def __init__(self, custom_logging=None):
        """
        初始化文件夹分析器
        
        Args:
            custom_logging: 可选的自定义日志记录器，如果提供则使用该记录器
        """
        self.COMPRESS_MODE_ENTIRE = COMPRESS_MODE_ENTIRE
        self.COMPRESS_MODE_SELECTIVE = COMPRESS_MODE_SELECTIVE
        self.COMPRESS_MODE_SKIP = COMPRESS_MODE_SKIP
    
    def calculate_folder_weight(self, folder_path: Path) -> float:
        """
        计算文件夹的权重
        
        Args:
            folder_path: 文件夹路径
            
        Returns:
            float: 文件夹权重值
        """
        try:
            # 计算层级深度（路径中的目录分隔符数量）
            depth = len(str(folder_path).split(os.sep))
            
            # 获取文件夹大小，将大小作为次要因素
            size_weight = get_folder_size(folder_path) / (1024 * 1024 * 1024)  # 转化为GB
            
            # 综合权重 = 深度 + 大小权重*0.1，深度占主要部分
            weight = depth + size_weight * 0.1
            
            return weight
        except Exception as e:
            logging.error(f"计算文件夹权重时出错: {folder_path}, {str(e)}")
            return float('inf')  # 返回无穷大
    
    def _get_dominant_types(self, file_types: Dict[str, int], top_n: int = 3) -> List[str]:
        """获取主要文件类型"""
        if not file_types:
            return []
        
        # 按数量排序并取前N个
        sorted_types = sorted(file_types.items(), key=lambda x: x[1], reverse=True)
        return [t[0] for t in sorted_types[:top_n]]
    
    def _determine_compress_mode(self, folder_path: Path, 
                               files: List[Path], 
                               file_types_count: Counter,
                               target_file_types: List[str] = None,
                               has_child_with_archive: bool = False,
                               min_count: int = 2) -> Tuple[str, Dict[str, int]]:
        """
        根据文件类型分布确定压缩模式，同时返回符合条件的文件扩展名统计
        
        Args:
            folder_path: 文件夹路径
            files: 文件列表
            file_types_count: 文件类型计数
            target_file_types: 目标文件类型列表
            has_child_with_archive: 子文件夹中是否有压缩包
            min_count: 最小匹配文件数量，低于此数值则不进行压缩
        
        Returns:
            Tuple[str, Dict[str, int]]: (压缩模式, 文件扩展名统计)
        """
        # 初始化符合条件的文件扩展名统计
        file_ext_count = Counter()
        
        # 如果没有文件，跳过处理
        if not files:
            return self.COMPRESS_MODE_SKIP, dict(file_ext_count)
        
        # 特殊规则：检查是否为单个图片且没有子文件夹的情况
        if get_single_image_compress_rule():
            # 检查是否有子文件夹
            subfolders = [item for item in folder_path.glob('*') if item.is_dir()]
            has_subfolders = len(subfolders) > 0
            
            # 检查是否只有一个文件且为图片
            if len(files) == 1 and not has_subfolders:
                file_type_manager = FileTypeManager()
                single_file = files[0]
                
                if file_type_manager.is_file_in_types(single_file, ["image"]):
                    # 记录图片文件扩展名
                    ext = single_file.suffix.lower()
                    if ext:
                        file_ext_count[ext] += 1
                    return self.COMPRESS_MODE_ENTIRE, dict(file_ext_count)
            
        # 如果文件夹在黑名单中，跳过处理
        if is_blacklisted_path(folder_path):
            return self.COMPRESS_MODE_SKIP, dict(file_ext_count)
            
        # 检查当前文件夹中是否有压缩包 - 只有当archive计数大于0时才认为有压缩包
        has_archive = file_types_count.get("archive", 0) > 0
            
        # 如果当前文件夹或子文件夹中有压缩包，使用selective模式而不是entire模式
        if has_archive or has_child_with_archive:
            # 如果没有指定目标类型，跳过处理（不压缩）
            if not target_file_types:
                return self.COMPRESS_MODE_SKIP, dict(file_ext_count)
                
            # 检查是否有匹配目标类型的文件
            file_type_manager = FileTypeManager()
            # 检查当前文件夹中的文件
            matching_files = [f for f in files if file_type_manager.is_file_in_types(f, target_file_types)]
            
            # 如果有匹配的文件，统计它们的扩展名
            if matching_files and len(matching_files) >= min_count:
                for file in matching_files:
                    ext = file.suffix.lower()
                    if ext:  # 只记录非空扩展名
                        file_ext_count[ext] += 1
                
                # 返回selective模式和扩展名统计
                return self.COMPRESS_MODE_SELECTIVE, dict(file_ext_count)
                
            # 没有匹配的文件或匹配文件数量不满足最小要求，跳过处理
            return self.COMPRESS_MODE_SKIP, dict(file_ext_count)
        
        # 如果没有指定目标类型，但文件数量满足最小要求，整体压缩，记录所有文件扩展名
        if not target_file_types:
            if len(files) >= min_count:
                for file in files:
                    ext = file.suffix.lower()
                    if ext:  # 只记录非空扩展名
                        file_ext_count[ext] += 1
                return self.COMPRESS_MODE_ENTIRE, dict(file_ext_count)
            else:
                return self.COMPRESS_MODE_SKIP, dict(file_ext_count)
            
        # 开始处理基于目标类型的判断
        file_type_manager = FileTypeManager()
        total_files = len(files)
        
        # 计算匹配目标类型的文件数量
        matching_files = []
        for file in files:
            if file_type_manager.is_file_in_types(file, target_file_types):
                matching_files.append(file)
                # 统计匹配文件的扩展名
                ext = file.suffix.lower()
                if ext:  # 只记录非空扩展名
                    file_ext_count[ext] += 1
        
        matching_count = len(matching_files)
        
        # 如果匹配文件数量不满足最小要求，跳过处理
        if matching_count < min_count:
            return self.COMPRESS_MODE_SKIP, dict(file_ext_count)
            
        # 如果所有文件都匹配目标类型，整体压缩
        if matching_count == total_files and matching_count > 0:
            return self.COMPRESS_MODE_ENTIRE, dict(file_ext_count)
            
        # 特殊处理：如果目标类型包含'image'，且图片类型无法匹配全部文件，
        # 则尝试使用扩展媒体类型(图片+文档+文本)进行匹配
        if "image" in target_file_types and matching_count < total_files:
            # 使用自定义函数检查是否所有文件都符合扩展媒体类型
            if try_extended_media_match(files, file_type_manager):
                # 如果所有文件都是图片/文档/文本类型，重新计算所有文件的扩展名统计
                file_ext_count = Counter()
                for file in files:
                    ext = file.suffix.lower()
                    if ext:  # 只记录非空扩展名
                        file_ext_count[ext] += 1
                        
                logging.info(f"[#process]📊 文件夹包含图片和文档/文本文件，进行整体压缩: {folder_path.name}")
                return self.COMPRESS_MODE_ENTIRE, dict(file_ext_count)
        
        # 如果部分文件匹配目标类型，选择性压缩
        if matching_count > 0:
            return self.COMPRESS_MODE_SELECTIVE, dict(file_ext_count)
            
        # 如果没有文件匹配，默认跳过
        return self.COMPRESS_MODE_SKIP, dict(file_ext_count)
    
    def _generate_recommendation(self, folder_path: Path, 
                               file_types_count: Counter,
                               compress_mode: str) -> str:
        """生成处理建议"""
        if not file_types_count:
            return "空文件夹，无需处理"
        
        # 获取主要文件类型
        dominant_types = self._get_dominant_types(file_types_count)
        dominant_types_str = ", ".join(dominant_types)
        
        if compress_mode == self.COMPRESS_MODE_ENTIRE:
            return f"建议整体压缩，主要包含: {dominant_types_str}"
        elif compress_mode == self.COMPRESS_MODE_SELECTIVE:
            return f"建议选择性压缩这些类型: {dominant_types_str}"
        else:
            return f"建议自定义处理，主要包含: {dominant_types_str}"
    
    def analyze_single_folder(self, folder_path: Path, parent_path: str = "", depth: int = 1, 
                             target_file_types: List[str] = None) -> FolderInfo:
        """
        分析单个文件夹，不递归分析子文件夹
        
        Args:
            folder_path: 要分析的文件夹路径
            parent_path: 父文件夹路径
            depth: 文件夹深度
            target_file_types: 目标文件类型列表，用于判断压缩模式
            
        Returns:
            FolderInfo: 文件夹信息
        """
        if isinstance(folder_path, str):
            folder_path = Path(folder_path)
        
        # 检查是否为黑名单路径
        if is_blacklisted_path(folder_path):
            return None
        
        # 创建文件夹信息对象
        folder_info = FolderInfo(
            path=str(folder_path),
            name=folder_path.name,
            parent_path=parent_path,
            depth=depth
        )
        
        # 计算文件夹权重
        folder_info.weight = self.calculate_folder_weight(folder_path)
        
        # 只获取当前文件夹中的文件（不包括子文件夹中的文件）
        try:
            all_files = list(folder_path.glob('*'))
            regular_files = [f for f in all_files if f.is_file()]
            
            # 记录总文件数和总大小
            folder_info.total_files = len(regular_files)
            folder_info.total_size = sum(f.stat().st_size for f in regular_files)
            folder_info.size_mb = folder_info.total_size / (1024 * 1024)
            
            # 分析文件类型分布
            file_types_count = Counter()
            file_ext_count = Counter()
            
            # 获取文件类型管理器
            file_type_manager = FileTypeManager()
            
            for file in regular_files:
                # 获取文件扩展名
                ext = file.suffix.lower()
                
                # 获取文件分类
                file_type = get_mime_category(file)
                if file_type:
                    file_types_count[file_type] += 1
                    
                    # 只记录符合目标文件类型的扩展名
                    # 如果指定了target_file_types，只记录这些类型的文件扩展名
                    # 否则记录所有已知文件类型的扩展名
                    should_record_ext = False
                    if target_file_types:
                        # 检查文件是否属于目标类型
                        if file_type_manager.is_file_in_types(file, target_file_types):
                            should_record_ext = True
                    else:
                        # 没有指定target_file_types，记录所有非空扩展名
                        should_record_ext = True
                    
                    if should_record_ext and ext:
                        file_ext_count[ext] += 1
                    
            # 记录文件类型分布
            folder_info.file_types = dict(file_types_count)
            folder_info.file_extensions = dict(file_ext_count)  # 只记录符合目标类型的文件扩展名
            folder_info.dominant_types = self._get_dominant_types(folder_info.file_types)
            
            # 确定压缩模式 - 传入目标文件类型
            folder_info.compress_mode, folder_info.file_extensions = self._determine_compress_mode(
                folder_path, 
                regular_files, 
                file_types_count,
                target_file_types
            )
            
            # 生成推荐处理方式
            folder_info.recommendation = self._generate_recommendation(
                folder_path,
                file_types_count,
                folder_info.compress_mode
            )
            
        except Exception as e:
            logging.error(f"分析文件夹时出错: {folder_path}, {str(e)}")
        
        return folder_info    
    def analyze_folder_structure(self, root_folder: Path, target_file_types: List[str] = None) -> FolderInfo:
        """
        分析文件夹结构，遍历所有子文件夹，构建树状结构
        
        Args:
            root_folder: 根文件夹路径
            target_file_types: 目标文件类型列表，用于判断压缩模式
            
        Returns:
            FolderInfo: 包含树状结构的根文件夹信息
        """
        if isinstance(root_folder, str):
            root_folder = Path(root_folder)
        
        return self._build_folder_tree(root_folder, "", 1, target_file_types)

    def _build_folder_tree(self, folder_path: Path, parent_path: str = "", depth: int = 1, 
                         target_file_types: List[str] = None) -> FolderInfo:
        """
        递归构建文件夹树结构
        
        Args:
            folder_path: 当前处理的文件夹路径
            parent_path: 父文件夹路径
            depth: 当前深度
            target_file_types: 目标文件类型
            
        Returns:
            FolderInfo: 当前文件夹的树状结构
        """
        # 检查是否为黑名单路径
        if is_blacklisted_path(folder_path):
            return None
        
        # 创建当前文件夹的信息对象
        folder_info = FolderInfo(
            path=str(folder_path),
            name=folder_path.name,
            parent_path=parent_path,
            depth=depth
        )
        
        # 计算文件夹权重
        folder_info.weight = self.calculate_folder_weight(folder_path)
        
        # 递归处理所有子文件夹（多线程并发）
        children = []
        has_child_with_archive = False
        subfolders = [item for item in folder_path.glob('*') if item.is_dir()]
        def process_child(item):
            return self._build_folder_tree(
                item, 
                parent_path=str(folder_path),
                depth=depth + 1,
                target_file_types=target_file_types
            )
        with ThreadPoolExecutor() as executor:
            future_to_item = {executor.submit(process_child, item): item for item in subfolders}
            for future in as_completed(future_to_item):
                child_info = future.result()
                if child_info:
                    children.append(child_info)
                    # 检查子文件夹中是否有archive类型
                    if child_info.file_types.get("archive", 0) > 0 or child_info.compress_mode == self.COMPRESS_MODE_SKIP:
                        has_child_with_archive = True
        # 按权重降序和名称升序排序子文件夹
        children.sort(key=lambda x: (-x.weight, x.name))
        folder_info.children = children
        
        # 分析当前文件夹文件（不包括子文件夹）
        try:
            all_items = list(folder_path.glob('*'))
            regular_files = [f for f in all_items if f.is_file()]
            # 记录总文件数
            folder_info.total_files = len(regular_files)
            # 注释掉统计文件大小相关代码
            # folder_info.total_size = sum(f.stat().st_size for f in regular_files)
            # folder_info.size_mb = folder_info.total_size / (1024 * 1024)
            # 分析文件类型分布
            file_types_count = Counter()
            file_ext_count = Counter()
            for file in regular_files:
                ext = file.suffix.lower()
                file_ext_count[ext] += 1
                file_type = get_mime_category(file)
                if file_type:
                    file_types_count[file_type] += 1
            folder_info.file_types = dict(file_types_count)
            folder_info.file_extensions = dict(file_ext_count)
            folder_info.dominant_types = self._get_dominant_types(folder_info.file_types)
            folder_info.compress_mode, folder_info.file_extensions = self._determine_compress_mode(
                folder_path, 
                regular_files, 
                file_types_count,
                target_file_types,
                has_child_with_archive
            )
            for child in folder_info.children:
                if child.compress_mode not in [None, "", self.COMPRESS_MODE_SKIP]:
                    if folder_info.compress_mode == self.COMPRESS_MODE_ENTIRE:
                        folder_info.compress_mode = self.COMPRESS_MODE_SELECTIVE
            folder_info.recommendation = self._generate_recommendation(
                folder_path,
                file_types_count,
                folder_info.compress_mode
            )
        except Exception as e:
            logging.error(f"分析文件夹时出错: {folder_path}, {str(e)}")
        return folder_info
    
    def generate_config_json(self, root_folder: Path,
                          output_path: Optional[Path] = None,
                          target_file_types: List[str] = None,
                          root_info: Optional[FolderInfo] = None) -> str: # 添加 root_info 参数
        """
        生成树状结构的文件夹配置JSON
        
        Args:
            root_folder: 根文件夹路径
            output_path: 输出JSON文件的路径，默认为与文件夹同名的json文件
            target_file_types: 目标文件类型列表，用于记录在配置中
            root_info: 可选的预先分析好的根文件夹信息
        
        Returns:
            str: 生成的JSON配置文件路径
        """
        # 如果没有提供 root_info，则分析文件夹树结构
        if root_info is None:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]正在分析文件夹结构..."),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                task = progress.add_task("[green]分析中...", total=None)
                root_info = self.analyze_folder_structure(root_folder, target_file_types=target_file_types)
                progress.update(task, completed=100)

        # 检查 root_info 是否有效
        if root_info is None:
             raise ValueError("无法获取文件夹信息，分析失败。")

        # 准备配置数据 (树形结构)
        config = {
            "folder_tree": root_info.to_tree_dict(),
            "config": {
                "timestamp": datetime.datetime.now().isoformat(),
                "target_file_types": target_file_types or []
            }
        }
        
        # 确定输出路径
        if output_path is None:
            output_path = Path(root_folder) / f"{Path(root_folder).name}_config.json"
        else:
            output_path = Path(output_path)
        
        # 写入JSON文件 - 使用UTF-8编码并确保不使用ASCII转义中文字符
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        console.print(f"[bold green]✓[/] 已生成配置文件: {output_path}")
        logging.info(f"已生成配置文件: {output_path}")
        return str(output_path)
    
    def analyze_folders(self, folder_paths: Union[str, Path, List[Union[str, Path]]], 
                     target_file_types: List[str] = None,
                     output_dir: Optional[Union[str, Path]] = None) -> Dict[str, str]:
        """
        分析多个文件夹并生成配置文件
        
        Args:
            folder_paths: 单个文件夹路径或文件夹路径列表
            target_file_types: 目标文件类型列表，例如 ['image', 'video']
            output_dir: 输出目录，默认为每个文件夹所在目录
            
        Returns:
            Dict[str, str]: 文件夹路径到生成的配置文件路径的映射
        """
        if isinstance(folder_paths, (str, Path)):
            folder_paths = [folder_paths]
        
        result = {}
        
        for folder_path in folder_paths:
            folder_path = Path(folder_path)
            
            if not folder_path.exists() or not folder_path.is_dir():
                logging.error(f"路径不存在或不是文件夹: {folder_path}")
                continue
            
            # 确定输出路径
            if output_dir:
                output_path = Path(output_dir) / f"{folder_path.name}_config.json"
            else:
                output_path = folder_path / f"{folder_path.name}_config.json"
            
            try:
                # 生成配置文件
                config_path = self.generate_config_json(
                    folder_path,
                    output_path,
                    target_file_types
                )
                
                result[str(folder_path)] = config_path
                logging.info(f"成功分析文件夹: {folder_path}")
            except Exception as e:
                logging.error(f"分析文件夹失败: {folder_path}, 错误: {str(e)}")
                import traceback
                logging.error(traceback.format_exc())
        
        return result


def display_folder_structure(root_folder: FolderInfo):
    """将树状结构的文件夹结构打印到控制台，使用Rich美化"""
    console.print(Panel.fit("[bold cyan]文件夹结构分析[/bold cyan]", border_style="cyan"))
    
    # 获取根文件夹压缩模式的颜色和名称
    root_mode_color = {
        "entire": "green",
        "selective": "yellow",
        "skip": "red"
    }.get(root_folder.compress_mode, "white")
    
    root_mode_name = {
        "entire": "🦷整体压缩",
        "selective": "🪴选择性压缩",
        "skip": "🥷跳过"
    }.get(root_folder.compress_mode, "未设置")
    
    # 创建Rich树状结构
    tree = Tree(f"[bold yellow]{root_folder.name}[/bold yellow] [dim]({root_folder.total_files}个文件, "
               f"{root_folder.size_mb:.2f} MB, 模式: {root_mode_name})[/dim]")
    
    # 显示根文件夹的文件类型
    if root_folder.file_types:
        for file_type, count in sorted(root_folder.file_types.items(), key=lambda x: x[1], reverse=True)[:3]:
            type_color = "green" if file_type in ["image", "video"] else "blue"
            tree.add(f"[{type_color}]{file_type}[/{type_color}]: {count}个文件")
    
    # 递归添加子文件夹
    _add_folder_to_tree(tree, root_folder)
    
    # 打印树
    console.print(tree)
    
    # 显示更详细的压缩统计
    stats = _collect_compression_stats(root_folder)
    
    table = Table(title="压缩模式统计", show_header=True, header_style="bold magenta")
    table.add_column("压缩模式", style="cyan")
    table.add_column("文件夹数量", style="green")
    table.add_column("总文件数", style="yellow")
    table.add_column("总大小 (MB)", style="blue")
    
    # 添加统计数据
    for mode, data in stats.items():
        mode_name = {
            "entire": "🦷整体压缩",
            "selective": "🪴选择性压缩",
            "skip": "🥷跳过",
            "none": "未设置"
        }.get(mode, mode)
        
        table.add_row(
            mode_name,
            str(data["count"]),
            str(data["files"]),
            f"{data['size']:.2f}"
        )
    
    console.print(table)
    
    # 显示建议的压缩操作
    compression_table = Table(title="建议压缩操作", show_header=True, header_style="bold blue")
    compression_table.add_column("文件夹", style="cyan")
    compression_table.add_column("压缩模式", style="green")
    compression_table.add_column("文件数", style="yellow")
    compression_table.add_column("大小 (MB)", style="blue")
    compression_table.add_column("建议", style="magenta")
    
    # 获取所有需要压缩的文件夹
    compression_folders = _get_compression_folders(root_folder)
    
    # 按大小排序
    compression_folders.sort(key=lambda x: x.size_mb, reverse=True)
    
    # 添加前10个最大的需要压缩的文件夹
    for folder in compression_folders[:10]:
        mode_name = {
            "entire": "🦷整体压缩",
            "selective": "🪴选择性压缩"
        }.get(folder.compress_mode, "未知")
        
        compression_table.add_row(
            folder.name,
            mode_name,
            str(folder.total_files),
            f"{folder.size_mb:.2f}",
            folder.recommendation
        )
    
    console.print(compression_table)

def _add_folder_to_tree(parent_tree: Tree, folder: FolderInfo):
    """递归地将文件夹添加到Rich树中"""
    for child in folder.children:
        # 根据压缩模式选择颜色
        mode_color = {
            "entire": "green",
            "selective": "yellow",
            "skip": "red"
        }.get(child.compress_mode, "white")
        
        # 获取压缩模式的中文名称
        mode_name = {
            "entire": "🦷整体压缩",
            "selective": "🪴选择性压缩",
            "skip": "🥷跳过"
        }.get(child.compress_mode, "未设置")
        
        # 创建子树
        child_tree = parent_tree.add(
            f"[bold {mode_color}]{child.name}[/bold {mode_color}] [dim]({child.total_files}个文件, "
            f"{child.size_mb:.2f} MB, 模式: {mode_name})[/dim]"
        )
        
        # 添加文件类型信息
        if child.file_types:
            for file_type, count in sorted(child.file_types.items(), key=lambda x: x[1], reverse=True)[:3]:
                type_color = "green" if file_type in ["image", "video"] else "blue"
                child_tree.add(f"[{type_color}]{file_type}[/{type_color}]: {count}个文件")
        
        # 递归处理子文件夹
        _add_folder_to_tree(child_tree, child)

def _collect_compression_stats(folder: FolderInfo) -> Dict[str, Dict[str, Any]]:
    """收集文件夹的压缩模式统计数据"""
    # 初始化统计数据
    stats = {
        "entire": {"count": 0, "files": 0, "size": 0.0},
        "selective": {"count": 0, "files": 0, "size": 0.0},
        "skip": {"count": 0, "files": 0, "size": 0.0},
        "none": {"count": 0, "files": 0, "size": 0.0}
    }
    
    # 添加当前文件夹数据
    mode = folder.compress_mode or "none"
    stats[mode]["count"] += 1
    stats[mode]["files"] += folder.total_files
    stats[mode]["size"] += folder.size_mb
    
    # 递归处理子文件夹
    for child in folder.children:
        child_stats = _collect_compression_stats(child)
        for mode, data in child_stats.items():
            stats[mode]["count"] += data["count"]
            stats[mode]["files"] += data["files"]
            stats[mode]["size"] += data["size"]
    
    return stats

def _get_compression_folders(folder: FolderInfo) -> List[FolderInfo]:
    """获取所有需要压缩的文件夹"""
    result = []
    
    # 如果当前文件夹需要压缩，添加到结果
    if folder.compress_mode in ["entire", "selective"]:
        result.append(folder)
    
    # 递归处理子文件夹
    for child in folder.children:
        result.extend(_get_compression_folders(child))
    
    return result

def analyze_folder(folder_path: Union[str, Path], target_file_types: List[str] = None, 
                  output_path: Optional[Union[str, Path]] = None, display: bool = False) -> str:
    """
    API函数：分析单个文件夹并生成配置
    
    Args:
        folder_path: 要分析的文件夹路径
        target_file_types: 目标文件类型列表
        output_path: 输出配置文件路径
        display: 是否在控制台显示结果
        
    Returns:
        str: 生成的配置文件路径
    """
    if isinstance(folder_path, str):
        folder_path = Path(folder_path)
    
    if not folder_path.exists() or not folder_path.is_dir():
        console.print(f"[bold red]错误:[/bold red] 指定的路径不存在或不是文件夹: {folder_path}")
        raise ValueError(f"指定的路径不存在或不是文件夹: {folder_path}")
    
    # 显示分析信息
    console.print(f"[bold blue]开始分析文件夹:[/bold blue] {folder_path}")
    if target_file_types:
        console.print(f"[bold blue]目标文件类型:[/bold blue] {', '.join(target_file_types)}")
    
    # 创建文件夹分析器
    analyzer = FolderAnalyzer()
    
    # 分析文件夹结构 (只执行一次)
    root_info = analyzer.analyze_folder_structure(folder_path, target_file_types=target_file_types)

    # 如果 root_info 为 None (例如，路径是黑名单)，则提前退出或抛出错误
    if root_info is None:
        console.print(f"[bold yellow]警告:[/bold yellow] 文件夹分析未返回有效信息 (可能在黑名单中): {folder_path}")
        # 根据需要决定是返回 None, 空字符串, 还是抛出异常
        # 这里选择抛出异常，因为后续需要 root_info
        raise ValueError(f"无法分析文件夹: {folder_path}")


    # 如果需要在控制台显示结果
    if display:
        display_folder_structure(root_info)

    # 生成配置文件，传入已分析的 root_info
    config_path = analyzer.generate_config_json(
        folder_path,
        output_path,
        target_file_types,
        root_info=root_info  # 传递 root_info
    )
    
    console.print(f"[bold green]分析完成！ 配置文件已保存到: {config_path}[/bold green]")
    logging.info(f"分析完成，配置文件已保存到: {config_path}")
    return config_path


def main():
    """主函数，处理命令行参数并执行文件夹分析"""
    console.print(Panel.fit("[bold cyan]文件夹分析工具[/bold cyan]", border_style="cyan"))
    
    parser = argparse.ArgumentParser(description='文件夹分析工具')
    parser.add_argument('--path', '-p', type=str, required=True, help='要分析的文件夹路径')
    parser.add_argument('--output', '-o', type=str, help='输出配置JSON的路径，默认为[文件夹名]_config.json')
    parser.add_argument('--display', '-d', action='store_true', help='在控制台显示分析结果')
    parser.add_argument('--types', '-t', type=str, help='要关注的文件类型，逗号分隔，例如: image,video')
    
    args = parser.parse_args()
    
    folder_path = Path(args.path)
    output_path = args.output
    target_file_types = args.types.split(',') if args.types else None
    
    try:
        # 使用API函数分析文件夹
        config_path = analyze_folder(
            folder_path, 
            target_file_types=target_file_types,
            output_path=output_path,
            display=args.display
        )
        
        console.print(f"[bold green]✓[/bold green] 分析完成，配置文件已保存到: {config_path}")
    
    except Exception as e:
        console.print(f"[bold red]✗[/bold red] 分析过程中出错: {str(e)}")
        import traceback
        console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    main()