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


class AssetDownloadError(Exception):
    """素材下载失败时抛出的异常"""
    pass


class YTDLPSearchProvider(AssetSearchSkill):
    """基于 yt-dlp 的 YouTube B-roll 检索与下载，自带本地缓存、元数据 sidecar 和数据库入库"""

    def __init__(self, config: dict):
        self.config = config.get("ytdlp", {})
        self.assets_dir = Path("output/assets")
        self.assets_dir.mkdir(parents=True, exist_ok=True)

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
        """利用 yt-dlp 搜索 YouTube 并在本地缓存

        如果下载失败，会抛出 AssetDownloadError 异常，而不是静默返回 fallback。
        这遵循 fail-fast 原则，避免产出黑屏视频。
        """
        if not query.strip():
            raise AssetDownloadError("Empty query provided")

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
            result = subprocess.run(
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
            else:
                raise AssetDownloadError(
                    f"yt-dlp completed but file not found: {target_file}"
                )
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            raise AssetDownloadError(
                f"Failed to download asset for query '{query}': {error_msg}"
            ) from e
        except subprocess.TimeoutExpired:
            raise AssetDownloadError(
                f"Download timed out for query '{query}' (180s limit)"
            )
        except Exception as e:
            raise AssetDownloadError(
                f"Unexpected error downloading asset for query '{query}': {e}"
            ) from e
