"""自动检索图片目录模块。

提供两种检索方式：
1. 检索系统常见图片目录（按平台自动判断）
2. 从指定根目录全盘搜索包含至少 N 张图片的目录
"""

import os
import sys
import logging
from typing import List, Tuple

from .config import Config

logger = logging.getLogger(__name__)

# 系统级目录（Linux/macOS），遍历时跳过（仅跳过虚拟文件系统和启动目录）
SKIP_DIRS_UNIX = {"/proc", "/sys", "/dev", "/boot", "/lost+found"}
# Windows 系统目录
SKIP_DIRS_WIN = {"$Recycle.Bin", "System Volume Information", "Windows",
                 "ProgramData", "Program Files", "Program Files (x86)",
                 "AppData", "Windows.old"}

# 常见图片目录候选（按平台）
def common_image_dirs() -> List[str]:
    """返回当前平台常见的图片存储目录。"""
    home = os.path.expanduser("~")
    dirs = []
    if sys.platform.startswith("win"):
        # Windows: 图片、下载、桌面，以及各盘根目录
        dirs = [
            os.path.join(home, "Pictures"),
            os.path.join(home, "Downloads"),
            os.path.join(home, "Desktop"),
            os.path.join(home, "Videos"),
            os.path.join(home, "OneDrive", "Pictures"),
        ]
        # 常见盘符 D: E: F:
        for drive in "DEFGH":
            d = f"{drive}:\\"
            if os.path.isdir(d):
                dirs.append(d)
    elif sys.platform == "darwin":
        # macOS
        dirs = [
            os.path.join(home, "Pictures"),
            os.path.join(home, "Downloads"),
            os.path.join(home, "Desktop"),
            os.path.join(home, "Movies"),
            os.path.join(home, "Documents"),
            "/Volumes",
            os.path.join(home, "Pictures", "Photos Library.photoslibrary", "Masters"),
        ]
    else:
        # Linux
        dirs = [
            os.path.join(home, "Pictures"),
            os.path.join(home, "Images"),
            os.path.join(home, "Downloads"),
            os.path.join(home, "Desktop"),
            os.path.join(home, "Documents"),
            os.path.join(home, "Videos"),
            "/mnt",
            "/media",
        ]
    # 过滤掉不存在的目录
    return [d for d in dirs if os.path.isdir(d)]


def _count_images_in_dir(path: str, exts: set, max_count: int = 50) -> int:
    """统计单个目录下（含子目录）的图片数量，达到 max_count 提前返回。"""
    count = 0
    try:
        for root, _dirs, files in os.walk(path):
            for name in files:
                if os.path.splitext(name)[1].lower() in exts:
                    count += 1
                    if count >= max_count:
                        return count
    except (PermissionError, OSError):
        pass
    return count


def discover_common_dirs(cfg: Config, min_images: int = 1) -> List[Tuple[str, int]]:
    """检索系统常见图片目录，返回 [(目录路径, 图片数量), ...]。

    仅返回图片数量 >= min_images 的目录。
    """
    exts = set(cfg.image_extensions)
    results = []
    for d in common_image_dirs():
        count = _count_images_in_dir(d, exts, max_count=max(min_images, 50))
        if count >= min_images:
            results.append((d, count))
            logger.info("发现图片目录: %s (%d 张)", d, count)
    return results


def _should_skip(name: str) -> bool:
    """判断目录名是否应跳过（系统目录）。"""
    if sys.platform.startswith("win"):
        return name in SKIP_DIRS_WIN
    else:
        return False  # UNIX 下通过路径前缀判断


def discover_dirs_with_images(
    root: str,
    cfg: Config,
    min_images: int = 10,
    max_depth: int = 8,
) -> List[Tuple[str, int]]:
    """从 root 开始搜索，返回包含 >= min_images 张图片的目录列表。

    - 跳过系统目录（/proc、/sys 等）
    - 每个目录的图片数只统计到 min_images 即提前返回（短路优化）
    - max_depth 限制递归深度，避免过深
    """
    exts = set(cfg.image_extensions)
    results: List[Tuple[str, int]] = []
    skipped = 0

    root = os.path.abspath(root)
    for current_root, dirs, files in os.walk(root):
        # 计算当前深度
        rel = os.path.relpath(current_root, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > max_depth:
            dirs[:] = []  # 不再深入
            continue

        # 跳过系统目录
        if sys.platform.startswith("win"):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS_WIN]
        else:
            if current_root in SKIP_DIRS_UNIX or any(
                current_root.startswith(s + os.sep) for s in SKIP_DIRS_UNIX
            ):
                dirs[:] = []
                continue

        # 统计当前目录（不递归）的图片数
        local_count = 0
        for name in files:
            if os.path.splitext(name)[1].lower() in exts:
                local_count += 1

        # 如果当前目录图片数达标，记录
        if local_count >= min_images:
            results.append((current_root, local_count))
            logger.info("发现图片目录: %s (%d 张)", current_root, local_count)

    if skipped:
        logger.info("跳过了 %d 个无权限目录", skipped)

    if not results:
        logger.info("在 %s 下未找到包含 >= %d 张图片的目录", root, min_images)

    return results


def update_config_with_dirs(
    config_path: str,
    dirs: List[str],
    merge: bool = True,
) -> str:
    """将发现的目录写入 config.yaml 的 scan_dirs。

    - merge=True: 与现有 scan_dirs 合并去重
    - merge=False: 覆盖现有 scan_dirs
    返回写入结果的描述。
    """
    import yaml

    existing_dirs: List[str] = []
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        existing_dirs = data.get("scan_dirs", []) or []
    else:
        data = {}

    if merge:
        merged = list(dict.fromkeys(existing_dirs + dirs))  # 去重保序
    else:
        merged = dirs

    data["scan_dirs"] = merged
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    added = len(merged) - len(existing_dirs) if merge else len(dirs)
    return f"已写入 {len(merged)} 个扫描目录到 {config_path}（新增 {added} 个）"
