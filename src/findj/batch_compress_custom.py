#!/usr/bin/env python3
"""
批量压缩脚本 - 使用自定义压缩函数
读取文件夹列表txt文件，使用compress_entire_folder函数批量压缩
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List
from datetime import datetime

# 导入自定义压缩模块
from autorepack.core.zip_compressor import ZipCompressor

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm

console = Console()


def read_folder_list(file_path: str) -> List[str]:
    """
    读取文件夹列表文件
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            folders = [line.strip() for line in f if line.strip()]
        return folders
    except Exception as e:
        console.print(f"[red]读取文件夹列表失败: {e}[/red]")
        return []


def validate_folders(folders: List[str]) -> List[Path]:
    """
    验证文件夹路径的有效性
    """
    valid_folders = []
    invalid_count = 0
    
    for folder_str in folders:
        folder_path = Path(folder_str)
        if folder_path.exists() and folder_path.is_dir():
            valid_folders.append(folder_path)
        else:
            console.print(f"[yellow]跳过无效路径: {folder_str}[/yellow]")
            invalid_count += 1
    
    if invalid_count > 0:
        console.print(f"[yellow]跳过了 {invalid_count} 个无效路径[/yellow]")
    
    return valid_folders


def batch_compress_folders(folders: List[Path], output_dir: str = None, 
                         compression_level: int = 7, delete_source: bool = False,
                         keep_folder_structure: bool = True) -> None:
    """
    批量压缩文件夹
    """
    if not folders:
        console.print("[red]没有有效的文件夹需要压缩[/red]")
        return
    
    # 创建压缩器实例
    compressor = ZipCompressor(compression_level=compression_level)
    
    # 如果指定了输出目录，创建它
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        console.print(f"[cyan]输出目录: {output_path.absolute()}[/cyan]")
    
    # 显示压缩配置
    console.print(Panel(
        f"[bold]批量压缩配置[/]\n"
        f"文件夹数量: [green]{len(folders)}[/]\n"
        f"压缩级别: [yellow]{compression_level}[/]\n"
        f"删除源文件: [{'red' if delete_source else 'green'}]{delete_source}[/]\n"
        f"保留文件夹结构: [{'green' if keep_folder_structure else 'yellow'}]{keep_folder_structure}[/]\n"
        f"输出目录: [cyan]{output_dir or '与源文件夹同级'}[/]",
        title="压缩设置",
        border_style="blue"
    ))
    
    # 统计变量
    success_count = 0
    fail_count = 0
    total_original_size = 0
    total_compressed_size = 0
    
    # 创建结果表格
    result_table = Table(show_header=True, header_style="bold blue")
    result_table.add_column("序号", justify="right", style="yellow", width=4)
    result_table.add_column("文件夹名", style="cyan", width=30)
    result_table.add_column("状态", justify="center", width=8)
    result_table.add_column("原始大小", justify="right", style="blue", width=12)
    result_table.add_column("压缩后", justify="right", style="green", width=12)
    result_table.add_column("压缩率", justify="right", style="magenta", width=8)
    
    # 开始批量压缩
    console.print(f"\n[bold green]开始批量压缩 {len(folders)} 个文件夹...[/bold green]\n")
    
    for i, folder_path in enumerate(folders, 1):
        folder_name = folder_path.name
        console.print(f"[bold cyan]({i}/{len(folders)})[/] 正在处理: [bold]{folder_name}[/]")
        
        try:
            # 确定压缩包输出路径
            if output_dir:
                target_zip = Path(output_dir) / f"{folder_name}.zip"
            else:
                target_zip = folder_path.parent / f"{folder_name}.zip"
            
            # 如果压缩包已存在，添加时间戳
            if target_zip.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                if output_dir:
                    target_zip = Path(output_dir) / f"{folder_name}_{timestamp}.zip"
                else:
                    target_zip = folder_path.parent / f"{folder_name}_{timestamp}.zip"
            
            # 调用自定义压缩函数
            result = compressor.compress_entire_folder(
                folder_path=folder_path,
                target_zip=target_zip,
                delete_source=delete_source,
                keep_folder_structure=keep_folder_structure
            )
            
            # 处理压缩结果
            if result.success:
                success_count += 1
                total_original_size += result.original_size
                total_compressed_size += result.compressed_size
                
                # 计算压缩率
                ratio = (1 - result.compressed_size / result.original_size) * 100 if result.original_size > 0 else 0
                
                result_table.add_row(
                    str(i),
                    folder_name,
                    "[green]✓[/]",
                    f"{result.original_size/1024/1024:.1f}MB",
                    f"{result.compressed_size/1024/1024:.1f}MB",
                    f"{ratio:.1f}%"
                )
                
                console.print(f"  [green]✓ 压缩成功: {target_zip.name}[/green]\n")
            else:
                fail_count += 1
                result_table.add_row(
                    str(i),
                    folder_name,
                    "[red]✗[/]",
                    "N/A",
                    "N/A",
                    "N/A"
                )
                
                console.print(f"  [red]✗ 压缩失败: {result.error_message}[/red]\n")
                
        except Exception as e:
            fail_count += 1
            result_table.add_row(
                str(i),
                folder_name,
                "[red]✗[/]",
                "N/A",
                "N/A",
                "N/A"
            )
            console.print(f"  [red]✗ 压缩出错: {str(e)}[/red]\n")
    
    # 显示结果表格
    console.print(result_table)
    
    # 显示总结信息
    total_ratio = (1 - total_compressed_size / total_original_size) * 100 if total_original_size > 0 else 0
    
    summary_panel = Panel(
        f"[bold green]压缩完成![/]\n\n"
        f"[bold]统计信息:[/]\n"
        f"• 成功: [green]{success_count}[/] 个\n"
        f"• 失败: [red]{fail_count}[/] 个\n"
        f"• 总计: [blue]{len(folders)}[/] 个\n\n"
        f"[bold]大小统计:[/]\n"
        f"• 原始总大小: [blue]{total_original_size/1024/1024:.1f}MB[/]\n"
        f"• 压缩后总大小: [green]{total_compressed_size/1024/1024:.1f}MB[/]\n"
        f"• 总体压缩率: [magenta]{total_ratio:.1f}%[/]\n"
        f"• 节省空间: [yellow]{(total_original_size-total_compressed_size)/1024/1024:.1f}MB[/]",
        title="批量压缩结果",
        border_style="green"
    )
    
    console.print(summary_panel)


def interactive_mode():
    """
    交互式模式
    """
    console = Console()
    
    # 显示欢迎信息
    console.print(Panel.fit(
        "[bold blue]批量文件夹压缩工具 - 交互模式[/bold blue]\n"
        "使用自定义 compress_entire_folder 函数",
        border_style="blue"
    ))
    
    # 获取文件夹列表文件路径
    while True:
        folder_list_file = Prompt.ask(
            "[bold green]请输入文件夹列表文件路径[/bold green]",
            default="uuid_folders.txt"
        )
        
        if not os.path.exists(folder_list_file):
            console.print(f"[red]错误: 文件 '{folder_list_file}' 不存在[/red]")
            continue
        
        break
    
    # 读取和验证文件夹列表
    console.print(f"[bold]读取文件夹列表:[/] [cyan]{folder_list_file}[/cyan]")
    folders_list = read_folder_list(folder_list_file)
    
    if not folders_list:
        console.print("[red]文件夹列表为空[/red]")
        return
    
    console.print(f"[green]从文件中读取到 {len(folders_list)} 个路径[/green]")
    
    # 验证文件夹路径
    valid_folders = validate_folders(folders_list)
    if not valid_folders:
        console.print("[red]没有有效的文件夹路径[/red]")
        return
    
    console.print(f"[green]验证通过 {len(valid_folders)} 个有效文件夹[/green]")
    
    # 显示文件夹预览
    if Confirm.ask("[bold yellow]是否预览要压缩的文件夹列表?[/bold yellow]", default=True):
        preview_table = Table(show_header=True, header_style="bold magenta")
        preview_table.add_column("序号", justify="right", style="yellow", width=4)
        preview_table.add_column("文件夹名", style="cyan", width=40)
        preview_table.add_column("路径", style="blue")
        
        for i, folder in enumerate(valid_folders[:10], 1):  # 只显示前10个
            preview_table.add_row(str(i), folder.name, str(folder))
        
        if len(valid_folders) > 10:
            preview_table.add_row("...", f"还有 {len(valid_folders) - 10} 个文件夹", "...")
        
        console.print(preview_table)
    
    # 获取输出目录
    use_output_dir = Confirm.ask("[bold yellow]是否指定输出目录?[/bold yellow]", default=False)
    output_dir = None
    if use_output_dir:
        output_dir = Prompt.ask(
            "[bold green]请输入输出目录路径[/bold green]",
            default="compressed"
        )
    
    # 获取压缩级别
    compression_level = int(Prompt.ask(
        "[bold yellow]请选择压缩级别 (0-9)[/bold yellow]",
        choices=[str(i) for i in range(10)],
        default="7"
    ))
    
    # 获取文件夹结构选项
    keep_folder_structure = Confirm.ask(
        "[bold yellow]是否保留最外层文件夹结构?[/bold yellow]",
        default=False
    )
    
    # 获取删除源文件选项
    delete_source = False
    if Confirm.ask("[bold red]是否在压缩成功后删除源文件夹? (危险操作)[/bold red]", default=True):
        # 二次确认
        if Confirm.ask("[bold red]确认删除源文件夹? 此操作不可逆![/bold red]", default=True):
            delete_source = True
        else:
            console.print("[green]已取消删除源文件夹选项[/green]")
    
    # 显示最终配置确认
    config_panel = Panel(
        f"[bold]批量压缩配置确认[/]\n\n"
        f"文件夹列表文件: [cyan]{folder_list_file}[/]\n"
        f"有效文件夹数量: [green]{len(valid_folders)}[/]\n"
        f"输出目录: [cyan]{output_dir or '与源文件夹同级'}[/]\n"
        f"压缩级别: [yellow]{compression_level}[/]\n"
        f"保留文件夹结构: [{'green' if keep_folder_structure else 'yellow'}]{keep_folder_structure}[/]\n"
        f"删除源文件: [{'red' if delete_source else 'green'}]{delete_source}[/]",
        title="配置确认",
        border_style="yellow"
    )
    
    console.print(config_panel)
    
    # 最终确认
    if not Confirm.ask("[bold green]确认开始批量压缩?[/bold green]", default=True):
        console.print("[yellow]已取消操作[/yellow]")
        return
    
    # 执行批量压缩
    batch_compress_folders(
        folders=valid_folders,
        output_dir=output_dir,
        compression_level=compression_level,
        delete_source=delete_source,
        keep_folder_structure=keep_folder_structure
    )


def main():
    parser = argparse.ArgumentParser(description='批量压缩文件夹 - 使用自定义compress_entire_folder函数')
    parser.add_argument(
        'folder_list_file',
        nargs='?',  # 使参数可选
        help='文件夹列表文件路径 (txt格式，每行一个文件夹路径，如果不提供则进入交互模式)'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        help='输出目录 (如果不指定，压缩包将放在源文件夹同级目录)'
    )
    parser.add_argument(
        '-l', '--level',
        type=int,
        default=7,
        choices=range(0, 10),
        help='压缩级别 (0-9，默认7)'
    )
    parser.add_argument(
        '--delete-source',
        action='store_true',
        help='压缩成功后删除源文件夹 (危险操作，请谨慎使用)'
    )
    parser.add_argument(
        '--no-folder-structure',
        action='store_true',
        help='不保留最外层文件夹结构，直接压缩文件夹内容'
    )
    parser.add_argument(
        '-i', '--interactive',
        action='store_true',
        help='强制进入交互模式'
    )
    
    args = parser.parse_args()
    
    # 处理文件夹结构参数
    args.keep_structure = not args.no_folder_structure
    
    # 如果没有提供文件夹列表文件或指定了交互模式，则进入交互模式
    if not args.folder_list_file or args.interactive:
        interactive_mode()
        return
    
    # 命令行模式
    # 检查文件夹列表文件是否存在
    if not os.path.exists(args.folder_list_file):
        console.print(f"[red]错误: 文件夹列表文件不存在: {args.folder_list_file}[/red]")
        sys.exit(1)
    
    # 显示欢迎信息
    console.print(Panel.fit(
        "[bold blue]批量文件夹压缩工具[/bold blue]\n"
        "使用自定义 compress_entire_folder 函数",
        border_style="blue"
    ))
    
    console.print(f"[bold]读取文件夹列表:[/] [cyan]{args.folder_list_file}[/cyan]")
    
    # 读取和验证文件夹列表
    folders_list = read_folder_list(args.folder_list_file)
    if not folders_list:
        console.print("[red]文件夹列表为空[/red]")
        sys.exit(1)
    
    console.print(f"[green]从文件中读取到 {len(folders_list)} 个路径[/green]")
    
    # 验证文件夹路径
    valid_folders = validate_folders(folders_list)
    if not valid_folders:
        console.print("[red]没有有效的文件夹路径[/red]")
        sys.exit(1)
    
    console.print(f"[green]验证通过 {len(valid_folders)} 个有效文件夹[/green]")
    
    # 如果启用了删除源文件，显示警告
    if args.delete_source:
        console.print(Panel(
            "[bold red]警告: 已启用删除源文件夹选项![/]\n"
            "[yellow]压缩成功后将删除原始文件夹，此操作不可逆![/]\n"
            "[red]请确保您已备份重要数据![/]",
            title="危险操作警告",
            border_style="red"
        ))
        
        # 简单确认 (在脚本中可以考虑添加交互确认)
        console.print("[yellow]继续执行批量压缩...[/yellow]")
    
    # 开始批量压缩
    batch_compress_folders(
        folders=valid_folders,
        output_dir=args.output,
        compression_level=args.level,
        delete_source=args.delete_source,
        keep_folder_structure=args.keep_structure
    )


if __name__ == '__main__':
    main()
