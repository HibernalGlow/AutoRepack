"""Typer CLI for repacku (重写自旧 argparse 版本)

功能:
1. analyze: 仅分析指定路径(或剪贴板) 生成 *_config.json
2. compress: 按配置文件或目录执行分析+压缩
3. single-pack: 单层打包模式 (子目录 + 散图)
4. gallery-pack: 画集模式 (.画集)
5. auto: (默认命令) 分析后询问是否压缩，可用 --yes 跳过确认

与 rawfilter 一致: 无参数尝试启动 lata (Taskfile UI)。
"""
from __future__ import annotations
import sys
import os
from pathlib import Path
from typing import Optional, List
import subprocess
import typer
from rich.console import Console
from loguru import logger

from repacku.core.folder_analyzer import analyze_folder as do_analyze
from repacku.core.zip_compressor import ZipCompressor
from repacku.core.single_packer import SinglePacker

try:
    import pyperclip  # type: ignore
except Exception:  # pragma: no cover
    pyperclip = None

app = typer.Typer(add_completion=False, help="repacku 打包/分析工具 (Typer 版)")
console = Console()

# ------------------ 辅助函数 ------------------

def _try_launch_lata(force: bool = False) -> bool:
    """尝试启动 lata / 相关 TUI。

    返回 True 表示已经成功启动（本次流程可结束）。
    返回 False 表示需要继续走 CLI 逻辑。
    """
    # 允许用户通过环境变量覆盖命令
    candidate_cmds: List[str] = []
    env_cmd = os.environ.get("LATA_CMD")
    if env_cmd:
        candidate_cmds.append(env_cmd)
    candidate_cmds.extend(["lata", "lata.exe", "taskui"])  # 可能的可执行名

    # 定位 Taskfile.yml：优先当前包，再向上查找
    pkg_dir = Path(__file__).parent
    search_paths = [pkg_dir, pkg_dir.parent.parent]
    taskfile_dir: Optional[Path] = None
    for base in search_paths:
        tf = base / "Taskfile.yml"
        if tf.exists():
            taskfile_dir = base
            break
    if not taskfile_dir:
        if force:
            console.print("[red]未找到 Taskfile.yml，无法启动 lata。[/red]")
        return False

    # 逐个尝试候选命令
    for cmd in candidate_cmds:
        try:
            result = subprocess.run(cmd, cwd=taskfile_dir)
            if result.returncode == 0:
                logger.info(f"已使用命令 '{cmd}' 启动 TUI (cwd={taskfile_dir})")
                return True
            else:
                logger.debug(f"命令 {cmd} 退出码 {result.returncode}，尝试下一个")
        except FileNotFoundError:
            continue
        except Exception as e:  # pragma: no cover
            logger.debug(f"启动 {cmd} 异常: {e}")
            continue

    if force:
        console.print("[yellow]未找到可用的 lata / taskui 命令，可执行: pip install lata[/yellow]")
    return False

def _clipboard_path() -> Optional[str]:
    if not pyperclip:
        return None
    try:
        data = pyperclip.paste().strip()
    except Exception:
        return None
    if not data:
        return None
    # 仅取第一行存在的路径
    for line in data.splitlines():
        p = line.strip().strip('"').strip("'")
        if p and os.path.exists(p):
            return p
    return None

# ------------------ 核心公共逻辑 ------------------

def _ensure_path(path: Optional[str], clipboard: bool) -> Path:
    if clipboard and not path:
        c = _clipboard_path()
        if c:
            path = c
    if not path:
        raise typer.BadParameter("未提供有效路径，可使用 --path 或 --clipboard")
    p = Path(path)
    if not p.exists() or not p.is_dir():
        raise typer.BadParameter(f"路径无效: {p}")
    return p

def _analyze(path: Path, types: List[str] | None, display: bool) -> Path:
    target = types if types else None
    cfg_path = do_analyze(path, target_file_types=target, display=display)
    return Path(cfg_path)

# ------------------ 命令定义 ------------------

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    path: Optional[str] = typer.Option(None, "--path", "-p", help="要处理的目录"),
    types: Optional[str] = typer.Option(None, "--types", "-t", help="文件类型逗号分隔，如: image,document"),
    clipboard: bool = typer.Option(False, "--clipboard", "-c", help="从剪贴板获取路径"),
    yes: bool = typer.Option(False, "--yes", "-y", help="自动确认后续操作"),
    delete_after: bool = typer.Option(False, "--delete-after", "-d", help="压缩成功后删除源"),
) -> None:
    """默认流程: 分析 -> (询问/或自动) 压缩"""
    if ctx.invoked_subcommand is not None:
        return
    raw_args = [a for a in sys.argv[1:] if a.strip()]
    if not raw_args:  # 尝试 lata
        if _try_launch_lata():
            raise typer.Exit(0)
        # 若用户既未给 path 又未声明 clipboard，优先给出提示并直接退出而不是报错
        if not path and not clipboard:
            console.print("[magenta]提示: 未提供路径参数，且未能启动 lata。\n"\
                           "请使用 --path / --clipboard 或安装 lata 后直接运行。[/magenta]")
            raise typer.Exit(1)
        console.print("[cyan]未检测到参数，进入 CLI 模式。[/cyan]")

    p = _ensure_path(path, clipboard)
    type_list = [s.strip() for s in types.split(',')] if types else None
    console.print(f"[blue]分析路径: {p}\n类型: {type_list or 'ALL'}[/blue]")
    cfg = _analyze(p, type_list, display=True)
    console.print(f"[green]分析完成: {cfg}[/green]")
    if not yes:
        confirm = typer.confirm("是否继续压缩?", default=True)
        if not confirm:
            console.print("[yellow]已取消压缩步骤。[/yellow]")
            raise typer.Exit(0)
    comp = ZipCompressor()
    results = comp.compress_from_json(cfg, delete_after_success=delete_after)
    succ = sum(1 for r in results if r.success)
    fail = len(results) - succ
    console.print(f"[green]成功: {succ}  失败: {fail}[/green]")

@app.command(help="仅分析，输出 *_config.json")
def analyze(
    path: Optional[str] = typer.Option(None, "--path", "-p"),
    types: Optional[str] = typer.Option(None, "--types", "-t"),
    clipboard: bool = typer.Option(False, "--clipboard", "-c"),
    no_display: bool = typer.Option(False, "--no-display", help="不展示树形结构"),
):
    p = _ensure_path(path, clipboard)
    type_list = [s.strip() for s in types.split(',')] if types else None
    cfg = _analyze(p, type_list, display=not no_display)
    console.print(f"[green]配置生成: {cfg}")

@app.command(help="分析后立即压缩 (跳过确认)")
def compress(
    path: Optional[str] = typer.Option(None, "--path", "-p"),
    types: Optional[str] = typer.Option(None, "--types", "-t"),
    clipboard: bool = typer.Option(False, "--clipboard", "-c"),
    delete_after: bool = typer.Option(False, "--delete-after", "-d"),
):
    p = _ensure_path(path, clipboard)
    type_list = [s.strip() for s in types.split(',')] if types else None
    cfg = _analyze(p, type_list, display=True)
    comp = ZipCompressor()
    comp.compress_from_json(cfg, delete_after_success=delete_after)

@app.command(help="单层打包模式 (不基于分析配置)")
def single_pack(
    path: Optional[str] = typer.Option(None, "--path", "-p"),
    clipboard: bool = typer.Option(False, "--clipboard", "-c"),
    delete_after: bool = typer.Option(False, "--delete-after", "-d"),
):
    p = _ensure_path(path, clipboard)
    packer = SinglePacker()
    packer.pack_directory(str(p), delete_after=delete_after)

@app.command(help="画集模式：递归查找包含 '.画集' 的文件夹")
def gallery_pack(
    path: Optional[str] = typer.Option(None, "--path", "-p"),
    clipboard: bool = typer.Option(False, "--clipboard", "-c"),
    delete_after: bool = typer.Option(False, "--delete-after", "-d"),
):
    p = _ensure_path(path, clipboard)
    packer = SinglePacker()
    packer.process_gallery_folders(str(p), delete_after=delete_after)

# 外部调用入口

def run():  # pragma: no cover
    app()

if __name__ == "__main__":  # pragma: no cover
    run()
