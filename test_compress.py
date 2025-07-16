#!/usr/bin/env python3
"""
测试 compress_entire_folder 函数
验证保留和不保留文件夹结构的功能
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# 添加项目路径到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from autorepack.core.zip_compressor import ZipCompressor
from rich.console import Console

console = Console()


def create_test_folder() -> Path:
    """
    创建测试文件夹结构
    """
    # 创建临时目录
    temp_dir = Path(tempfile.mkdtemp(prefix="compress_test_"))
    
    # 创建测试文件夹
    test_folder = temp_dir / "TestFolder"
    test_folder.mkdir()
    
    # 创建子文件夹和文件
    (test_folder / "subfolder1").mkdir()
    (test_folder / "subfolder2").mkdir()
    
    # 创建测试文件
    (test_folder / "file1.txt").write_text("这是测试文件1的内容", encoding='utf-8')
    (test_folder / "file2.txt").write_text("这是测试文件2的内容", encoding='utf-8')
    (test_folder / "subfolder1" / "subfile1.txt").write_text("子文件夹1中的文件", encoding='utf-8')
    (test_folder / "subfolder2" / "subfile2.txt").write_text("子文件夹2中的文件", encoding='utf-8')
    (test_folder / "subfolder1" / "image.jpg").write_bytes(b"fake image data")
    
    console.print(f"[green]✓ 创建测试文件夹:[/] {test_folder}")
    return test_folder


def test_compress_with_folder_structure():
    """
    测试保留文件夹结构的压缩
    """
    console.print("\n[bold blue]测试1: 保留文件夹结构[/bold blue]")
    
    # 创建测试文件夹
    test_folder = create_test_folder()
    
    try:
        # 创建压缩器
        compressor = ZipCompressor(compression_level=5)
        
        # 压缩包路径
        zip_path = test_folder.parent / f"{test_folder.name}_with_structure.zip"
        
        # 执行压缩（保留文件夹结构）
        result = compressor.compress_entire_folder(
            folder_path=test_folder,
            target_zip=zip_path,
            delete_source=False,
            keep_folder_structure=True
        )
        
        # 检查结果
        if result.success:
            console.print(f"[green]✓ 压缩成功:[/] {zip_path.name}")
            console.print(f"  • 原始大小: {result.original_size/1024:.1f}KB")
            console.print(f"  • 压缩后大小: {result.compressed_size/1024:.1f}KB")
            
            # 验证压缩包内容
            import zipfile
            with zipfile.ZipFile(zip_path, 'r') as zf:
                files = zf.namelist()
                console.print(f"  • 压缩包内容 ({len(files)} 个条目):")
                for file in sorted(files):
                    console.print(f"    - {file}")
                    
                # 检查是否包含文件夹名
                has_folder_structure = any(f.startswith(f"{test_folder.name}/") for f in files)
                if has_folder_structure:
                    console.print(f"  • [green]✓ 正确保留了文件夹结构[/]")
                else:
                    console.print(f"  • [red]✗ 未保留文件夹结构[/]")
        else:
            console.print(f"[red]✗ 压缩失败:[/] {result.error_message}")
            
    finally:
        # 清理测试文件
        shutil.rmtree(test_folder.parent)


def test_compress_without_folder_structure():
    """
    测试不保留文件夹结构的压缩
    """
    console.print("\n[bold blue]测试2: 不保留文件夹结构[/bold blue]")
    
    # 创建测试文件夹
    test_folder = create_test_folder()
    
    try:
        # 创建压缩器
        compressor = ZipCompressor(compression_level=5)
        
        # 压缩包路径
        zip_path = test_folder.parent / f"{test_folder.name}_without_structure.zip"
        
        # 执行压缩（不保留文件夹结构）
        result = compressor.compress_entire_folder(
            folder_path=test_folder,
            target_zip=zip_path,
            delete_source=False,
            keep_folder_structure=False
        )
        
        # 检查结果
        if result.success:
            console.print(f"[green]✓ 压缩成功:[/] {zip_path.name}")
            console.print(f"  • 原始大小: {result.original_size/1024:.1f}KB")
            console.print(f"  • 压缩后大小: {result.compressed_size/1024:.1f}KB")
            
            # 验证压缩包内容
            import zipfile
            with zipfile.ZipFile(zip_path, 'r') as zf:
                files = zf.namelist()
                console.print(f"  • 压缩包内容 ({len(files)} 个条目):")
                for file in sorted(files):
                    console.print(f"    - {file}")
                    
                # 检查是否不包含外层文件夹名
                has_folder_structure = any(f.startswith(f"{test_folder.name}/") for f in files)
                if not has_folder_structure:
                    console.print(f"  • [green]✓ 正确移除了外层文件夹结构[/]")
                else:
                    console.print(f"  • [red]✗ 仍然包含外层文件夹结构[/]")
        else:
            console.print(f"[red]✗ 压缩失败:[/] {result.error_message}")
            
    finally:
        # 清理测试文件
        shutil.rmtree(test_folder.parent)


def test_compare_structures():
    """
    对比两种压缩方式的差异
    """
    console.print("\n[bold blue]测试3: 对比两种压缩方式[/bold blue]")
    
    # 创建测试文件夹
    test_folder = create_test_folder()
    
    try:
        # 创建压缩器
        compressor = ZipCompressor(compression_level=5)
        
        # 两个压缩包路径
        zip_with_structure = test_folder.parent / f"{test_folder.name}_with.zip"
        zip_without_structure = test_folder.parent / f"{test_folder.name}_without.zip"
        
        # 执行两种压缩
        result1 = compressor.compress_entire_folder(
            test_folder, zip_with_structure, False, True
        )
        
        result2 = compressor.compress_entire_folder(
            test_folder, zip_without_structure, False, False
        )
        
        if result1.success and result2.success:
            import zipfile
            
            console.print("\n[bold yellow]对比结果:[/bold yellow]")
            
            # 对比文件内容
            with zipfile.ZipFile(zip_with_structure, 'r') as zf1:
                files1 = set(zf1.namelist())
            
            with zipfile.ZipFile(zip_without_structure, 'r') as zf2:
                files2 = set(zf2.namelist())
            
            console.print(f"保留结构的压缩包文件数: [cyan]{len(files1)}[/]")
            console.print(f"不保留结构的压缩包文件数: [cyan]{len(files2)}[/]")
            
            console.print("\n[bold]保留结构的文件列表:[/]")
            for f in sorted(files1):
                console.print(f"  - [green]{f}[/]")
            
            console.print("\n[bold]不保留结构的文件列表:[/]")
            for f in sorted(files2):
                console.print(f"  - [blue]{f}[/]")
                
            # 检查预期差异
            folder_prefix = f"{test_folder.name}/"
            has_prefix_in_1 = any(f.startswith(folder_prefix) for f in files1)
            has_prefix_in_2 = any(f.startswith(folder_prefix) for f in files2)
            
            console.print(f"\n[bold]验证结果:[/]")
            console.print(f"保留结构包含文件夹前缀: [{'green' if has_prefix_in_1 else 'red'}]{has_prefix_in_1}[/]")
            console.print(f"不保留结构包含文件夹前缀: [{'red' if has_prefix_in_2 else 'green'}]{not has_prefix_in_2}[/]")
            
            if has_prefix_in_1 and not has_prefix_in_2:
                console.print("[bold green]✓ 测试通过: 两种模式工作正常![/]")
            else:
                console.print("[bold red]✗ 测试失败: 压缩模式未按预期工作![/]")
        
    finally:
        # 清理测试文件
        shutil.rmtree(test_folder.parent)


def main():
    """
    运行所有测试
    """
    console.print("[bold magenta]🧪 compress_entire_folder 功能测试[/bold magenta]")
    console.print("=" * 60)
    
    try:
        # 运行测试
        test_compress_with_folder_structure()
        test_compress_without_folder_structure()
        test_compare_structures()
        
        console.print("\n[bold green]🎉 所有测试完成![/bold green]")
        
    except Exception as e:
        console.print(f"\n[bold red]❌ 测试过程中出现错误:[/] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
