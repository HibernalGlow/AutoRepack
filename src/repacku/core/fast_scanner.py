#!/usr/bin/env python
"""
高性能文件夹扫描器

使用多种优化技术提升扫描速度:
1. scandir-rs (Rust 实现的高性能目录扫描)
2. 并行处理优化
3. 扩展名缓存
4. 批量处理减少 I/O
"""

import os
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple, Iterator, Any
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
import logging

# 尝试导入高性能库
try:
    import scandir_rs
    HAS_SCANDIR_RS = True
except ImportError:
    HAS_SCANDIR_RS = False

try:
    from joblib import Parallel, delayed
    HAS_JOBLIB = True
except ImportError:
    HAS_JOBLIB = False

from repacku.core.common_utils import (
    DEFAULT_FILE_TYPES, BLACKLIST_KEYWORDS,
    COMPRESS_MODE_ENTIRE, COMPRESS_MODE_SELECTIVE, COMPRESS_MODE_SKIP,
    FileTypeManager, is_blacklisted_path
)


# 预编译扩展名到类型的映射 (反向索引，加速查找)
_EXT_TO_TYPE_CACHE: Dict[str, str] = {}

def _build_ext_cache():
    """构建扩展名到类型的缓存映射"""
    global _EXT_TO_TYPE_CACHE
    if _EXT_TO_TYPE_CACHE:
        return
    for type_name, extensions in DEFAULT_FILE_TYPES.items():
        for ext in extensions:
            _EXT_TO_TYPE_CACHE[ext] = type_name

_build_ext_cache()


def fast_get_file_type(ext: str) -> Optional[str]:
    """快速获取文件类型 (使用缓存)"""
    return _EXT_TO_TYPE_CACHE.get(ext.lower())


@dataclass
class ScanResult:
    """扫描结果数据类"""
    path: str
    name: str
    depth: int
    files: List[Tuple[str, str, int]] = field(default_factory=list)  # (name, ext, size)
    subdirs: List[str] = field(default_factory=list)
    file_types: Dict[str, int] = field(default_factory=dict)
    file_extensions: Dict[str, int] = field(default_factory=dict)
    total_files: int = 0
    total_size: int = 0


class FastScanner:
    """高性能文件夹扫描器"""
    
    def __init__(self, max_workers: int = None, use_rust: bool = True):
        """
        初始化扫描器
        
        Args:
            max_workers: 最大工作线程数，默认为 CPU 核心数 * 2
            use_rust: 是否使用 Rust 实现的 scandir (如果可用)
        """
        self.max_workers = max_workers or min(32, (os.cpu_count() or 1) * 2)
        self.use_rust = use_rust and HAS_SCANDIR_RS
        self._file_type_manager = FileTypeManager()
        
    def scan_directory_fast(self, root_path: Path) -> Iterator[Tuple[str, List[os.DirEntry], List[os.DirEntry]]]:
        """
        快速扫描目录，返回 (目录路径, 文件列表, 子目录列表)
        
        使用 scandir-rs 或 os.scandir 进行高效扫描
        """
        if self.use_rust:
            yield from self._scan_with_rust(root_path)
        else:
            yield from self._scan_with_os(root_path)
    
    def _scan_with_rust(self, root_path: Path) -> Iterator[Tuple[str, List, List]]:
        """使用 scandir-rs 进行扫描"""
        try:
            # scandir_rs.walk 返回类似 os.walk 的结果
            for dirpath, dirnames, filenames in scandir_rs.walk(str(root_path)):
                # 过滤黑名单目录
                dirnames[:] = [d for d in dirnames if not self._is_blacklisted_name(d)]
                yield dirpath, filenames, dirnames
        except Exception as e:
            logging.warning(f"scandir-rs 扫描失败，回退到 os.scandir: {e}")
            yield from self._scan_with_os(root_path)
    
    def _scan_with_os(self, root_path: Path) -> Iterator[Tuple[str, List, List]]:
        """使用 os.scandir 进行扫描 (优化版)"""
        try:
            entries = list(os.scandir(root_path))
        except (OSError, PermissionError) as e:
            logging.warning(f"无法扫描目录 {root_path}: {e}")
            return
        
        files = []
        dirs = []
        
        for entry in entries:
            try:
                if entry.is_file(follow_symlinks=False):
                    files.append(entry)
                elif entry.is_dir(follow_symlinks=False):
                    if not self._is_blacklisted_name(entry.name):
                        dirs.append(entry)
            except (OSError, PermissionError):
                continue
        
        yield str(root_path), files, dirs
    
    def _is_blacklisted_name(self, name: str) -> bool:
        """检查目录名是否在黑名单中 (只检查目录名，不检查完整路径)"""
        name_lower = name.lower()
        # 只有完全匹配或以黑名单关键词开头才过滤
        for kw in BLACKLIST_KEYWORDS:
            kw_lower = kw.lower()
            if name_lower == kw_lower or name_lower.startswith(kw_lower + '.'):
                return True
        return False
    
    def scan_single_folder(self, folder_path: Path, 
                          target_types: List[str] = None,
                          calc_size: bool = False) -> ScanResult:
        """
        扫描单个文件夹 (不递归)
        
        Args:
            folder_path: 文件夹路径
            target_types: 目标文件类型
            calc_size: 是否计算文件大小 (关闭可提升速度)
        """
        result = ScanResult(
            path=str(folder_path),
            name=folder_path.name,
            depth=len(folder_path.parts)
        )
        
        # 只检查目录名，不检查完整路径
        if self._is_blacklisted_name(folder_path.name):
            return result
        
        try:
            entries = os.scandir(folder_path)
        except (OSError, PermissionError) as e:
            logging.warning(f"无法扫描 {folder_path}: {e}")
            return result
        
        file_types = Counter()
        file_exts = Counter()
        files_data = []
        subdirs = []
        total_size = 0
        
        for entry in entries:
            try:
                if entry.is_file(follow_symlinks=False):
                    ext = Path(entry.name).suffix.lower()
                    size = entry.stat().st_size if calc_size else 0
                    files_data.append((entry.name, ext, size))
                    total_size += size
                    
                    # 快速类型查找
                    ftype = fast_get_file_type(ext)
                    if ftype:
                        file_types[ftype] += 1
                    if ext:
                        file_exts[ext] += 1
                        
                elif entry.is_dir(follow_symlinks=False):
                    if not self._is_blacklisted_name(entry.name):
                        subdirs.append(entry.path)
            except (OSError, PermissionError):
                continue
        
        result.files = files_data
        result.subdirs = subdirs
        result.file_types = dict(file_types)
        result.file_extensions = dict(file_exts)
        result.total_files = len(files_data)
        result.total_size = total_size
        
        return result


    def scan_tree_parallel(self, root_path: Path, 
                          target_types: List[str] = None,
                          calc_size: bool = False) -> Dict[str, ScanResult]:
        """
        并行扫描整个目录树
        
        Args:
            root_path: 根目录路径
            target_types: 目标文件类型
            calc_size: 是否计算文件大小
            
        Returns:
            Dict[str, ScanResult]: 路径到扫描结果的映射
        """
        results: Dict[str, ScanResult] = {}
        
        # 第一阶段：收集所有目录
        all_dirs = self._collect_all_dirs(root_path)
        
        # 第二阶段：并行扫描所有目录
        if HAS_JOBLIB and len(all_dirs) > 100:
            # 大量目录时使用 joblib
            scan_results = Parallel(n_jobs=self.max_workers, prefer="threads")(
                delayed(self.scan_single_folder)(Path(d), target_types, calc_size)
                for d in all_dirs
            )
            for res in scan_results:
                results[res.path] = res
        else:
            # 使用 ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self.scan_single_folder, Path(d), target_types, calc_size): d
                    for d in all_dirs
                }
                for future in as_completed(futures):
                    try:
                        res = future.result()
                        results[res.path] = res
                    except Exception as e:
                        logging.warning(f"扫描失败: {futures[future]}, {e}")
        
        return results
    
    def _collect_all_dirs(self, root_path: Path) -> List[str]:
        """快速收集所有目录路径"""
        dirs = [str(root_path)]
        
        if self.use_rust:
            try:
                for dirpath, dirnames, _ in scandir_rs.walk(str(root_path)):
                    # 过滤黑名单
                    dirnames[:] = [d for d in dirnames if not self._is_blacklisted_name(d)]
                    for d in dirnames:
                        dirs.append(os.path.join(dirpath, d))
                return dirs
            except Exception:
                pass
        
        # 回退到 os.walk
        for dirpath, dirnames, _ in os.walk(root_path):
            # 过滤黑名单 - 只检查目录名
            dirnames[:] = [d for d in dirnames if not self._is_blacklisted_name(d)]
            for d in dirnames:
                full_path = os.path.join(dirpath, d)
                dirs.append(full_path)
        
        return dirs


class FastFolderAnalyzer:
    """高性能文件夹分析器 (基于 FastScanner)"""
    
    def __init__(self, max_workers: int = None):
        self.scanner = FastScanner(max_workers=max_workers)
        self._file_type_manager = FileTypeManager()
        
        self.COMPRESS_MODE_ENTIRE = COMPRESS_MODE_ENTIRE
        self.COMPRESS_MODE_SELECTIVE = COMPRESS_MODE_SELECTIVE
        self.COMPRESS_MODE_SKIP = COMPRESS_MODE_SKIP
    
    def analyze_folder_tree_fast(self, root_path: Path, 
                                 target_file_types: List[str] = None) -> Dict[str, Any]:
        """
        快速分析整个文件夹树
        
        Args:
            root_path: 根目录
            target_file_types: 目标文件类型
            
        Returns:
            分析结果字典
        """
        if isinstance(root_path, str):
            root_path = Path(root_path)
        
        # 并行扫描所有目录
        scan_results = self.scanner.scan_tree_parallel(
            root_path, 
            target_types=target_file_types,
            calc_size=False  # 不计算大小以提升速度
        )
        
        # 构建树结构
        return self._build_tree_from_scans(root_path, scan_results, target_file_types)
    
    def _build_tree_from_scans(self, root_path: Path, 
                               scans: Dict[str, ScanResult],
                               target_types: List[str] = None) -> Dict[str, Any]:
        """从扫描结果构建树结构"""
        root_scan = scans.get(str(root_path))
        if not root_scan:
            return {}
        
        def build_node(scan: ScanResult) -> Dict[str, Any]:
            # 确定压缩模式
            compress_mode = self._determine_compress_mode_fast(
                scan, target_types, scans
            )
            
            # 构建子节点
            children = []
            for subdir in scan.subdirs:
                child_scan = scans.get(subdir)
                if child_scan:
                    children.append(build_node(child_scan))
            
            # 按文件数量排序子节点
            children.sort(key=lambda x: x.get('total_files', 0), reverse=True)
            
            return {
                'path': scan.path,
                'name': scan.name,
                'depth': scan.depth,
                'total_files': scan.total_files,
                'file_types': scan.file_types,
                'file_extensions': scan.file_extensions,
                'compress_mode': compress_mode,
                'children': children if children else None
            }
        
        return build_node(root_scan)
    
    def _determine_compress_mode_fast(self, scan: ScanResult, 
                                      target_types: List[str],
                                      all_scans: Dict[str, ScanResult]) -> str:
        """快速确定压缩模式"""
        if not scan.files:
            return self.COMPRESS_MODE_SKIP
        
        # 检查是否有压缩包
        has_archive = scan.file_types.get('archive', 0) > 0
        
        # 检查子目录是否有压缩包
        has_child_archive = any(
            all_scans.get(subdir, ScanResult(path='', name='', depth=0)).file_types.get('archive', 0) > 0
            for subdir in scan.subdirs
        )
        
        if has_archive or has_child_archive:
            if not target_types:
                return self.COMPRESS_MODE_SKIP
            
            # 检查是否有匹配的文件
            matching_count = sum(
                scan.file_types.get(t, 0) for t in target_types
            )
            if matching_count >= 2:
                return self.COMPRESS_MODE_SELECTIVE
            return self.COMPRESS_MODE_SKIP
        
        # 无压缩包情况
        if not target_types:
            return self.COMPRESS_MODE_ENTIRE if scan.total_files >= 2 else self.COMPRESS_MODE_SKIP
        
        # 计算匹配文件数
        matching_count = sum(scan.file_types.get(t, 0) for t in target_types)
        
        if matching_count < 2:
            return self.COMPRESS_MODE_SKIP
        
        if matching_count == scan.total_files:
            return self.COMPRESS_MODE_ENTIRE
        
        return self.COMPRESS_MODE_SELECTIVE


# 便捷函数
def fast_scan_folder(folder_path: Path, 
                     target_types: List[str] = None,
                     max_workers: int = None) -> Dict[str, Any]:
    """
    快速扫描文件夹的便捷函数
    
    Args:
        folder_path: 文件夹路径
        target_types: 目标文件类型
        max_workers: 最大工作线程数
        
    Returns:
        分析结果字典
    """
    analyzer = FastFolderAnalyzer(max_workers=max_workers)
    return analyzer.analyze_folder_tree_fast(folder_path, target_types)


def benchmark_scan(folder_path: Path, iterations: int = 3) -> Dict[str, float]:
    """
    对比不同扫描方法的性能
    
    Args:
        folder_path: 测试文件夹
        iterations: 迭代次数
        
    Returns:
        各方法的平均耗时
    """
    import time
    from repacku.core.folder_analyzer import FolderAnalyzer
    
    results = {}
    
    # 测试原始方法
    original_times = []
    for _ in range(iterations):
        start = time.perf_counter()
        analyzer = FolderAnalyzer()
        analyzer.analyze_folder_structure(folder_path)
        original_times.append(time.perf_counter() - start)
    results['original'] = sum(original_times) / len(original_times)
    
    # 测试快速方法
    fast_times = []
    for _ in range(iterations):
        start = time.perf_counter()
        fast_scan_folder(folder_path)
        fast_times.append(time.perf_counter() - start)
    results['fast'] = sum(fast_times) / len(fast_times)
    
    # 计算加速比
    results['speedup'] = results['original'] / results['fast'] if results['fast'] > 0 else 0
    
    return results
