"""
压缩模块 - 提供压缩相关功能
"""
import os
import shutil
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple, Dict

from .models import CompressionResult
from ..config.config import SEVEN_ZIP_PATH, COMPRESSION_LEVEL
from ..config.file_types import IMAGE_EXTENSIONS, ALLOW_REPACK_EXTENSIONS
from ..file_ops.file_utils import safe_path, safe_copy_file, safe_remove_file, get_folder_size, cmd_delete

logger = logging.getLogger(__name__)

class ZipCompressor:
    """压缩处理类，封装所有压缩相关的操作"""
    
    def __init__(self, seven_zip_path: str = SEVEN_ZIP_PATH,
                compression_level: int = COMPRESSION_LEVEL):
        """
        初始化压缩器
        
        Args:
            seven_zip_path: 7-Zip可执行文件路径
            compression_level: 压缩级别（1-9）
        """
        self.seven_zip_path = seven_zip_path
        self.compression_level = compression_level
    
    def create_temp_workspace(self) -> Tuple[Path, Path]:
        """
        创建临时工作目录
        
        Returns:
            临时基础目录和工作目录的元组
        """
        temp_base = tempfile.mkdtemp(prefix="zip_")
        temp_base_path = Path(temp_base)
        temp_work_dir = temp_base_path / "work"
        temp_work_dir.mkdir(exist_ok=True)
        return temp_base_path, temp_work_dir
    
    def compress_files(self, source_path: Path, target_zip: Path, 
                      files_to_zip: List[Path] = None, 
                      delete_source: bool = False) -> subprocess.CompletedProcess:
        """
        压缩文件到目标路径
        
        Args:
            source_path: 源文件夹路径
            target_zip: 目标zip文件路径
            files_to_zip: 要压缩的文件列表（如果为None则压缩整个文件夹）
            delete_source: 压缩后是否删除源文件
            
        Returns:
            压缩命令的执行结果
        """
        logger.info(f"[#process]🔄 开始压缩: {source_path}")
        
        if files_to_zip:
            # 压缩指定的文件列表
            files_str = " ".join(f'"{safe_path(f)}"' for f in files_to_zip)
            cmd = f'"{self.seven_zip_path}" a -r -aoa -tzip -mx={self.compression_level} "{safe_path(target_zip)}" {files_str}'
        else:
            # 压缩整个目录
            cmd = f'"{self.seven_zip_path}" a -r -aoa -tzip -mx={self.compression_level} "{safe_path(target_zip)}" "{safe_path(source_path)}\\*"'
            if delete_source:
                cmd += " -sdel"
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"[#process]✅ 压缩完成: {target_zip}")
        else:
            logger.info(f"[#process]❌ 压缩失败: {result.stderr}")
        return result
    
    def _has_archive_files(self, folder_path: Path) -> bool:
        """
        检查文件夹及其子文件夹中是否包含压缩包文件
        
        Args:
            folder_path: 要检查的文件夹路径
            
        Returns:
            是否包含压缩包文件
        """
        # 定义压缩文件扩展名
        archive_extensions = {".zip", ".rar", ".7z", ".cbz", ".cbr"}
        
        # 递归检查文件夹中的所有文件
        for file_path in folder_path.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in archive_extensions:
                logger.info(f"[#file_ops]🔍 发现压缩包文件: {file_path}")
                return True
        
        return False
    
    def _cleanup_empty_folder(self, folder_path: Path) -> None:
        """
        清理空文件夹
        
        Args:
            folder_path: 要清理的文件夹路径
        """
        if not any(folder_path.iterdir()):
            try:
                folder_path.rmdir()
                logger.info(f"[#file_ops]🗑️ 已删除空文件夹: {folder_path}")
            except Exception as e:
                logger.info(f"[#file_ops]❌ 删除空文件夹失败: {folder_path}, 错误: {e}")


def compare_zip_contents(zip1_path: Path, zip2_path: Path) -> bool:
    """
    比较两个压缩包的内容是否相同
    
    Args:
        zip1_path: 第一个压缩包路径
        zip2_path: 第二个压缩包路径
        
    Returns:
        如果两个压缩包的文件数量和大小都相同，返回True
    """
    try:
        # 使用7z l命令列出压缩包内容
        cmd1 = f'"{SEVEN_ZIP_PATH}" l "{zip1_path}"'
        cmd2 = f'"{SEVEN_ZIP_PATH}" l "{zip2_path}"'
        
        result1 = subprocess.run(cmd1, shell=True, capture_output=True, text=True)
        result2 = subprocess.run(cmd2, shell=True, capture_output=True, text=True)
        
        if result1.returncode != 0 or result2.returncode != 0:
            return False
            
        # 解析输出，获取文件列表和大小
        def parse_7z_output(output: str) -> Dict[str, int]:
            files = {}
            for line in output.split('\n'):
                # 7z输出格式：日期 时间 属性 大小 压缩后大小 文件名
                parts = line.strip().split()
                if len(parts) >= 5 and parts[0][0].isdigit():  # 确保是文件行
                    try:
                        size = int(parts[3])
                        name = ' '.join(parts[5:])  # 文件名可能包含空格
                        files[name] = size
                    except (ValueError, IndexError):
                        continue
            return files
            
        files1 = parse_7z_output(result1.stdout)
        files2 = parse_7z_output(result2.stdout)
        
        # 比较文件数量和总大小
        if len(files1) != len(files2):
            return False
            
        # 比较每个文件的大小
        return all(files1.get(name) == files2.get(name) for name in files1)
    except Exception as e:
        logger.info(f"❌ 比较压缩包时发生错误: {e}")
        return False