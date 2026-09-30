"""配置加载模块"""

import os
from dataclasses import dataclass, field
from typing import List, Dict, Any

try:
    import yaml
except ImportError:
    sys_exit_msg = (
        "缺少依赖 PyYAML，请先安装：\n"
        "  pip install -r requirements.txt\n"
        "或单独安装：\n"
        "  pip install pyyaml"
    )
    raise SystemExit(sys_exit_msg)


@dataclass
class WebConfig:
    host: str = "127.0.0.1"
    port: int = 8080
    password: str = ""


@dataclass
class BackupConfig:
    enabled: bool = False
    type: str = "s3"
    s3: Dict[str, str] = field(default_factory=dict)
    webdav: Dict[str, str] = field(default_factory=dict)
    encryption_password: str = ""


@dataclass
class Config:
    scan_dirs: List[str] = field(default_factory=list)
    image_extensions: List[str] = field(default_factory=lambda: [
        ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".tiff"
    ])
    database: str = "gallery.db"
    thumbnail_dir: str = "thumbs"
    thumbnail_size: tuple = (300, 300)
    log_file: str = "logs/gallery.log"
    log_level: str = "INFO"
    web: WebConfig = field(default_factory=WebConfig)
    backup: BackupConfig = field(default_factory=BackupConfig)


def load_config(path: str = "config.yaml") -> Config:
    """从 YAML 文件加载配置。文件不存在则使用默认值。"""
    cfg = Config()
    if not os.path.exists(path):
        return cfg

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    # 以配置文件所在目录为基准，将相对路径转为绝对路径
    base_dir = os.path.dirname(os.path.abspath(path))

    cfg.scan_dirs = data.get("scan_dirs", cfg.scan_dirs)
    cfg.image_extensions = [
        e.lower() for e in data.get("image_extensions", cfg.image_extensions)
    ]
    cfg.database = _abs(base_dir, data.get("database", cfg.database))
    cfg.thumbnail_dir = _abs(base_dir, data.get("thumbnail_dir", cfg.thumbnail_dir))
    ts = data.get("thumbnail_size", list(cfg.thumbnail_size))
    cfg.thumbnail_size = (int(ts[0]), int(ts[1]))
    cfg.log_file = _abs(base_dir, data.get("log_file", cfg.log_file))
    cfg.log_level = data.get("log_level", cfg.log_level)

    web_data = data.get("web", {})
    cfg.web = WebConfig(
        host=web_data.get("host", "127.0.0.1"),
        port=int(web_data.get("port", 8080)),
        password=web_data.get("password", ""),
    )

    bk_data = data.get("backup", {})
    cfg.backup = BackupConfig(
        enabled=bk_data.get("enabled", False),
        type=bk_data.get("type", "s3"),
        s3=bk_data.get("s3", {}),
        webdav=bk_data.get("webdav", {}),
        encryption_password=bk_data.get("encryption_password", ""),
    )

    return cfg


def _abs(base_dir: str, p: str) -> str:
    """若 p 是相对路径，拼到 base_dir 下；否则原样返回。"""
    if os.path.isabs(p):
        return p
    return os.path.join(base_dir, p)


def ensure_dirs(cfg: Config):
    """确保数据库目录、缩略图目录、日志目录存在。"""
    for path in [cfg.database, cfg.thumbnail_dir, cfg.log_file]:
        d = os.path.dirname(os.path.abspath(path))
        if d:
            os.makedirs(d, exist_ok=True)
