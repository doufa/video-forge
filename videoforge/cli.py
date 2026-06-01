"""VideoForge CLI - 命令行工具

Usage:
    python -m videoforge.cli stats         # 素材库统计
    python -m videoforge.cli scan          # 扫描并索引现有素材
    python -m videoforge.cli list          # 列出素材
    python -m videoforge.cli tag           # 为素材生成 CLIP 向量
    python -m videoforge.cli search        # 搜索素材
    python -m videoforge.cli dedup         # 查找/删除重复素材
    python -m videoforge.cli template      # 管理叙事模板
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from videoforge.storage import Database, Asset, read_sidecar
from videoforge.utils.paths import PROJECT_ROOT, get_relative_path, get_absolute_path


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def cmd_stats(args):
    """显示素材库统计信息"""
    from videoforge.storage.vector_store import VectorStore

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

    vector_store = VectorStore()
    vector_store.load()
    indexed = vector_store.active_count

    print("=" * 40)
    print("VideoForge Asset Library")
    print("=" * 40)
    print(f"Total assets: {total}")
    print(f"  - Videos: {videos} ({format_size(video_size)})")
    print(f"  - Images: {images} ({format_size(image_size)})")
    print(f"  - Audio: {audio} ({format_size(audio_size)})")
    print(f"Total size: {format_size(total_size)}")
    print("-" * 40)
    print(f"Indexed (FAISS): {indexed} ({indexed*100//max(total,1)}%)")
    print(f"Reviewed: {reviewed} ({reviewed*100//max(total,1)}%)")
    print("=" * 40)


def cmd_scan(args):
    """扫描并索引现有素材到数据库"""
    scan_dir = Path(args.dir) if args.dir else PROJECT_ROOT / "output" / "assets"

    if not scan_dir.exists():
        print(f"Directory not found: {scan_dir}")
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

    print(f"\nScan complete: added {added}, skipped {skipped}")


def cmd_list(args):
    """列出素材"""
    with Database() as db:
        assets = db.list_assets(
            asset_type=args.type,
            reviewed=args.reviewed,
            limit=args.limit,
        )

        if not assets:
            print("No assets found")
            return

        print(f"Found {len(assets)} assets:\n")
        for asset in assets:
            tags_str = ", ".join(asset.tags[:3]) if asset.tags else ""
            size_str = format_size(asset.file_size) if asset.file_size else "?"
            reviewed_mark = "Y" if asset.reviewed else " "
            indexed_mark = "V" if asset.embedding else " "
            print(f"[{reviewed_mark}{indexed_mark}] {asset.path}")
            print(f"    Type: {asset.asset_type} | Size: {size_str}")
            if tags_str:
                print(f"    Tags: {tags_str}")
            print()


def cmd_tag(args):
    """为素材生成 CLIP 向量并添加到 FAISS 索引"""
    from videoforge.skills.asset_tag.clip_embedder import (
        get_asset_embedding,
        is_clip_available,
    )
    from videoforge.storage.vector_store import VectorStore

    if not is_clip_available():
        print("CLIP not available. Install with:")
        print("  pip install git+https://github.com/openai/CLIP.git torch torchvision")
        return

    vector_store = VectorStore()
    vector_store.load()

    tagged = 0
    skipped = 0
    errors = 0

    with Database() as db:
        if args.all:
            assets = db.list_assets(limit=10000)
        else:
            assets = [a for a in db.list_assets(limit=10000) if a.id not in vector_store._asset_to_faiss]

        if not assets:
            print("No assets to tag")
            return

        print(f"Tagging {len(assets)} assets...")

        for i, asset in enumerate(assets, 1):
            if not args.force and asset.id in vector_store._asset_to_faiss:
                skipped += 1
                continue

            asset_path = get_absolute_path(asset.path)
            if not asset_path.exists():
                print(f"  [SKIP] File not found: {asset.path}")
                skipped += 1
                continue

            print(f"  [{i}/{len(assets)}] {asset.filename_original or asset.path}...", end=" ", flush=True)

            try:
                embedding = get_asset_embedding(asset_path)
                if embedding is not None:
                    vector_store.add(embedding, asset.id)

                    asset.embedding = embedding.tobytes()
                    db.update_asset(asset)

                    print("OK")
                    tagged += 1
                else:
                    print("FAILED (no embedding)")
                    errors += 1
            except Exception as e:
                print(f"ERROR: {e}")
                errors += 1

    vector_store.save()

    print(f"\nTagging complete: {tagged} tagged, {skipped} skipped, {errors} errors")
    print(f"FAISS index now contains {vector_store.active_count} vectors")


def cmd_search(args):
    """搜索素材"""
    query = " ".join(args.query)
    if not query:
        print("Please provide a search query")
        return

    from videoforge.skills.asset_search.local_faiss import LocalFAISSProvider
    from videoforge.config import load_config

    config = load_config()
    provider = LocalFAISSProvider(config.get("skills", {}).get("asset_search", {}))

    print(f"Searching for: {query}\n")
    results = provider.search(query, top_k=args.limit)

    if not results:
        print("No results found")
        return

    print(f"Found {len(results)} results:\n")
    for i, result in enumerate(results, 1):
        score_pct = int(result.score * 100)
        print(f"{i}. [{score_pct}%] {result.asset_path.name}")
        print(f"   Source: {result.source} | Type: {result.asset_type}")
        if result.description:
            print(f"   Description: {result.description[:60]}...")
        print()


def cmd_dedup(args):
    """查找和删除重复素材"""
    from videoforge.storage.dedup import deduplicate_assets

    method = args.method
    dry_run = not args.execute
    threshold = args.threshold

    print(f"Finding duplicates using {method} method...")
    if dry_run:
        print("(Dry run - no files will be deleted)\n")

    result = deduplicate_assets(
        method=method,
        threshold=threshold,
        dry_run=dry_run,
    )

    if result["groups"] == 0:
        print("No duplicates found!")
        return

    print(f"Found {result['duplicates']} duplicates in {result['groups']} groups")
    print(f"Space that can be freed: {format_size(result['freed_bytes'])}\n")

    if dry_run and result["details"]:
        print("Duplicate groups:")
        for i, group in enumerate(result["details"][:10], 1):
            print(f"\n  Group {i}: {group.original_path}")
            for dup_id, dup_path, sim in group.duplicates:
                print(f"    - {dup_path} (similarity: {sim:.2%})")

        if len(result["details"]) > 10:
            print(f"\n  ... and {len(result['details']) - 10} more groups")

        print("\nRun with --execute to remove duplicates")
    elif not dry_run:
        print(f"Removed {result['duplicates']} duplicate files")


def cmd_template(args):
    """管理叙事模板"""
    from videoforge.skills.rag_template import TemplateExtractor
    from videoforge.config import load_config

    config = load_config()
    extractor = TemplateExtractor(config)

    if args.action == "list":
        templates = extractor.list_templates(args.domain)
        if not templates:
            print("No templates found")
            return

        print(f"Found {len(templates)} templates:\n")
        for t in templates:
            print(f"  [{t.id}] {t.topic_domain}")
            print(f"      Channel: {t.source_channel or 'N/A'}")
            print(f"      Techniques: {', '.join(t.techniques[:3])}")
            print(f"      Structure: {len(t.structure)} parts")
            print()

    elif args.action == "extract":
        if not args.url:
            print("Please provide a YouTube URL with --url")
            return

        print(f"Extracting template from: {args.url}")
        template = extractor.extract_from_url(args.url, channel=args.channel or "")

        if not template:
            print("Failed to extract template")
            return

        print(f"\nExtracted template:")
        print(f"  Domain: {template.topic_domain}")
        print(f"  Techniques: {', '.join(template.techniques)}")
        print(f"  Structure ({len(template.structure)} parts):")
        for part in template.structure:
            print(f"    - [{part['type']}] {part['description'][:50]}...")

        if args.save:
            template_id = extractor.save_template(template)
            print(f"\nSaved as template ID: {template_id}")
        else:
            print("\nUse --save to save this template")

    elif args.action == "show":
        if not args.id:
            print("Please provide a template ID with --id")
            return

        template = extractor.get_template(args.id)
        if not template:
            print(f"Template {args.id} not found")
            return

        print(f"Template {template.id}:")
        print(f"  Domain: {template.topic_domain}")
        print(f"  Channel: {template.source_channel or 'N/A'}")
        print(f"  URL: {template.source_url or 'N/A'}")
        print(f"  Techniques: {', '.join(template.techniques)}")
        print(f"  Style: {template.style_notes}")
        print(f"\n  Structure:")
        for i, part in enumerate(template.structure, 1):
            print(f"    {i}. [{part['type']}] {part['description']}")


def main():
    parser = argparse.ArgumentParser(
        description="VideoForge CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # stats
    parser_stats = subparsers.add_parser("stats", help="Show library statistics")
    parser_stats.set_defaults(func=cmd_stats)

    # scan
    parser_scan = subparsers.add_parser("scan", help="Scan and index assets")
    parser_scan.add_argument("--dir", help="Directory to scan", default=None)
    parser_scan.set_defaults(func=cmd_scan)

    # list
    parser_list = subparsers.add_parser("list", help="List assets")
    parser_list.add_argument("--type", choices=["video", "image", "audio"], help="Filter by type")
    parser_list.add_argument("--reviewed", action="store_true", help="Show only reviewed")
    parser_list.add_argument("--limit", type=int, default=20, help="Max results")
    parser_list.set_defaults(func=cmd_list)

    # tag
    parser_tag = subparsers.add_parser("tag", help="Generate CLIP embeddings for assets")
    parser_tag.add_argument("--all", action="store_true", help="Tag all assets (not just untagged)")
    parser_tag.add_argument("--force", action="store_true", help="Re-tag even if already indexed")
    parser_tag.set_defaults(func=cmd_tag)

    # search
    parser_search = subparsers.add_parser("search", help="Search assets")
    parser_search.add_argument("query", nargs="+", help="Search query")
    parser_search.add_argument("--limit", type=int, default=5, help="Max results")
    parser_search.set_defaults(func=cmd_search)

    # dedup
    parser_dedup = subparsers.add_parser("dedup", help="Find and remove duplicate assets")
    parser_dedup.add_argument("--method", choices=["hash", "visual"], default="hash",
                              help="Deduplication method (default: hash)")
    parser_dedup.add_argument("--threshold", type=float, default=0.95,
                              help="Visual similarity threshold (default: 0.95)")
    parser_dedup.add_argument("--execute", action="store_true",
                              help="Actually delete duplicates (default: dry run)")
    parser_dedup.set_defaults(func=cmd_dedup)

    # template
    parser_template = subparsers.add_parser("template", help="Manage narrative templates")
    parser_template.add_argument("action", choices=["list", "extract", "show"],
                                 help="Action to perform")
    parser_template.add_argument("--url", help="YouTube URL for extraction")
    parser_template.add_argument("--channel", help="Channel name for extraction")
    parser_template.add_argument("--save", action="store_true", help="Save extracted template")
    parser_template.add_argument("--id", type=int, help="Template ID for show")
    parser_template.add_argument("--domain", help="Filter by topic domain")
    parser_template.set_defaults(func=cmd_template)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
