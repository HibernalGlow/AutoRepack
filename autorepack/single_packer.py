#!/usr/bin/env python
"""
单层文件夹打包工具

将单个目录下的一级内容处理为独立的压缩包：
1. 将每个一级子文件夹打包成独立的压缩包
2. 将一级目录下的所有图片文件打包成一个压缩包
3. 压缩包名称基于父文件夹名称
"""

import os
import shutil
import tempfile
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger
# 使用autorepack的日志器
from rich.console import Console
console = Console()

class SinglePacker:
    """单层目录打包工具
    
    只处理指定目录下的一级内容：
    1. 将每个一级子文件夹打包成独立的压缩包
    2. 将一级目录下的所有图片文件打包成一个压缩包
    3. 压缩包名称基于父文件夹名称
    """
    
    SUPPORTED_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp', '.jxl', '.avif', '.gif')
    
    def __init__(self):
        """初始化单层打包工具
        
        Args:
            logger: 日志对象，如果不提供将使用默认日志器
        """
        
    
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
            
            # 处理子文件夹
            for subdir in subdirs:
                current_task += 1
                progress = (current_task / total_tasks) * 100
                logger.info(f"总进度: ({current_task}/{total_tasks}) {progress:.1f}%")
                console.print(f"[cyan]总进度: ({current_task}/{total_tasks}) {progress:.1f}%[/cyan]")
                
                subdir_name = os.path.basename(subdir)
                archive_name = f"{subdir_name}.zip"
                archive_path = os.path.join(directory_path, archive_name)
                
                logger.info(f"🔄 打包子文件夹: {subdir_name}")
                console.print(f"[blue]🔄 打包子文件夹: {subdir_name}[/blue]")
                
                if self._create_archive(subdir, archive_path):
                    if delete_after:
                        self._cleanup_source(subdir)
            
            # 处理散图文件
            if images:
                current_task += 1
                progress = (current_task / total_tasks) * 100
                logger.info(f"总进度: ({current_task}/{total_tasks}) {progress:.1f}%")
                console.print(f"[cyan]总进度: ({current_task}/{total_tasks}) {progress:.1f}%[/cyan]")
                
                images_archive_name = f"{base_name}.zip"
                images_archive_path = os.path.join(directory_path, images_archive_name)
                
                # 创建临时目录存放图片
                with tempfile.TemporaryDirectory() as temp_dir:
                    for image in images:
                        shutil.copy2(image, temp_dir)
                    
                    logger.info(f"🔄 打包散图文件: {len(images)}个文件")
                    console.print(f"[blue]🔄 打包散图文件: {len(images)}个文件[/blue]")
                    
                    if self._create_archive(temp_dir, images_archive_path):
                        # 删除原始图片文件
                        if delete_after:
                            for image in images:
                                self._cleanup_source(image)
            
            logger.info("✅ 打包完成")
            console.print(f"[green]✅ 打包完成: {directory_path}[/green]")
            
        except Exception as e:
            logger.error(f"❌ 处理过程中出现错误: {str(e)}")
            console.print(f"[red]❌ 处理过程中出现错误: {str(e)}[/red]")
    
    def _create_archive(self, source_path: str, archive_path: str) -> bool:
        """创建压缩包
        
        Args:
            source_path: 要打包的源路径
            archive_path: 目标压缩包路径
            
        Returns:
            bool: 压缩是否成功
        """
        try:
            cmd = ['7z', 'a', '-tzip', archive_path, f"{source_path}\\*"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"❌ 创建压缩包失败: {archive_path}\n{result.stderr}")
                console.print(f"[red]❌ 创建压缩包失败: {archive_path}[/red]")
                return False
            else:
                logger.info(f"✅ 创建压缩包成功: {os.path.basename(archive_path)}")
                console.print(f"[green]✅ 创建压缩包成功: {os.path.basename(archive_path)}[/green]")
                
                # 验证压缩包完整性
                logger.info(f"🔄 正在验证压缩包完整性: {os.path.basename(archive_path)}")
                test_cmd = ['7z', 't', archive_path]
                test_result = subprocess.run(test_cmd, capture_output=True, text=True)
                
                if test_result.returncode != 0:
                    logger.error(f"❌ 压缩包验证失败: {archive_path}\n{test_result.stderr}")
                    console.print(f"[red]❌ 压缩包验证失败: {archive_path}[/red]")
                    return False
                else:
                    logger.info(f"✅ 压缩包验证成功: {os.path.basename(archive_path)}")
                    console.print(f"[green]✅ 压缩包验证成功: {os.path.basename(archive_path)}[/green]")
                    return True
                
        except Exception as e:
            logger.error(f"❌ 创建压缩包时出现错误: {str(e)}")
            console.print(f"[red]❌ 创建压缩包时出现错误: {str(e)}[/red]")
            return False
            
    def _cleanup_source(self, source_path: str):
        """清理源文件或文件夹
        
        Args:
            source_path: 要清理的源路径
        """
        try:
            if os.path.isdir(source_path):
                shutil.rmtree(source_path)
                logger.info(f"✅ 已删除源文件夹: {os.path.basename(source_path)}")
                console.print(f"[green]✅ 已删除源文件夹: {os.path.basename(source_path)}[/green]")
            elif os.path.isfile(source_path):
                os.remove(source_path)
                logger.info(f"✅ 已删除源文件: {os.path.basename(source_path)}")
                console.print(f"[green]✅ 已删除源文件: {os.path.basename(source_path)}[/green]")
        except Exception as e:
            logger.error(f"❌ 清理源文件时出现错误: {str(e)}")
            console.print(f"[red]❌ 清理源文件时出现错误: {str(e)}[/red]")
    
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
