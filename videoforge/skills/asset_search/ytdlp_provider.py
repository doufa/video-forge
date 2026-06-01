from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
from pathlib import Path

from videoforge.models import AssetResult
from videoforge.skills.base import AssetSearchSkill
from videoforge.storage import Asset, Database
from videoforge.storage.sidecar import AssetMetadata, read_sidecar, write_sidecar
from videoforge.utils.paths import get_relative_path

logger = logging.getLogger(__name__)


class YTDLPSearchProvider(AssetSearchSkill):
    """基于 yt-dlp 的 YouTube B-roll 检索与下载，自带本地缓存、元数据 sidecar 和数据库入库"""

    def __init__(self, config: dict):
        self.config = config.get("ytdlp", {})
        self.assets_dir = Path("output/assets")
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.fallback_asset = self.assets_dir / "fallback.jpg"
        self._ensure_fallback_asset()

    def _ensure_fallback_asset(self):
        """确保存在一个兜底的本地素材"""
        if not self.fallback_asset.exists():
            logger.info("Creating fallback black image...")
            black_jpg = bytes.fromhex(
                "ffd8ffe000104a46494600010101004800480000ffdb004300080606070605080707070909080a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c30313434341f27393d38323c2e333432ffdb0043010909090c0b0c180d0d1832211c213232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232ffc00011080001000103012200021101031101ffc4001f0000010501010101010100000000000000000102030405060708090a0bffc400b5100002010303020403050504040000017d01020300041105122131410613516107227114328191a1082342b1c11552d1f02433627282090a161718191a25262728292a3435363738393a434445464748494a535455565758595a636465666768696a737475767778797a838485868788898a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae1e2e3e4e5e6e7e8e9eaf1f2f3f4f5f6f7f8f9faffc4001f0100030101010101010101010000000000000102030405060708090a0bffc400b51100020102040403040705040400010277000102031104052131061241510761711322328108144291a1b1c109233352f0156272d10a162434e125f11718191a262728292a35363738393a434445464748494a535455565758595a636465666768696a737475767778797a838485868788898a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae2e3e4e5e6e7e8e9eaf2f3f4f5f6f7f8f9faffda000c03010002110311003f00f9fe8a28a00f"
            )
            self.fallback_asset.write_bytes(black_jpg)

    def _slugify(self, text: str) -> str:
        """将搜索词转为合法的文件名"""
        text = text.lower()
        text = re.sub(r"[^a-z0-9]+", "_", text)
        return text.strip("_")

    def _get_video_info(self, query: str) -> dict | None:
        """获取视频元信息（不下载）"""
        cmd = [
            sys.executable,
            "-m",
            "yt_dlp",
            f"ytsearch1:{query}",
            "--dump-json",
            "--no-download",
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30, encoding="utf-8"
            )
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
        except Exception as e:
            logger.debug(f"Failed to get video info: {e}")
        return None

    def _write_metadata(
        self, target_file: Path, query: str, video_info: dict | None
    ) -> AssetMetadata:
        """写入 sidecar 元数据并返回"""
        original_url = ""
        duration_sec = None
        resolution = ""
        width = None
        height = None

        if video_info:
            original_url = video_info.get("webpage_url", "")
            duration_sec = video_info.get("duration")
            width = video_info.get("width")
            height = video_info.get("height")
            if width and height:
                resolution = f"{width}x{height}"

        file_size = target_file.stat().st_size if target_file.exists() else None

        metadata = AssetMetadata(
            source="youtube",
            original_query=query,
            original_url=original_url,
            description=f"YouTube search result for: {query}",
            tags=self._extract_tags(query),
            duration_sec=duration_sec,
            resolution=resolution,
            file_size=file_size,
            reviewed=False,
        )
        write_sidecar(target_file, metadata)
        logger.debug(f"Wrote sidecar metadata for {target_file}")
        return metadata

    def _ingest_to_database(
        self, target_file: Path, metadata: AssetMetadata, video_info: dict | None
    ) -> int | None:
        """将素材入库到数据库"""
        rel_path = get_relative_path(target_file)

        width = None
        height = None
        if video_info:
            width = video_info.get("width")
            height = video_info.get("height")

        try:
            with Database() as db:
                existing = db.get_asset_by_path(rel_path)
                if existing:
                    logger.debug(f"Asset already in database: {rel_path}")
                    return existing.id

                asset = Asset(
                    path=rel_path,
                    asset_type="video",
                    source="youtube",
                    original_query=metadata.original_query,
                    original_url=metadata.original_url,
                    filename_original=target_file.name,
                    description=metadata.description,
                    tags=metadata.tags,
                    duration_sec=metadata.duration_sec,
                    width=width,
                    height=height,
                    file_size=metadata.file_size,
                    reviewed=False,
                )
                asset_id = db.add_asset(asset)
                logger.info(f"Ingested asset to database: {rel_path} (ID: {asset_id})")
                return asset_id

        except Exception as e:
            logger.error(f"Failed to ingest asset to database: {e}")
            return None

    def _extract_tags(self, query: str) -> list[str]:
        """从搜索词提取标签"""
        words = re.split(r"[\s,]+", query.lower())
        tags = [w.strip() for w in words if len(w.strip()) > 2]
        return list(dict.fromkeys(tags))[:10]

    def search(self, query: str, top_k: int = 1, **kwargs) -> list[AssetResult]:
        """利用 yt-dlp 搜索 YouTube 并在本地缓存"""
        if not query.strip():
            return [
                AssetResult(
                    asset_path=self.fallback_asset,
                    score=0.0,
                    source="fallback",
                    asset_type="image",
                )
            ]

        safe_query = re.sub(r"[^\w\-_\. ]", "_", query)
        target_file = Path(self.assets_dir) / f"{safe_query}.mp4"

        if target_file.exists():
            logger.info(f"Using cached asset for query '{query}': {target_file}")
            metadata = read_sidecar(target_file)
            return [
                AssetResult(
                    asset_path=target_file,
                    score=1.0,
                    source="local_cache",
                    description=metadata.description if metadata else query,
                    asset_type="video",
                )
            ]

        logger.info(f"Downloading yt-dlp asset for query '{query}'...")

        video_info = self._get_video_info(query)

        cmd = [
            sys.executable,
            "-m",
            "yt_dlp",
            f"ytsearch1:{query}",
            "-f",
            "bestvideo[height<=1080][ext=mp4]/bestvideo[height<=1080][ext=webm]/best[height<=1080]/best",
            "-o",
            str(target_file),
            "--no-playlist",
            "--merge-output-format",
            "mp4",
        ]

        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=180,
                encoding="utf-8",
            )
            if target_file.exists():
                logger.info(f"Successfully downloaded: {target_file}")
                metadata = self._write_metadata(target_file, query, video_info)
                self._ingest_to_database(target_file, metadata, video_info)
                return [
                    AssetResult(
                        asset_path=target_file,
                        score=1.0,
                        source="youtube",
                        description=query,
                        asset_type="video",
                    )
                ]
        except Exception as e:
            logger.warning(
                f"Failed to download asset for query '{query}': {e}. Using fallback."
            )

        return [
            AssetResult(
                asset_path=self.fallback_asset,
                score=0.0,
                source="fallback",
                asset_type="image",
            )
        ]
