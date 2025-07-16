#!/usr/bin/env python3
"""
搜索包含16位UUID命名的JSON文件的文件夹
只输出最深层的文件夹（避免嵌套输出）
"""

import os
import sys
import re
import argparse
from pathlib import Path
from typing import Set, List, Tuple
from datetime import datetime

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def is_uuid_json_file(filename: str) -> bool:
    """
    检查文件名是否符合16位ASCII字符 + .json的格式
    """
    # 移除.json后缀
    if not filename.lower().endswith('.json'):
        return False
    
    name_without_ext = filename[:-5]  # 移除.json
    
    # 检查是否为16位ASCII字符
    if len(name_without_ext) != 16:
        return False
    
    # 检查是否全部为ASCII字符（通常UUID使用十六进制字符）
    return all(c.isascii() and (c.isalnum() or c in '-_') for c in name_without_ext)


def count_total_folders(root_path: str) -> int:
    """
    统计总文件夹数量，用于进度条
    """
    total_count = 0
    for root, dirs, files in os.walk(root_path):
        total_count += 1
    return total_count


def find_folders_with_uuid_json(root_path: str, console: Console) -> Tuple[Set[str], int]:
    """
    查找包含UUID JSON文件的所有文件夹，带进度条
    """
    folders_with_json = set()
    total_folders = count_total_folders(root_path)
    processed_folders = 0
    total_json_files = 0
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        task = progress.add_task("扫描文件夹...", total=total_folders)
        
        for root, dirs, files in os.walk(root_path):
            # 检查当前文件夹是否包含符合条件的JSON文件
            uuid_json_files = [f for f in files if is_uuid_json_file(f)]
            
            if uuid_json_files:
                folders_with_json.add(os.path.abspath(root))
                total_json_files += len(uuid_json_files)
            
            processed_folders += 1
            progress.update(task, advance=1, description=f"扫描文件夹... (找到 {len(folders_with_json)} 个匹配文件夹)")
    
    return folders_with_json, total_json_files


def filter_deepest_folders(folders: Set[str]) -> List[str]:
    """
    过滤出最深层的文件夹，如果父文件夹和子文件夹都包含JSON文件，只保留子文件夹
    """
    sorted_folders = sorted(folders, key=len, reverse=True)  # 按路径长度降序排列
    result = []
    
    for folder in sorted_folders:
        # 检查是否有任何已添加的文件夹是当前文件夹的子文件夹
        is_parent_of_existing = any(
            existing.startswith(folder + os.sep) for existing in result
        )
        
        if not is_parent_of_existing:
            result.append(folder)
    
    return sorted(result)


def save_results_to_file(deepest_folders: List[str], output_file: str) -> bool:
    """
    将搜索结果保存到txt文件 - 只写入文件夹列表
    """
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            for folder in deepest_folders:
                f.write(f"{folder}\n")
        return True
    except Exception as e:
        return False


def interactive_mode():
    """
    交互式模式
    """
    console = Console()
    
    # 显示欢迎信息
    console.print(Panel.fit(
        "[bold blue]UUID JSON 文件夹搜索工具[/bold blue]\n"
        "搜索包含16位UUID命名的JSON文件的文件夹",
        border_style="blue"
    ))
    
    # 获取搜索路径
    while True:
        folder_path = Prompt.ask(
            "[bold green]请输入要搜索的文件夹路径[/bold green]",
            default="."
        )
        
        if not os.path.exists(folder_path):
            console.print(f"[red]错误: 路径 '{folder_path}' 不存在[/red]")
            continue
        
        if not os.path.isdir(folder_path):
            console.print(f"[red]错误: '{folder_path}' 不是一个文件夹[/red]")
            continue
        
        break
    
    # 获取选项
    verbose = Confirm.ask("[bold yellow]是否显示详细信息?[/bold yellow]", default=False)
    save_to_file = Confirm.ask("[bold yellow]是否将结果保存到txt文件?[/bold yellow]", default=True)
    
    output_file = None
    if save_to_file:
        output_file = Prompt.ask(
            "[bold green]请输入输出文件名[/bold green]",
            default=f"uuid_folders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
    
    # 执行搜索
    search_and_display(folder_path, verbose, console, output_file)


def search_and_display(folder_path: str, verbose: bool, console: Console, output_file: str = None):
    """
    执行搜索并显示结果
    """
    folder_path = os.path.abspath(folder_path)
    
    console.print(f"\n[bold]搜索文件夹:[/bold] [cyan]{folder_path}[/cyan]")
    console.print("[bold]查找包含16位UUID命名的JSON文件的文件夹...[/bold]\n")
    
    # 查找所有包含UUID JSON文件的文件夹
    all_folders, total_json_files = find_folders_with_uuid_json(folder_path, console)
    
    if verbose and all_folders:
        console.print(f"\n[bold green]找到 {len(all_folders)} 个包含UUID JSON文件的文件夹:[/bold green]")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("文件夹路径", style="cyan")
        table.add_column("JSON文件数", justify="right", style="green")
        
        for folder in sorted(all_folders):
            try:
                files = os.listdir(folder)
                uuid_json_files = [f for f in files if is_uuid_json_file(f)]
                table.add_row(folder, str(len(uuid_json_files)))
            except PermissionError:
                table.add_row(folder, "[red]无权限[/red]")
        
        console.print(table)
        console.print()
    
    # 过滤出最深层的文件夹
    console.print("[bold]正在过滤嵌套文件夹...[/bold]")
    deepest_folders = filter_deepest_folders(all_folders)
    
    # 显示最终结果
    console.print(Panel(
        f"[bold green]最终结果 (仅最深层文件夹): {len(deepest_folders)} 个[/bold green]\n"
        f"[bold blue]总共找到 UUID JSON 文件: {total_json_files} 个[/bold blue]",
        title="搜索完成",
        border_style="green"
    ))
    
    if deepest_folders:
        console.print("\n[bold]结果列表:[/bold]")
        
        # 创建结果表格
        result_table = Table(show_header=True, header_style="bold blue")
        result_table.add_column("序号", justify="right", style="yellow")
        result_table.add_column("文件夹路径", style="cyan")
        if verbose:
            result_table.add_column("JSON文件数", justify="right", style="green")
        
        for i, folder in enumerate(deepest_folders, 1):
            if verbose:
                try:
                    files = os.listdir(folder)
                    uuid_json_files = [f for f in files if is_uuid_json_file(f)]
                    result_table.add_row(str(i), folder, str(len(uuid_json_files)))
                except PermissionError:
                    result_table.add_row(str(i), folder, "[red]无权限[/red]")
            else:
                result_table.add_row(str(i), folder)
        
        console.print(result_table)
        
        # 显示详细的JSON文件信息
        if verbose and Confirm.ask("\n[bold yellow]是否显示每个文件夹中的具体JSON文件?[/bold yellow]", default=False):
            for folder in deepest_folders:
                console.print(f"\n[bold cyan]{folder}[/bold cyan]:")
                try:
                    files = os.listdir(folder)
                    uuid_json_files = [f for f in files if is_uuid_json_file(f)]
                    if uuid_json_files:
                        for json_file in sorted(uuid_json_files):
                            console.print(f"  • [green]{json_file}[/green]")
                    else:
                        console.print("  [red]无UUID JSON文件[/red]")
                except PermissionError:
                    console.print("  [red](无法读取文件夹内容)[/red]")
        
        # 保存结果到文件
        if output_file:
            if save_results_to_file(deepest_folders, output_file):
                console.print(f"\n[bold green]✓ 结果已保存到文件: {output_file}[/bold green]")
            else:
                console.print(f"\n[bold red]✗ 保存文件失败: {output_file}[/bold red]")
    else:
        console.print("\n[yellow]未找到包含16位UUID命名的JSON文件的文件夹[/yellow]")


def main():
    parser = argparse.ArgumentParser(
        description='搜索包含16位UUID命名的JSON文件的文件夹'
    )
    parser.add_argument(
        'folder_path',
        nargs='?',  # 使路径参数可选
        help='要搜索的根文件夹路径 (如果不提供则进入交互模式)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='显示详细信息'
    )
    parser.add_argument(
        '-i', '--interactive',
        action='store_true',
        help='强制进入交互模式'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        help='输出文件路径 (保存文件夹列表到txt文件)'
    )
    
    args = parser.parse_args()
    console = Console()
    
    # 如果没有提供路径参数或指定了交互模式，则进入交互模式
    if not args.folder_path or args.interactive:
        interactive_mode()
        return
    
    # 命令行模式
    # 检查路径是否存在
    if not os.path.exists(args.folder_path):
        console.print(f"[red]错误: 路径 '{args.folder_path}' 不存在[/red]", file=sys.stderr)
        sys.exit(1)
    
    if not os.path.isdir(args.folder_path):
        console.print(f"[red]错误: '{args.folder_path}' 不是一个文件夹[/red]", file=sys.stderr)
        sys.exit(1)
    
    search_and_display(args.folder_path, args.verbose, console, args.output)


if __name__ == '__main__':
    main()