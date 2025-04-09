"""
配置模块 - 包含所有程序配置
"""
from pathlib import Path

# 基础配置
SEVEN_ZIP_PATH = "C:\\Program Files\\7-Zip\\7z.exe"
COMPRESSION_LEVEL = 5  # 1-9, 9为最高压缩率
MAX_WORKERS = 4  # 并行处理的最大工作线程数

# 日志面板布局
TEXTUAL_LAYOUT = {
    "cur_stats": {
        "ratio": 2,
        "title": "📊 总体进度",
        "style": "lightyellow"
    },
    "cur_progress": {
        "ratio": 2,
        "title": "🔄 当前进度",
        "style": "lightcyan"
    },
    "file_ops": {
        "ratio": 3,
        "title": "📂 文件操作",
        "style": "lightpink"
    },
    "process": {
        "ratio": 3,
        "title": "📝 处理日志",
        "style": "lightblue"
    }
}

# 日志配置
LOG_CONFIG = {
    'script_name': 'comic_auto_repack',
    'console_enabled': False
} 