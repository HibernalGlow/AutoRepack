#!/usr/bin/env python
"""
单层文件夹打包工具

将单个目录下的一级内容处理为独立的压缩包：
1. 将每个一级子文件夹打包成独立的压缩包
2. 将一级目录下的所有图片文件打包成一个压缩包
3. 压缩包名称基于父文件夹名称
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger
from rich.console import Console

# 复用核心压缩器
from repacku.core.zip_compressor import ZipCompressor, CompressionResult

console = Console()

class SinglePacker:
    """单层目录打包工具
    
    只处理指定目录下的一级内容：
    1. 将每个一级子文件夹打包成独立的压缩包
    2. 将一级目录下的所有图片文件打包成一个压缩包
    3. 压缩包名称基于父文件夹名称
    """
    
    SUPPORTED_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp', '.jxl', '.avif', '.gif')
    
    def __init__(self, compression_level: Optional[int] = None, threads: int = 16):
        """初始化单层打包工具并复用 ZipCompressor
        
        Args:
            compression_level: 压缩级别(0-9)，不传则读取配置
            threads: 压缩线程数
        """
        self.compressor = ZipCompressor(compression_level=compression_level, threads=threads)

    # ---------------- Internal helpers -----------------
    def _has_internal_archive(self, folder_path: str | Path) -> bool:
        """检测文件夹内部(递归)是否已存在压缩包文件
        
        用于跳过已经含有压缩结果的目录，避免重复打包。
        支持常见后缀: .zip .7z .rar .tar .gz .bz2 .xz
        """
        p = Path(folder_path)
        if not p.exists() or not p.is_dir():
            return False
        archive_exts = {'.zip', '.7z', '.rar', '.tar', '.gz', '.bz2', '.xz'}
        for child in p.rglob('*'):
            if child.is_file() and child.suffix.lower() in archive_exts:
                return True
        return False
    
    def pack_directory(self, directory_path: str, delete_after: bool = True):
        """处理指定目录的单层打包
        
        Args:
            directory_path: 要处理的目录路径
            delete_after: 打包后是否删除源文件
        """
        try:
            directory_path = os.path.abspath(directory_path)
            if not os.path.exists(directory_path):
                logger.error(f"❌ 目录不存在: {directory_path}")
                console.print(f"[red]❌ 目录不存在: {directory_path}[/red]")
                return
                
            if not os.path.isdir(directory_path):
                logger.error(f"❌ 指定路径不是目录: {directory_path}")
                console.print(f"[red]❌ 指定路径不是目录: {directory_path}[/red]")
                return
                
            base_name = os.path.basename(directory_path)
            logger.info(f"🔄 开始处理目录: {directory_path}")
            console.print(f"[blue]🔄 开始处理目录: {directory_path}[/blue]")
            
            # 获取一级目录内容
            items = os.listdir(directory_path)
            subdirs = []
            images = []
            
            for item in items:
                item_path = os.path.join(directory_path, item)
                if os.path.isdir(item_path):
                    subdirs.append(item_path)
                elif os.path.isfile(item_path) and item_path.lower().endswith(self.SUPPORTED_IMAGE_EXTENSIONS):
                    images.append(item_path)
            
            # 计算总任务数
            total_tasks = len(subdirs) + (1 if images else 0)
            current_task = 0
            
            # 处理子文件夹 (使用 ZipCompressor)
            for subdir in subdirs:
                current_task += 1
                progress = (current_task / total_tasks) * 100 if total_tasks else 100
                logger.info(f"总进度: ({current_task}/{total_tasks}) {progress:.1f}%")
                console.print(f"[cyan]总进度: ({current_task}/{total_tasks}) {progress:.1f}%[/cyan]")

                subdir_name = os.path.basename(subdir)

                # 检查内部是否已有压缩包
                if self._has_internal_archive(subdir):
                    logger.info(f"⏭️ 跳过子文件夹(已含压缩包): {subdir_name}")
                    console.print(f"[yellow]⏭️ 跳过子文件夹(已含压缩包): {subdir_name}[/yellow]")
                    continue

                archive_path = Path(directory_path) / f"{subdir_name}.zip"
                logger.info(f"🔄 打包子文件夹: {subdir_name}")
                console.print(f"[blue]🔄 打包子文件夹: {subdir_name}[/blue]")

                result = self.compressor.compress_entire_folder(
                    Path(subdir),
                    archive_path,
                    delete_source=delete_after,
                    keep_folder_structure=True  # 原逻辑是仅包含内容，不保留外层
                )
                if not result.success:
                    logger.error(f"❌ 子文件夹压缩失败: {subdir_name} -> {result.error_message}")
                    console.print(f"[red]❌ 子文件夹压缩失败: {subdir_name}[/red]")

            # 处理散图文件 (复用 compress_files)
            if images:
                current_task += 1
                progress = (current_task / total_tasks) * 100 if total_tasks else 100
                logger.info(f"总进度: ({current_task}/{total_tasks}) {progress:.1f}%")
                console.print(f"[cyan]总进度: ({current_task}/{total_tasks}) {progress:.1f}%[/cyan]")

                images_archive_path = Path(directory_path) / f"{base_name}.zip"
                logger.info(f"🔄 打包散图文件: {len(images)}个文件")
                console.print(f"[blue]🔄 打包散图文件: {len(images)}个文件[/blue]")

                # 使用 compress_files 非递归匹配同级图片；传入扩展名列表
                image_ext_list = list(self.SUPPORTED_IMAGE_EXTENSIONS)
                result = self.compressor.compress_files(
                    Path(directory_path),
                    images_archive_path,
                    file_extensions=image_ext_list,
                    delete_source=delete_after
                )
                if not result.success:
                    logger.error(f"❌ 散图压缩失败: {result.error_message}")
                    console.print(f"[red]❌ 散图压缩失败[/red]")
            
            logger.info("✅ 打包完成")
            console.print(f"[green]✅ 打包完成: {directory_path}[/green]")
            
        except Exception as e:
            logger.error(f"❌ 处理过程中出现错误: {str(e)}")
            console.print(f"[red]❌ 处理过程中出现错误: {str(e)}[/red]")
    
    # 原 _create_archive 与 _cleanup_source 已由 ZipCompressor 取代
    
    def process_gallery_folders(self, directory_path: str, delete_after: bool = True):
        """处理指定目录下的所有.画集文件夹
        
        Args:
            directory_path: 要处理的目录路径
            delete_after: 打包后是否删除源文件
        """
        try:
            directory_path = os.path.abspath(directory_path)
            if not os.path.exists(directory_path):
                logger.error(f"❌ 目录不存在: {directory_path}")
                console.print(f"[red]❌ 目录不存在: {directory_path}[/red]")
                return
                
            if not os.path.isdir(directory_path):
                logger.error(f"❌ 指定路径不是目录: {directory_path}")
                console.print(f"[red]❌ 指定路径不是目录: {directory_path}[/red]")
                return
            
            logger.info(f"🔍 开始扫描目录寻找.画集文件夹: {directory_path}")
            console.print(f"[blue]🔍 开始扫描目录寻找.画集文件夹: {directory_path}[/blue]")
            
            gallery_folders = []
            
            # 递归查找所有.画集文件夹
            for root, dirs, _ in os.walk(directory_path):
                for dir_name in dirs:
                    if ". 画集" in dir_name:
                        gallery_path = os.path.join(root, dir_name)
                        gallery_folders.append(gallery_path)
            
            if not gallery_folders:
                logger.info(f"⚠️ 在目录中未找到任何.画集文件夹: {directory_path}")
                console.print(f"[yellow]⚠️ 在目录中未找到任何.画集文件夹: {directory_path}[/yellow]")
                return
                
            logger.info(f"✅ 找到 {len(gallery_folders)} 个.画集文件夹")
            console.print(f"[green]✅ 找到 {len(gallery_folders)} 个.画集文件夹[/green]")
            
            # 处理每个.画集文件夹
            for i, gallery_folder in enumerate(gallery_folders):
                logger.info(f"画集处理进度: ({i+1}/{len(gallery_folders)})")
                console.print(f"[blue]画集处理进度: ({i+1}/{len(gallery_folders)})[/blue]")
                
                logger.info(f"🔄 处理画集文件夹: {gallery_folder}")
                console.print(f"[cyan]🔄 处理画集文件夹: {gallery_folder}[/cyan]")
                
                self.pack_directory(gallery_folder, delete_after)
                
            logger.info(f"✅ 所有.画集文件夹处理完成")
            console.print(f"[green]✅ 所有.画集文件夹处理完成[/green]")
            
        except Exception as e:
            logger.error(f"❌ 处理画集文件夹时出现错误: {str(e)}")
            console.print(f"[red]❌ 处理画集文件夹时出现错误: {str(e)}[/red]")


# 简单的测试代码
if __name__ == "__main__":
    # 配置基本日志
    logging.basicConfig(level=logging.INFO)
    
    import sys
    if len(sys.argv) > 1:
        path = sys.argv[1]
        gallery_mode = "--gallery" in sys.argv
        
        packer = SinglePacker()
        if gallery_mode:
            packer.process_gallery_folders(path)
        else:
            packer.pack_directory(path)
    else:
        print("请提供一个目录路径作为参数")
