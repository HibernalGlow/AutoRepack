"""
常量定义 - 包含程序中使用的各种常量
"""

# 默认设置
DEFAULT_OPTIONS = {
    "organize_media": True,
    "move_unwanted": True,
    "compress": True,
    "process_scattered": True,
    "images_only": False
}

# 工具描述
TOOL_DESCRIPTION = "文件批量管理和压缩工具"

# 预设配置
PRESET_CONFIGS = {
    "全部处理": {
        "description": "执行所有操作",
        "checkbox_options": ["clipboard", "organize_media", "move_unwanted", "compress", "process_scattered"],
        "input_values": {}
    },
    "仅整理": {
        "description": "只整理媒体文件和不需要的文件",
        "checkbox_options": ["clipboard", "organize_media", "move_unwanted"],
        "input_values": {}
    },
    "仅压缩": {
        "description": "只压缩文件夹和处理散图",
        "checkbox_options": ["clipboard", "compress", "process_scattered"],
        "input_values": {}
    },
    "只压缩图片": {
        "description": "只压缩图片文件，保留文件夹和其他文件",
        "checkbox_options": ["clipboard", "images_only"],
        "input_values": {}
    }
}

# 复选框选项
CHECKBOX_OPTIONS = [
    ("从剪贴板读取路径", "clipboard", "--clipboard", True),
    ("整理媒体文件", "organize_media", "--organize-media", True),
    ("移动不需要文件", "move_unwanted", "--move-unwanted", True),
    ("压缩文件夹", "compress", "--compress", True),
    ("处理散图", "process_scattered", "--process-scattered", True),
    ("只压缩图片文件", "images_only", "--images-only", False),
    ("执行所有操作", "all", "--all", False),
]

# 输入框选项
INPUT_OPTIONS = [
    ("待处理路径", "path", "--path", "", "输入待处理文件夹路径"),
] 