#!/usr/bin/env python3
"""Personal Gallery Sync — 命令行入口。

用法:
    python main.py scan        扫描本地图片并建立索引 + 生成缩略图
    python main.py serve       启动 Web 画廊服务（可远程查看）
    python main.py backup      备份索引中的图片到你配置的云存储
    python main.py full        扫描 + 备份（一键全量同步）
    python main.py discover    自动检索图片目录（可写入 config.yaml）
"""

import argparse
import logging
import os
import sys

from gallery_sync.config import load_config, ensure_dirs
from gallery_sync.scanner import scan, count_images
from gallery_sync.index import ImageIndex
from gallery_sync.thumbnail import make_thumbnail
from gallery_sync.backup import BackupClient
from gallery_sync.web import run_server
from gallery_sync.discover import (
    discover_common_dirs,
    discover_dirs_with_images,
    update_config_with_dirs,
)


def setup_logging(cfg):
    ensure_dirs(cfg)
    logging.basicConfig(
        level=getattr(logging, cfg.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(cfg.log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def cmd_scan(cfg):
    index = ImageIndex(cfg.database)
    total = count_images(cfg)
    logging.info("预计扫描 %d 张图片", total)
    valid_paths = set()
    done = 0
    for info in scan(cfg):
        valid_paths.add(info.path)
        # 仅当文件有变化时才重新读元数据/索引
        if index.needs_update(info.path, info.mtime, info.size):
            index.upsert(info)
            make_thumbnail(info.path, cfg.thumbnail_dir, info.file_hash, cfg.thumbnail_size)
        done += 1
        if done % 50 == 0:
            logging.info("已处理 %d / %d", done, total)
    index.remove_missing(valid_paths)
    logging.info("扫描完成，索引共 %d 张图片", index.count())
    index.close()


def cmd_serve(cfg):
    index = ImageIndex(cfg.database)
    run_server(cfg, index)
    index.close()


def cmd_backup(cfg):
    if not cfg.backup.enabled:
        logging.warning("备份未启用，请在 config.yaml 中设置 backup.enabled: true")
        return
    client = BackupClient(cfg.backup)
    index = ImageIndex(cfg.database)
    rows = index.all(limit=100000)
    logging.info("开始备份 %d 张图片", len(rows))
    ok = 0
    for row in rows:
        remote_key = f"{row['folder']}/{row['filename']}" if row["folder"] else row["filename"]
        if client.upload(row["path"], remote_key):
            ok += 1
        if (ok + 1) % 20 == 0:
            logging.info("已备份 %d / %d", ok, len(rows))
    logging.info("备份完成：成功 %d / %d", ok, len(rows))
    index.close()


def cmd_full(cfg):
    cmd_scan(cfg)
    if cfg.backup.enabled:
        cmd_backup(cfg)


def cmd_discover(cfg, args):
    """自动检索图片目录。

    - 无 --root：只检索系统常见图片目录（快速）
    - 有 --root：从该根目录全盘搜索含 >= --min-images 张图片的目录
    - --write：将结果写入 config.yaml 的 scan_dirs
    - --no-merge：覆盖而非合并现有 scan_dirs
    """
    if args.root:
        logging.info("从 %s 搜索包含 >= %d 张图片的目录...", args.root, args.min_images)
        results = discover_dirs_with_images(
            args.root, cfg, min_images=args.min_images, max_depth=args.max_depth
        )
    else:
        logging.info("检索系统常见图片目录...")
        results = discover_common_dirs(cfg, min_images=args.min_images)

    if not results:
        print("\n未找到符合条件的图片目录。")
        print("提示：可尝试 --root <路径> 指定更大范围，或降低 --min-images 阈值。")
        return

    print(f"\n发现 {len(results)} 个图片目录：")
    print("-" * 60)
    for path, count in results:
        print(f"  [{count:>5} 张]  {path}")
    print("-" * 60)

    if args.write:
        dirs = [p for p, _ in results]
        msg = update_config_with_dirs(args.config, dirs, merge=not args.no_merge)
        print(f"\n{msg}")
    else:
        print("\n提示：加 --write 参数可将以上目录自动写入 config.yaml")


def main():
    parser = argparse.ArgumentParser(description="Personal Gallery Sync")
    parser.add_argument("command", choices=["scan", "serve", "backup", "full", "discover"],
                        help="scan=扫描索引, serve=启动Web画廊, backup=备份到云存储, full=扫描+备份, discover=自动检索图片目录")
    parser.add_argument("-c", "--config", default="config.yaml", help="配置文件路径")
    # discover 专属参数
    parser.add_argument("--root", default=None, help="discover 专用：全盘搜索的根目录（不指定则只扫常见目录）")
    parser.add_argument("--min-images", type=int, default=1, help="discover 专用：目录至少包含多少张图片才计入（默认 1）")
    parser.add_argument("--max-depth", type=int, default=8, help="discover 专用：全盘搜索的最大递归深度（默认 8）")
    parser.add_argument("--write", action="store_true", help="discover 专用：将发现的目录写入 config.yaml")
    parser.add_argument("--no-merge", action="store_true", help="discover 专用：覆盖现有 scan_dirs 而非合并")
    args = parser.parse_args()

    cfg = load_config(args.config)
    setup_logging(cfg)

    if args.command == "discover":
        cmd_discover(cfg, args)
        return

    if not cfg.scan_dirs and args.command in ("scan", "full"):
        logging.error("未配置 scan_dirs，请先运行 'python main.py discover --write' 自动检索，或手动编辑 config.yaml")
        sys.exit(1)

    {
        "scan": cmd_scan,
        "serve": cmd_serve,
        "backup": cmd_backup,
        "full": cmd_full,
    }[args.command](cfg)


if __name__ == "__main__":
    main()
