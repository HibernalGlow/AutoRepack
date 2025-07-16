#!/usr/bin/env python3
"""
pytest 测试文件
测试 compress_entire_folder 函数的核心功能
"""

import pytest
import tempfile
import shutil
import zipfile
from pathlib import Path
import sys

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from autorepack.core.zip_compressor import ZipCompressor


@pytest.fixture
def test_folder():
    """
    创建测试文件夹的 fixture
    """
    # 创建临时目录
    temp_dir = Path(tempfile.mkdtemp(prefix="pytest_compress_"))
    
    # 创建测试文件夹
    test_folder = temp_dir / "TestFolder"
    test_folder.mkdir()
    
    # 创建子文件夹和文件
    (test_folder / "subfolder1").mkdir()
    (test_folder / "subfolder2").mkdir()
    
    # 创建测试文件
    (test_folder / "file1.txt").write_text("Test content 1 " * 100, encoding='utf-8')  # 增加文件大小
    (test_folder / "file2.txt").write_text("Test content 2 " * 100, encoding='utf-8')  # 增加文件大小
    (test_folder / "subfolder1" / "subfile1.txt").write_text("Subfile 1 " * 50, encoding='utf-8')  # 增加文件大小
    (test_folder / "subfolder2" / "subfile2.txt").write_text("Subfile 2 " * 50, encoding='utf-8')  # 增加文件大小
    
    yield test_folder
    
    # 清理
    shutil.rmtree(temp_dir)


@pytest.fixture
def compressor():
    """
    创建压缩器实例的 fixture
    """
    return ZipCompressor(compression_level=5)


def test_compress_with_folder_structure(test_folder, compressor):
    """
    测试保留文件夹结构的压缩
    """
    zip_path = test_folder.parent / f"{test_folder.name}_with_structure.zip"
    
    # 执行压缩
    result = compressor.compress_entire_folder(
        folder_path=test_folder,
        target_zip=zip_path,
        delete_source=False,
        keep_folder_structure=True
    )
    
    # 验证结果
    assert result.success, f"压缩失败: {result.error_message}"
    assert zip_path.exists(), "压缩包文件不存在"
    assert result.original_size > 0, "原始大小应该大于0"
    assert result.compressed_size > 0, "压缩后大小应该大于0"
    
    # 验证压缩包内容
    with zipfile.ZipFile(zip_path, 'r') as zf:
        files = zf.namelist()
        
        # 检查是否包含文件夹结构
        folder_prefix = f"{test_folder.name}/"
        has_folder_structure = any(f.startswith(folder_prefix) for f in files)
        assert has_folder_structure, "应该保留文件夹结构"
        
        # 检查关键文件是否存在
        expected_files = [
            f"{test_folder.name}/file1.txt",
            f"{test_folder.name}/file2.txt",
            f"{test_folder.name}/subfolder1/subfile1.txt",
            f"{test_folder.name}/subfolder2/subfile2.txt"
        ]
        
        for expected_file in expected_files:
            assert expected_file in files, f"缺少文件: {expected_file}"


def test_compress_without_folder_structure(test_folder, compressor):
    """
    测试不保留文件夹结构的压缩
    """
    zip_path = test_folder.parent / f"{test_folder.name}_without_structure.zip"
    
    # 执行压缩
    result = compressor.compress_entire_folder(
        folder_path=test_folder,
        target_zip=zip_path,
        delete_source=False,
        keep_folder_structure=False
    )
    
    # 验证结果
    assert result.success, f"压缩失败: {result.error_message}"
    assert zip_path.exists(), "压缩包文件不存在"
    assert result.original_size > 0, "原始大小应该大于0"
    assert result.compressed_size > 0, "压缩后大小应该大于0"
    
    # 验证压缩包内容
    with zipfile.ZipFile(zip_path, 'r') as zf:
        files = zf.namelist()
        
        # 检查不应该包含外层文件夹结构
        folder_prefix = f"{test_folder.name}/"
        has_folder_structure = any(f.startswith(folder_prefix) for f in files)
        assert not has_folder_structure, "不应该包含外层文件夹结构"
        
        # 检查关键文件是否存在（不带文件夹前缀）
        expected_files = [
            "file1.txt",
            "file2.txt",
            "subfolder1/subfile1.txt",
            "subfolder2/subfile2.txt"
        ]
        
        for expected_file in expected_files:
            assert expected_file in files, f"缺少文件: {expected_file}"


def test_compression_ratio(test_folder, compressor):
    """
    测试压缩率是否合理
    """
    zip_path = test_folder.parent / f"{test_folder.name}_ratio_test.zip"
    
    result = compressor.compress_entire_folder(
        folder_path=test_folder,
        target_zip=zip_path,
        delete_source=False,
        keep_folder_structure=True
    )
    
    assert result.success, "压缩应该成功"
    
    # 压缩率应该在合理范围内
    compression_ratio = result.compressed_size / result.original_size
    assert 0.1 < compression_ratio < 1.0, f"压缩率异常: {compression_ratio}"


def test_invalid_folder_path(compressor):
    """
    测试无效文件夹路径的处理
    """
    invalid_path = Path("/nonexistent/folder")
    zip_path = Path("/tmp/test.zip")
    
    result = compressor.compress_entire_folder(
        folder_path=invalid_path,
        target_zip=zip_path,
        delete_source=False,
        keep_folder_structure=True
    )
    
    assert not result.success, "对于无效路径应该返回失败"
    # 兼容中英文系统的错误信息
    error_msg = result.error_message.lower()
    assert any(keyword in error_msg for keyword in ["不存在", "not exist", "找不到", "cannot find", "no such"]), f"错误信息不符合预期: {result.error_message}"


def test_both_modes_same_content(test_folder, compressor):
    """
    测试两种模式压缩的文件内容是否一致
    """
    zip_with = test_folder.parent / f"{test_folder.name}_with.zip"
    zip_without = test_folder.parent / f"{test_folder.name}_without.zip"
    
    # 执行两种压缩
    result1 = compressor.compress_entire_folder(
        test_folder, zip_with, False, True
    )
    result2 = compressor.compress_entire_folder(
        test_folder, zip_without, False, False
    )
    
    assert result1.success and result2.success, "两种压缩都应该成功"
    
    # 验证内容一致性
    with zipfile.ZipFile(zip_with, 'r') as zf1, zipfile.ZipFile(zip_without, 'r') as zf2:
        files1 = zf1.namelist()
        files2 = zf2.namelist()
        
        # 移除路径前缀后，文件列表应该相同
        folder_name = test_folder.name
        normalized_files1 = [f.replace(f"{folder_name}/", "") for f in files1 if not f.endswith('/')]
        normalized_files2 = [f for f in files2 if not f.endswith('/')]
        
        assert set(normalized_files1) == set(normalized_files2), "两种模式的文件内容应该一致"


if __name__ == "__main__":
    # 直接运行测试
    pytest.main([__file__, "-v"])
