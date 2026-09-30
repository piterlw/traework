"""缩略图生成模块。"""

import os
import logging
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)


def thumbnail_path(thumbnail_dir: str, file_hash: str) -> str:
    """根据文件哈希生成缩略图路径（前 2 字符分子目录，避免单目录文件过多）。"""
    sub = file_hash[:2] if file_hash else "xx"
    return os.path.join(thumbnail_dir, sub, file_hash + ".jpg")


def make_thumbnail(
    src_path: str,
    thumbnail_dir: str,
    file_hash: str,
    size: tuple = (300, 300),
) -> Optional[str]:
    """生成缩略图，已存在则跳过。返回缩略图路径。"""
    if not file_hash:
        return None
    out = thumbnail_path(thumbnail_dir, file_hash)
    if os.path.exists(out):
        return out
    try:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with Image.open(src_path) as img:
            img.thumbnail(size)
            # 统一转 RGB 保存为 JPEG
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(out, "JPEG", quality=85)
        return out
    except Exception as e:
        logger.warning("生成缩略图失败 %s: %s", src_path, e)
        return None
