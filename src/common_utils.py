"""
通用工具模块

包含文件类型管理、扩展名配置和统计结果格式化等共用功能
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Optional, Union

logger = logging.getLogger(__name__)

# 文件类型和扩展名映射
DEFAULT_FILE_TYPES = {
    "text": {".txt", ".md", ".log", ".ini", ".cfg", ".conf", ".json", ".xml", ".yml", ".yaml", ".csv", ".convert"},
    "image": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".svg", ".ico", ".raw", ".jxl", ".avif", ".psd"},
    "video": {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg", ".nov"},
    "audio": {".mp3", ".wav", ".ogg", ".flac", ".aac", ".wma", ".m4a", ".opus"},
    "document": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp"},
    "archive": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso", ".cbz", ".cbr"},
    "code": {".py", ".js", ".html", ".css", ".java", ".c", ".cpp", ".cs", ".php", ".go", ".rs", ".rb", ".ts"},
    "font": {".ttf", ".otf", ".woff", ".woff2", ".eot"},
    "executable": {".exe", ".dll", ".bat", ".sh", ".msi", ".app", ".apk"},
    "model": {".pth", ".h5", ".pb", ".onnx", ".tflite", ".mlmodel", ".pt", ".bin", ".caffemodel"}
}

# 黑名单关键词列表，用于跳过某些文件夹
BLACKLIST_KEYWORDS = [
    "node_modules", "__pycache__", ".git", ".svn", "tmp", "temp", 
    "cache", "logs", ".vscode", ".idea", ".vs", "画集", ".vs"
]

# 定义压缩模式常量
COMPRESS_MODE_ENTIRE = "entire"  # 压缩整个文件夹
COMPRESS_MODE_SELECTIVE = "selective"  # 选择性压缩文件
COMPRESS_MODE_SKIP = "skip"  # 跳过不处理

# 文件工具函数
def safe_path(path: Path) -> str:
    """
    安全处理路径字符串，避免UNC路径问题
    
    Args:
        path: 路径对象
    
    Returns:
        str: 安全的路径字符串
    """
    return str(path)

def is_blacklisted_path(path: Path) -> bool:
    """
    检查路径是否在黑名单中
    
    Args:
        path: 要检查的路径
    
    Returns:
        bool: 如果路径包含黑名单关键词则返回True
    """
    path_str = str(path).lower()
    return any(keyword.lower() in path_str for keyword in BLACKLIST_KEYWORDS)

def get_folder_size(folder_path: Path) -> int:
    """
    获取文件夹总大小（字节）
    
    Args:
        folder_path: 文件夹路径
    
    Returns:
        int: 文件夹总大小（字节）
    """
    total_size = 0
    try:
        for dirpath, _, filenames in os.walk(folder_path):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                if os.path.isfile(file_path) and not os.path.islink(file_path):
                    total_size += os.path.getsize(file_path)
    except Exception as e:
        logger.error(f"计算文件夹大小时出错: {folder_path}, {str(e)}")
    return total_size

def compare_zip_contents(source_folder: Path, zip_file: Path) -> bool:
    """
    比较源文件夹与压缩文件内容是否一致（简化版）
    
    Args:
        source_folder: 源文件夹路径
        zip_file: 压缩文件路径
    
    Returns:
        bool: 如果压缩包存在且大小不为0则返回True
    """
    # 简单确认压缩包存在且大小不为0
    return zip_file.exists() and zip_file.stat().st_size > 0

def create_directory(path: Path) -> bool:
    """
    创建目录，如果目录已存在则不做任何操作
    
    Args:
        path: 要创建的目录路径
    
    Returns:
        bool: 操作是否成功
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"创建目录失败: {path}, {str(e)}")
        return False

def ensure_file_extension(file_path: Path, extension: str) -> Path:
    """
    确保文件有正确的扩展名
    
    Args:
        file_path: 文件路径
        extension: 期望的扩展名（如".zip"）
    
    Returns:
        Path: 带有正确扩展名的文件路径
    """
    if not extension.startswith('.'):
        extension = '.' + extension
        
    if file_path.suffix.lower() != extension.lower():
        return file_path.with_suffix(extension)
    return file_path

# 文件类型管理器
class FileTypeManager:
    """文件类型管理器，负责识别和判断文件类型"""
    
    def __init__(self, custom_file_types: Dict[str, Set[str]] = None):
        """
        初始化文件类型管理器
        
        Args:
            custom_file_types: 可选的自定义文件类型映射
        """
        self.file_types = DEFAULT_FILE_TYPES.copy()
        
        # 合并自定义文件类型
        if custom_file_types:
            for type_name, extensions in custom_file_types.items():
                if type_name in self.file_types:
                    # 合并已有类型的扩展名
                    self.file_types[type_name].update(extensions)
                else:
                    # 添加新类型
                    self.file_types[type_name] = set(extensions)
    
    def get_file_type(self, file_path: Path) -> Optional[str]:
        """
        获取文件的类型，仅基于文件扩展名
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: 文件类型，如果无法识别则返回None
        """
        if not isinstance(file_path, Path):
            file_path = Path(file_path)
        
        # 通过扩展名匹配
        ext = file_path.suffix.lower()
        for type_name, extensions in self.file_types.items():
            if ext in extensions:
                return type_name
        
        # 尝试通过文件名推断
        filename = file_path.name.lower()
        if any(keyword in filename for keyword in ["readme", "license", "changelog"]):
            return "text"
        
        # 无法识别
        return None
    
    def is_file_in_types(self, file_path: Path, target_types: List[str]) -> bool:
        """
        判断文件是否属于指定的类型列表
        
        Args:
            file_path: 文件路径
            target_types: 目标类型列表
            
        Returns:
            bool: 文件是否属于目标类型
        """
        if not target_types:
            return True  # 如果没有指定类型，默认返回True
        
        file_type = self.get_file_type(file_path)
        
        # 如果文件类型无法识别，使用扩展名
        if file_type is None:
            ext = file_path.suffix.lower()
            # 检查扩展名是否在任何目标类型中
            for type_name in target_types:
                if type_name in self.file_types and ext in self.file_types[type_name]:
                    return True
            return False
        
        return file_type in target_types
    
    def get_all_file_types(self) -> List[str]:
        """获取所有支持的文件类型名称列表"""
        return list(self.file_types.keys())
    
    def get_extensions_for_type(self, type_name: str) -> List[str]:
        """
        获取指定类型的所有文件扩展名
        
        Args:
            type_name: 类型名称
            
        Returns:
            List[str]: 扩展名列表
        """
        if type_name in self.file_types:
            return list(self.file_types[type_name])
        return []

# 简便的工具函数
def get_file_type(file_path: Path) -> Optional[str]:
    """
    获取文件的类型（使用默认管理器的便捷函数）
    
    Args:
        file_path: 文件路径
        
    Returns:
        str: 文件类型，如果无法识别则返回None
    """
    manager = FileTypeManager()
    return manager.get_file_type(file_path)

def is_file_in_types(file_path: Path, target_types: List[str]) -> bool:
    """
    判断文件是否属于指定的类型列表（使用默认管理器的便捷函数）
    
    Args:
        file_path: 文件路径
        target_types: 目标类型列表
        
    Returns:
        bool: 文件是否属于目标类型
    """
    manager = FileTypeManager()
    return manager.is_file_in_types(file_path, target_types)

def try_extended_media_match(file_paths: List[Path], file_type_manager: FileTypeManager = None) -> bool:
    """
    尝试使用扩展的媒体类型(图片+文档+文本)匹配所有文件

    当图片格式不能完全匹配所有文件时，尝试使用扩展媒体类型进行匹配。
    这个函数用于在压缩模式判断时，让包含图片+文档+文本的文件夹能够被整体压缩。
    必须至少包含一张图片，否则返回False。

    Args:
        file_paths: 要匹配的文件路径列表
        file_type_manager: 文件类型管理器，如果为None则创建新实例

    Returns:
        bool: 如果所有文件都能被图片+文档+文本类型匹配上且至少包含一张图片，返回True
    """
    if not file_paths:
        return False
        
    if file_type_manager is None:
        file_type_manager = FileTypeManager()
    
    # 扩展的媒体类型列表
    extended_media_types = ["image", "document", "text"]
    
    # 用于追踪是否找到至少一张图片
    has_image = False
    
    # 检查所有文件是否都属于扩展媒体类型
    for file_path in file_paths:
        if not file_path.is_file():
            continue
            
        file_type = file_type_manager.get_file_type(file_path)
        
        # 检查是否为图片类型
        if file_type == "image":
            has_image = True
            
        if file_type not in extended_media_types:
            # 发现一个不属于扩展媒体类型的文件，返回False
            return False
    
    # 所有文件都匹配了扩展媒体类型，且至少有一张图片
    return has_image

# 统计结果类
class CompressionResult:
    """压缩结果类"""
    
    def __init__(self, success: bool, original_size: int = 0, compressed_size: int = 0, error_message: str = ""):
        self.success = success
        self.original_size = original_size
        self.compressed_size = compressed_size
        self.error_message = error_message
        
    def get_compression_ratio(self) -> float:
        """获取压缩比例"""
        if self.original_size == 0:
            return 0
        return (self.compressed_size / self.original_size) * 100
    
    def __str__(self) -> str:
        if self.success:
            ratio = self.get_compression_ratio()
            return f"压缩成功: 原始大小={self.original_size/1024/1024:.2f}MB, " \
                   f"压缩后大小={self.compressed_size/1024/1024:.2f}MB, 压缩率={ratio:.1f}%"
        else:
            return f"压缩失败: {self.error_message}"

class CompressionStats:
    """压缩统计信息类"""
    
    def __init__(self):
        self.successful_compressions = 0
        self.failed_compressions = 0
        self.total_original_size = 0
        self.total_compressed_size = 0
    
    def add_result(self, result: CompressionResult):
        """添加一个压缩结果到统计信息中"""
        if result.success:
            self.successful_compressions += 1
            self.total_original_size += result.original_size
            self.total_compressed_size += result.compressed_size
        else:
            self.failed_compressions += 1
    
    def get_summary(self) -> str:
        """获取统计摘要"""
        total_compressions = self.successful_compressions + self.failed_compressions
        if total_compressions == 0:
            return "没有进行任何压缩操作"
        
        success_rate = (self.successful_compressions / total_compressions) * 100
        if self.total_original_size > 0:
            compression_ratio = (self.total_compressed_size / self.total_original_size) * 100
        else:
            compression_ratio = 0
        
        return (f"总计: {total_compressions}个文件夹, 成功: {self.successful_compressions}, "
                f"失败: {self.failed_compressions}, 成功率: {success_rate:.1f}%\n"
                f"总原始大小: {self.total_original_size/1024/1024:.2f}MB, "
                f"总压缩后大小: {self.total_compressed_size/1024/1024:.2f}MB, "
                f"总体压缩率: {compression_ratio:.1f}%")