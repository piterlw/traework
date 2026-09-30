"""本地图片扫描器：遍历配置目录，发现图片文件并提取元数据。"""

import os
import hashlib
import logging
from dataclasses import dataclass
from typing import Iterator, List

try:
    from PIL import Image
except ImportError:  # Pillow 在运行时安装
    Image = None

try:
    import piexif
except ImportError:
    piexif = None

from .config import Config

logger = logging.getLogger(__name__)


@dataclass
class ImageInfo:
    path: str
    size: int
    mtime: float
    file_hash: str
    width: int = 0
    height: int = 0
    taken_at: str = ""  # EXIF DateTimeOriginal, ISO format
    folder: str = ""
    filename: str = ""


def _file_hash(path: str, chunk_size: int = 65536) -> str:
    """计算文件的 SHA-256 哈希（分块读取，大文件友好）。"""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
    except OSError as e:
        logger.warning("无法读取文件 %s: %s", path, e)
        return ""
    return h.hexdigest()


def _read_image_meta(path: str):
    """读取图片尺寸和 EXIF 拍摄时间。"""
    width = height = 0
    taken_at = ""
    if Image is None:
        return width, height, taken_at
    try:
        with Image.open(path) as img:
            width, height = img.size
            # 尝试读取 EXIF
            exif = img.info.get("exif")
            if exif and piexif is not None:
                try:
                    info = piexif.load(exif)
                    dt = info.get("Exif", {}).get(piexif.ExifIFD.DateTimeOriginal)
                    if dt:
                        taken_at = dt.decode("utf-8", "ignore") if isinstance(dt, bytes) else str(dt)
                except Exception:
                    pass
    except Exception as e:
        logger.debug("读取图片元数据失败 %s: %s", path, e)
    return width, height, taken_at


def scan(cfg: Config) -> Iterator[ImageInfo]:
    """扫描所有配置目录，逐个产出 ImageInfo。"""
    exts = set(cfg.image_extensions)
    for base_dir in cfg.scan_dirs:
        if not os.path.isdir(base_dir):
            logger.warning("扫描目录不存在，跳过: %s", base_dir)
            continue
        logger.info("开始扫描目录: %s", base_dir)
        for root, _dirs, files in os.walk(base_dir):
            for name in files:
                ext = os.path.splitext(name)[1].lower()
                if ext not in exts:
                    continue
                full_path = os.path.join(root, name)
                try:
                    st = os.stat(full_path)
                except OSError as e:
                    logger.warning("stat 失败 %s: %s", full_path, e)
                    continue
                file_hash = _file_hash(full_path)
                if not file_hash:
                    continue
                width, height, taken_at = _read_image_meta(full_path)
                yield ImageInfo(
                    path=full_path,
                    size=st.st_size,
                    mtime=st.st_mtime,
                    file_hash=file_hash,
                    width=width,
                    height=height,
                    taken_at=taken_at,
                    folder=os.path.relpath(root, base_dir),
                    filename=name,
                )
    logger.info("扫描完成")


def count_images(cfg: Config) -> int:
    """统计图片总数（用于进度提示）。"""
    exts = set(cfg.image_extensions)
    total = 0
    for base_dir in cfg.scan_dirs:
        if not os.path.isdir(base_dir):
            continue
        for root, _dirs, files in os.walk(base_dir):
            for name in files:
                if os.path.splitext(name)[1].lower() in exts:
                    total += 1
    return total
