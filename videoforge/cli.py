"""VideoForge CLI - 命令行工具

Usage:
    python -m videoforge.cli stats         # 素材库统计
    python -m videoforge.cli scan          # 扫描并索引现有素材
    python -m videoforge.cli list          # 列出素材
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from videoforge.storage import Database, Asset, read_sidecar
from videoforge.utils.paths import PROJECT_ROOT, get_relative_path


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def cmd_stats(args):
    """显示素材库统计信息"""
    with Database() as db:
        total = db.count_assets()
        videos = db.count_assets("video")
        images = db.count_assets("image")
        audio = db.count_assets("audio")

        video_size = db.get_total_size("video")
        image_size = db.get_total_size("image")
        audio_size = db.get_total_size("audio")
        total_size = video_size + image_size + audio_size

        reviewed = len(db.list_assets(reviewed=True, limit=10000))
        indexed = len([a for a in db.list_assets(limit=10000) if a.embedding])

        print("=" * 40)
        print("VideoForge 素材库统计")
        print("=" * 40)
        print(f"总素材数: {total}")
        print(f"  - 视频: {videos} ({format_size(video_size)})")
        print(f"  - 图片: {images} ({format_size(image_size)})")
        print(f"  - 音频: {audio} ({format_size(audio_size)})")
        print(f"总大小: {format_size(total_size)}")
        print("-" * 40)
        print(f"已索引 (有向量): {indexed} ({indexed*100//max(total,1)}%)")
        print(f"已审核: {reviewed} ({reviewed*100//max(total,1)}%)")
        print("=" * 40)


def cmd_scan(args):
    """扫描并索引现有素材到数据库"""
    scan_dir = Path(args.dir) if args.dir else PROJECT_ROOT / "output" / "assets"

    if not scan_dir.exists():
        print(f"目录不存在: {scan_dir}")
        return

    video_exts = {".mp4", ".webm", ".mkv", ".mov", ".avi"}
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    audio_exts = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}

    added = 0
    skipped = 0

    with Database() as db:
        for file_path in scan_dir.iterdir():
            if not file_path.is_file():
                continue

            ext = file_path.suffix.lower()
            if ext in video_exts:
                asset_type = "video"
            elif ext in image_exts:
                asset_type = "image"
            elif ext in audio_exts:
                asset_type = "audio"
            else:
                continue

            rel_path = get_relative_path(file_path)
            existing = db.get_asset_by_path(rel_path)
            if existing:
                skipped += 1
                continue

            metadata = read_sidecar(file_path)
            asset = Asset(
                path=rel_path,
                asset_type=asset_type,
                source=metadata.source if metadata else "local",
                original_query=metadata.original_query if metadata else "",
                original_url=metadata.original_url if metadata else "",
                filename_original=file_path.name,
                description=metadata.description if metadata else "",
                tags=metadata.tags if metadata else [],
                file_size=file_path.stat().st_size,
                reviewed=metadata.reviewed if metadata else False,
            )

            db.add_asset(asset)
            added += 1
            print(f"  + {file_path.name}")

    print(f"\n扫描完成: 新增 {added}, 跳过 {skipped}")


def cmd_list(args):
    """列出素材"""
    with Database() as db:
        assets = db.list_assets(
            asset_type=args.type,
            reviewed=args.reviewed,
            limit=args.limit,
        )

        if not assets:
            print("没有找到素材")
            return

        print(f"找到 {len(assets)} 个素材:\n")
        for asset in assets:
            tags_str = ", ".join(asset.tags[:3]) if asset.tags else ""
            size_str = format_size(asset.file_size) if asset.file_size else "?"
            reviewed_mark = "✓" if asset.reviewed else " "
            print(f"[{reviewed_mark}] {asset.path}")
            print(f"    类型: {asset.asset_type} | 大小: {size_str}")
            if tags_str:
                print(f"    标签: {tags_str}")
            print()


def main():
    parser = argparse.ArgumentParser(
        description="VideoForge CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="命令")

    # stats
    parser_stats = subparsers.add_parser("stats", help="显示素材库统计")
    parser_stats.set_defaults(func=cmd_stats)

    # scan
    parser_scan = subparsers.add_parser("scan", help="扫描并索引素材")
    parser_scan.add_argument("--dir", help="要扫描的目录", default=None)
    parser_scan.set_defaults(func=cmd_scan)

    # list
    parser_list = subparsers.add_parser("list", help="列出素材")
    parser_list.add_argument("--type", choices=["video", "image", "audio"], help="类型过滤")
    parser_list.add_argument("--reviewed", action="store_true", help="只显示已审核")
    parser_list.add_argument("--limit", type=int, default=20, help="最大数量")
    parser_list.set_defaults(func=cmd_list)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
