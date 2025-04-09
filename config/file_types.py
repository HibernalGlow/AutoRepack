"""
文件类型定义 - 包含各种文件类型的扩展名集合
"""
from typing import Set, Dict

# 不需要压缩的文件类型
UNWANTED_EXTENSIONS: Set[str] = {
    '.url', '.txt', '.tsd', '.db', '.js', '.htm', '.html', '.docx', '.psd', '.pdf', 
    '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.nov', '.rmvb', 
    '.mp3', '.mp4', '.wav', '.flac', '.m4a', '.ogg', '.aac', '.wma', '.opus', '.ape', '.alac',
    '.psd', '.ai', '.cdr', '.eps', '.svg', '.raw', '.cr2', '.nef', '.arw', '.dng', '.tif', '.tiff'
}

# 在仅图片模式下允许与图片一起保留的文件类型（仅文本类格式）
ALLOW_REPACK_EXTENSIONS: Set[str] = {
    '.txt', '.md', '.json', '.xml', '.yaml', '.yml', '.ini', '.cfg', '.conf', '.log', '.css', '.js', '.html', '.htm'
}

# 黑名单关键词
BLACKLIST_KEYWORDS = ['_temp', '画集', '00去图', '00不需要', '[00不需要]', '动画']

# 媒体文件类型
MEDIA_TYPES = {
    '[00不需要]': {
        'extensions': ['.url', '.txt', '.tsd', '.db', '.js', '.htm', '.html', '.docx'],
        'associated_extensions': []  # 关联的字幕和图片文件
    },
    '[01视频]': {
        'extensions': ['.mp4', '.avi', '.webm', '.rmvb', '.mov', '.mkv','.flv','.wmv', '.nov'],
        'associated_extensions': ['.ass', '.srt', '.ssa', '.jxl', '.avif', '.jpg', '.jpeg', '.png', '.webp']  # 关联的字幕和图片文件
    },
    '[04cbz]': {
        'extensions': ['.cbz'],
        'associated_extensions': []
    }
}

# 定义图像文件扩展名集合
IMAGE_EXTENSIONS: Set[str] = {
    '.webp', '.avif', '.jxl', '.jpg', '.jpeg',
    '.png', '.gif', '.yaml', '.log', '.bmp'
} 