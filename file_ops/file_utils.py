"""
文件操作工具函数 - 提供基础文件操作功能
"""
import os
import stat
import time
import shutil
import subprocess
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

def get_folder_size(folder_path: Path) -> int:
    """
    计算文件夹的总大小
    
    Args:
        folder_path: 要计算大小的文件夹路径
        
    Returns:
        文件夹中所有文件的总大小（字节）
    """
    return sum(f.stat().st_size for f in folder_path.rglob('*') if f.is_file())

def get_long_path_name(path_str: str) -> str:
    """
    转换为长路径格式，解决Windows长路径问题
    
    Args:
        path_str: 原始路径字符串
        
    Returns:
        转换后的长路径字符串
    """
    if not path_str.startswith("\\\\?\\"):
        if os.path.isabs(path_str):
            return "\\\\?\\" + path_str
    return path_str

def safe_path(path: Path) -> str:
    """
    确保路径支持长文件名，解决Windows文件路径长度限制
    
    Args:
        path: 原始路径对象
        
    Returns:
        支持长文件名的路径字符串
    """
    return get_long_path_name(str(path.absolute()))

def create_temp_dir(parent_dir: Path) -> Path:
    """
    在指定目录下创建临时目录
    
    Args:
        parent_dir: 父目录路径
        
    Returns:
        创建的临时目录路径
    """
    temp_dir = parent_dir / f"temp_{int(time.time())}_{os.getpid()}"
    temp_dir.mkdir(exist_ok=True)
    return temp_dir

def safe_copy_file(src: Path, dst: Path) -> bool:
    """
    安全地复制文件，处理各种错误情况
    
    Args:
        src: 源文件路径
        dst: 目标文件路径
        
    Returns:
        复制是否成功
    """
    logger.info(f"🔄 开始复制文件: {src} -> {dst}")
    try:
        # 使用长路径
        src_long = safe_path(src)
        dst_long = safe_path(dst)
        
        # 确保目标目录存在
        dst.parent.mkdir(parents=True, exist_ok=True)
        
        # 尝试直接复制
        try:
            logger.info("🔄 尝试直接复制文件...")
            with open(src_long, 'rb') as fsrc:
                with open(dst_long, 'wb') as fdst:
                    shutil.copyfileobj(fsrc, fdst)
            logger.info("✅ 文件复制成功")
            return True
        except Exception as e:
            logger.info(f"❌ 复制文件失败: {e}")
            return False
    except Exception as e:
        logger.info(f"❌ 复制文件失败: {src} -> {dst}, 错误: {str(e)}")
        return False

def safe_remove_file(file_path: Path) -> bool:
    """
    安全地删除文件，处理各种错误情况
    
    Args:
        file_path: 要删除的文件路径
        
    Returns:
        删除是否成功
    """
    try:
        # 使用长路径
        long_path = safe_path(file_path)
        
        # 尝试清除只读属性
        try:
            if file_path.exists():
                current_mode = file_path.stat().st_mode
                file_path.chmod(current_mode | stat.S_IWRITE)
        except Exception as e:
            logger.info(f"⚠️ 清除只读属性失败: {file_path}, 错误: {e}")
        
        # 尝试使用不同的方法删除文件
        try:
            # 方法1：直接删除
            os.remove(long_path)
            return True
        except Exception as e1:
            logger.info(f"❌ 直接删除失败，尝试其他方法: {e1}")
            try:
                # 方法2：使用Windows API删除
                if os.path.exists(long_path):
                    import ctypes
                    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
                    if kernel32.DeleteFileW(long_path):
                        return True
                    error = ctypes.get_last_error()
                    if error == 0:  # ERROR_SUCCESS
                        return True
                    logger.info(f"⚠️ Windows API删除失败，错误码: {error}")
            except Exception as e2:
                logger.info(f"❌ Windows API删除失败: {e2}")
                try:
                    # 方法3：使用shell删除
                    import subprocess
                    subprocess.run(['cmd', '/c', 'del', '/f', '/q', long_path], 
                                 shell=True, 
                                 capture_output=True)
                    if not os.path.exists(long_path):
                        return True
                except Exception as e3:
                    logger.info(f"❌ Shell删除失败: {e3}")
        
        return False
    except Exception as e:
        logger.info(f"❌ 删除文件失败: {file_path}, 错误: {str(e)}")
        return False

def cmd_delete(path: str, is_directory: bool = False) -> bool:
    """
    使用 CMD 命令删除文件或文件夹
    
    Args:
        path: 要删除的文件或文件夹路径
        is_directory: 是否是目录
        
    Returns:
        删除是否成功
    """
    try:
        if is_directory:
            # 删除目录及其所有内容
            cmd = f'cmd /c rmdir /s /q "{path}"'
        else:
            # 删除单个文件
            cmd = f'cmd /c del /f /q "{path}"'
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0
    except Exception as e:
        logger.info(f"❌ CMD删除失败 {path}: {e}")
        return False

def delete_empty_folders(directory: Path):
    """
    删除空文件夹
    
    Args:
        directory: 要清理的根目录
    """
    for root, dirs, files in os.walk(directory, topdown=False):
        for dir_name in dirs:
            dir_path = Path(root) / dir_name
            try:
                if not any(dir_path.iterdir()):
                    if not cmd_delete(str(dir_path), is_directory=True):
                        logger.info(f"❌ 删除空文件夹失败 {dir_path}")
                    else:
                        logger.info(f"🗑️ 已删除空文件夹: {dir_path}")
            except Exception as e:
                logger.info(f"❌ 检查空文件夹失败 {dir_path}: {e}") 