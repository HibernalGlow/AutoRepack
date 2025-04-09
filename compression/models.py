"""
压缩模块的数据模型 - 定义压缩结果和统计类
"""
from dataclasses import dataclass

@dataclass
class CompressionResult:
    """
    表示单次压缩操作的结果
    """
    success: bool
    original_size: int = 0
    compressed_size: int = 0
    error_message: str = ""

@dataclass
class CompressionStats:
    """
    表示压缩统计信息的类
    """
    total_original_size: int = 0
    total_compressed_size: int = 0
    successful_compressions: int = 0
    failed_compressions: int = 0
    
    @property
    def total_space_saved(self) -> int:
        """
        计算节省的总空间大小
        """
        return self.total_original_size - self.total_compressed_size
    
    @property
    def compression_ratio(self) -> float:
        """
        计算压缩率（压缩后大小/原始大小）
        """
        if self.total_original_size == 0:
            return 0
        return (self.total_compressed_size / self.total_original_size) * 100
    
    def format_size(self, size_in_bytes: int) -> str:
        """
        将字节大小格式化为人类可读的字符串
        """
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_in_bytes < 1024:
                return f"{size_in_bytes:.2f} {unit}"
            size_in_bytes /= 1024
        return f"{size_in_bytes:.2f} TB"
    
    def get_summary(self) -> str:
        """
        获取统计摘要信息
        """
        return (
            f"\n压缩统计摘要:\n"
            f"总处理文件夹数: {self.successful_compressions + self.failed_compressions}\n"
            f"成功压缩: {self.successful_compressions}\n"
            f"失败数量: {self.failed_compressions}\n"
            f"原始总大小: {self.format_size(self.total_original_size)}\n"
            f"压缩后总大小: {self.format_size(self.total_compressed_size)}\n"
            f"节省空间: {self.format_size(self.total_space_saved)}\n"
            f"平均压缩率: {self.compression_ratio:.1f}%"
        ) 