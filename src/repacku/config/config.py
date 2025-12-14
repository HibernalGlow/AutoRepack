
"""
配置相关工具函数：统一从 compression_config.json 读取配置
"""
import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent / "compression_config.json"

def get_config():
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def get_compression_level():
    cfg = get_config()
    return cfg.get("compression", {}).get("level", 5)

def get_file_types():
    cfg = get_config()
    return cfg.get("file_types", {})

def get_special_rules():
    cfg = get_config()
    return cfg.get("special_rules", {})

def get_single_image_compress_rule():
    rules = get_special_rules()
    return rules.get("image_processing", {}).get("single_image_compress", False)
