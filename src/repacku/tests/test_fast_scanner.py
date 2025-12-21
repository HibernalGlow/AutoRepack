#!/usr/bin/env python
"""
快速扫描器单元测试
"""

import os
import tempfile
from pathlib import Path
import pytest

from repacku.core.fast_scanner import (
    FastScanner, 
    FastFolderAnalyzer,
    fast_get_file_type,
    fast_scan_folder,
    ScanResult,
    _EXT_TO_TYPE_CACHE
)
from repacku.core.common_utils import COMPRESS_MODE_ENTIRE, COMPRESS_MODE_SELECTIVE, COMPRESS_MODE_SKIP


class TestFastGetFileType:
    """测试快速文件类型查找"""
    
    def test_image_extensions(self):
        """测试图片扩展名识别"""
        assert fast_get_file_type('.jpg') == 'image'
        assert fast_get_file_type('.jpeg') == 'image'
        assert fast_get_file_type('.png') == 'image'
        assert fast_get_file_type('.webp') == 'image'
        assert fast_get_file_type('.avif') == 'image'
    
    def test_video_extensions(self):
        """测试视频扩展名识别"""
        assert fast_get_file_type('.mp4') == 'video'
        assert fast_get_file_type('.mkv') == 'video'
        assert fast_get_file_type('.avi') == 'video'
    
    def test_archive_extensions(self):
        """测试压缩包扩展名识别"""
        assert fast_get_file_type('.zip') == 'archive'
        assert fast_get_file_type('.rar') == 'archive'
        assert fast_get_file_type('.7z') == 'archive'
    
    def test_unknown_extension(self):
        """测试未知扩展名"""
        assert fast_get_file_type('.xyz123') is None
        assert fast_get_file_type('.unknown') is None
    
    def test_case_insensitive(self):
        """测试大小写不敏感"""
        assert fast_get_file_type('.JPG') == 'image'
        assert fast_get_file_type('.Png') == 'image'
        assert fast_get_file_type('.MP4') == 'video'


class TestExtCache:
    """测试扩展名缓存"""
    
    def test_cache_populated(self):
        """测试缓存已填充"""
        assert len(_EXT_TO_TYPE_CACHE) > 0
    
    def test_cache_contains_common_types(self):
        """测试缓存包含常见类型"""
        assert '.jpg' in _EXT_TO_TYPE_CACHE
        assert '.mp4' in _EXT_TO_TYPE_CACHE
        assert '.zip' in _EXT_TO_TYPE_CACHE
        assert '.py' in _EXT_TO_TYPE_CACHE


class TestFastScanner:
    """测试 FastScanner 类"""
    
    @pytest.fixture
    def scanner(self):
        return FastScanner(max_workers=4)
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时测试目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建测试文件结构
            root = Path(tmpdir)
            
            # 创建图片文件
            (root / "image1.jpg").touch()
            (root / "image2.png").touch()
            
            # 创建子目录
            subdir = root / "subdir"
            subdir.mkdir()
            (subdir / "video.mp4").touch()
            (subdir / "doc.pdf").touch()
            
            # 创建嵌套子目录
            nested = subdir / "nested"
            nested.mkdir()
            (nested / "archive.zip").touch()
            
            yield root
    
    def test_scan_single_folder(self, scanner, temp_dir):
        """测试单文件夹扫描"""
        result = scanner.scan_single_folder(temp_dir)
        
        assert result.path == str(temp_dir)
        assert result.total_files == 2  # image1.jpg, image2.png
        assert 'image' in result.file_types
        assert result.file_types['image'] == 2
        assert len(result.subdirs) == 1  # subdir
    
    def test_scan_single_folder_with_extensions(self, scanner, temp_dir):
        """测试扫描结果包含扩展名统计"""
        result = scanner.scan_single_folder(temp_dir)
        
        assert '.jpg' in result.file_extensions
        assert '.png' in result.file_extensions
    
    def test_scan_tree_parallel(self, scanner, temp_dir):
        """测试并行树扫描"""
        results = scanner.scan_tree_parallel(temp_dir, show_progress=False)
        
        # 应该扫描到 3 个目录
        assert len(results) == 3
        assert str(temp_dir) in results
        assert str(temp_dir / "subdir") in results
        assert str(temp_dir / "subdir" / "nested") in results
    
    def test_blacklist_filtering(self, scanner):
        """测试黑名单过滤"""
        assert scanner._is_blacklisted_name("node_modules")
        assert scanner._is_blacklisted_name("__pycache__")
        assert scanner._is_blacklisted_name(".git")
        assert not scanner._is_blacklisted_name("normal_folder")


class TestFastFolderAnalyzer:
    """测试 FastFolderAnalyzer 类"""
    
    @pytest.fixture
    def analyzer(self):
        return FastFolderAnalyzer(max_workers=4)
    
    @pytest.fixture
    def temp_dir_images(self):
        """创建只包含图片的临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "a.jpg").touch()
            (root / "b.png").touch()
            (root / "c.webp").touch()
            yield root
    
    @pytest.fixture
    def temp_dir_mixed(self):
        """创建混合文件的临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "image.jpg").touch()
            (root / "video.mp4").touch()
            (root / "doc.pdf").touch()
            yield root
    
    @pytest.fixture
    def temp_dir_with_archive(self):
        """创建包含压缩包的临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "image.jpg").touch()
            (root / "archive.zip").touch()
            yield root
    
    def test_analyze_images_only(self, analyzer, temp_dir_images):
        """测试纯图片目录分析"""
        result = analyzer.analyze_folder_tree_fast(temp_dir_images, ['image'], show_progress=False)
        
        assert result['total_files'] == 3
        assert result['file_types']['image'] == 3
        assert result['compress_mode'] == COMPRESS_MODE_ENTIRE
    
    def test_analyze_mixed_with_target(self, analyzer, temp_dir_mixed):
        """测试混合目录指定目标类型"""
        result = analyzer.analyze_folder_tree_fast(temp_dir_mixed, ['image'], show_progress=False)
        
        # 只有 1 个图片，不满足最小数量要求
        assert result['compress_mode'] == COMPRESS_MODE_SKIP
    
    def test_analyze_with_archive(self, analyzer, temp_dir_with_archive):
        """测试包含压缩包的目录"""
        result = analyzer.analyze_folder_tree_fast(temp_dir_with_archive, ['image'], show_progress=False)
        
        # 有压缩包时应该跳过或选择性压缩
        assert result['compress_mode'] in [COMPRESS_MODE_SKIP, COMPRESS_MODE_SELECTIVE]


class TestFastScanFolder:
    """测试便捷函数"""
    
    def test_fast_scan_folder(self):
        """测试 fast_scan_folder 函数"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "test.jpg").touch()
            (root / "test.png").touch()
            
            result = fast_scan_folder(root, show_progress=False)
            
            assert 'path' in result
            assert 'total_files' in result
            assert result['total_files'] == 2


class TestScanResult:
    """测试 ScanResult 数据类"""
    
    def test_default_values(self):
        """测试默认值"""
        result = ScanResult(path="/test", name="test", depth=1)
        
        assert result.files == []
        assert result.subdirs == []
        assert result.file_types == {}
        assert result.total_files == 0
        assert result.total_size == 0
    
    def test_with_data(self):
        """测试带数据的结果"""
        result = ScanResult(
            path="/test",
            name="test",
            depth=1,
            files=[("a.jpg", ".jpg", 100)],
            file_types={"image": 1},
            total_files=1,
            total_size=100
        )
        
        assert len(result.files) == 1
        assert result.file_types["image"] == 1
