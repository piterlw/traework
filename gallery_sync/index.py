"""SQLite 图片索引数据库。"""

import os
import sqlite3
import logging
from typing import List, Optional, Tuple

from .scanner import ImageInfo

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    folder TEXT,
    filename TEXT,
    size INTEGER,
    mtime REAL,
    file_hash TEXT,
    width INTEGER,
    height INTEGER,
    taken_at TEXT,
    indexed_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_images_hash ON images(file_hash);
CREATE INDEX IF NOT EXISTS idx_images_folder ON images(folder);
CREATE INDEX IF NOT EXISTS idx_images_taken ON images(taken_at);
"""


class ImageIndex:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(os.path.abspath(db_path)) or ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def upsert(self, info: ImageInfo):
        """插入或更新一条图片记录（按 path 唯一）。"""
        self.conn.execute(
            """INSERT INTO images (path, folder, filename, size, mtime, file_hash,
                                   width, height, taken_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(path) DO UPDATE SET
                   folder=excluded.folder,
                   filename=excluded.filename,
                   size=excluded.size,
                   mtime=excluded.mtime,
                   file_hash=excluded.file_hash,
                   width=excluded.width,
                   height=excluded.height,
                   taken_at=excluded.taken_at,
                   indexed_at=datetime('now')""",
            (info.path, info.folder, info.filename, info.size, info.mtime,
             info.file_hash, info.width, info.height, info.taken_at),
        )
        self.conn.commit()

    def remove_missing(self, valid_paths: set):
        """删除已不在磁盘上的记录。"""
        cur = self.conn.execute("SELECT path FROM images")
        existing = {row["path"] for row in cur.fetchall()}
        missing = existing - valid_paths
        for p in missing:
            self.conn.execute("DELETE FROM images WHERE path = ?", (p,))
        if missing:
            self.conn.commit()
            logger.info("清理了 %d 条已删除文件的记录", len(missing))

    def needs_update(self, path: str, mtime: float, size: int) -> bool:
        """判断文件是否需要重新索引。"""
        row = self.conn.execute(
            "SELECT mtime, size FROM images WHERE path = ?", (path,)
        ).fetchone()
        if row is None:
            return True
        return row["mtime"] != mtime or row["size"] != size

    def all(self, limit: int = 100, offset: int = 0) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM images ORDER BY taken_at DESC, indexed_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) AS c FROM images").fetchone()["c"]

    def folders(self) -> List[str]:
        return [
            r["folder"]
            for r in self.conn.execute(
                "SELECT DISTINCT folder FROM images ORDER BY folder"
            ).fetchall()
        ]

    def by_folder(self, folder: str, limit: int = 100, offset: int = 0) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM images WHERE folder = ? ORDER BY taken_at DESC LIMIT ? OFFSET ?",
            (folder, limit, offset),
        ).fetchall()

    def get(self, image_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM images WHERE id = ?", (image_id,)
        ).fetchone()

    def close(self):
        self.conn.close()
