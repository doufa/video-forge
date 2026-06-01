from __future__ import annotations

import logging
import re
import subprocess
import sys
from pathlib import Path

from videoforge.models import AssetResult
from videoforge.skills.base import AssetSearchSkill

logger = logging.getLogger(__name__)

class YTDLPSearchProvider(AssetSearchSkill):
    """基于 yt-dlp 的 YouTube B-roll 检索与下载，自带本地缓存"""

    def __init__(self, config: dict):
        self.config = config.get("ytdlp", {})
        self.assets_dir = Path("output/assets")
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        # 默认使用通用 fallback 图片/视频
        self.fallback_asset = self.assets_dir / "fallback.jpg"
        self._ensure_fallback_asset()

    def _ensure_fallback_asset(self):
        """确保存在一个兜底的本地素材"""
        if not self.fallback_asset.exists():
            # 这里简单生成一个纯色黑底图作为后备（需要 ffmpeg 或者 simply mock a fake file, but a real file is better for HyperFrames if needed. 
            # 实际上由于 HyperFrames 是 Web 引擎，任何存在的 jpg 都可以作为占位。）
            # 我们用 python 写入一个极其简单的纯色 BMP 图片，改为 .jpg 结尾即可欺骗一些简单的检查，或者使用 base64 写入真实的小图片。
            # 为了简单起见，我们生成一个极简的 1x1 黑色 JPEG。
            logger.info("Creating fallback black image...")
            # 1x1 black JPEG hex
            black_jpg = bytes.fromhex(
                "ffd8ffe000104a46494600010101004800480000ffdb004300080606070605080707070909080a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c30313434341f27393d38323c2e333432ffdb0043010909090c0b0c180d0d1832211c213232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232ffc00011080001000103012200021101031101ffc4001f0000010501010101010100000000000000000102030405060708090a0bffc400b5100002010303020403050504040000017d01020300041105122131410613516107227114328191a1082342b1c11552d1f02433627282090a161718191a25262728292a3435363738393a434445464748494a535455565758595a636465666768696a737475767778797a838485868788898a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae1e2e3e4e5e6e7e8e9eaf1f2f3f4f5f6f7f8f9faffc4001f0100030101010101010101010000000000000102030405060708090a0bffc400b51100020102040403040705040400010277000102031104052131061241510761711322328108144291a1b1c109233352f0156272d10a162434e125f11718191a262728292a35363738393a434445464748494a535455565758595a636465666768696a737475767778797a838485868788898a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae2e3e4e5e6e7e8e9eaf2f3f4f5f6f7f8f9faffda000c03010002110311003f00f9fe8a28a00f"
            )
            self.fallback_asset.write_bytes(black_jpg)

    def _slugify(self, text: str) -> str:
        """将搜索词转为合法的文件名"""
        text = text.lower()
        text = re.sub(r'[^a-z0-9]+', '_', text)
        return text.strip('_')

    def search(self, query: str, top_k: int = 1, **kwargs) -> list[AssetResult]:
        """
        利用 yt-dlp 搜索 YouTube 并在本地缓存。
        """
        if not query.strip():
            return [AssetResult(asset_path=self.fallback_asset, score=0.0, source="fallback", asset_type="image")]
            
        slug = self._slugify(query)
        # 使用 mp4 格式，兼容性更好
        safe_query = re.sub(r'[^\w\-_\. ]', '_', query)
        target_file = Path(self.assets_dir) / f"{safe_query}.mp4"

        # 检查本地缓存
        if target_file.exists():
            logger.info(f"Using cached asset for query '{query}': {target_file}")
            return [AssetResult(
                asset_path=target_file,
                score=1.0,
                source="local_cache",
                description=query,
                asset_type="video"
            )]
            
        logger.info(f"Downloading yt-dlp asset for query '{query}'...")
        # 调用 yt-dlp
        # 格式选择：优先 webm，fallback 到 mp4，确保大多数视频都能下载
        cmd = [
            sys.executable, "-m", "yt_dlp",
            f"ytsearch1:{query}",
            "-f", "bestvideo[height<=1080][ext=mp4]/bestvideo[height<=1080][ext=webm]/best[height<=1080]/best",
            "-o", str(target_file),
            "--no-playlist",
            "--merge-output-format", "mp4"  # 确保输出为 mp4 格式
        ]

        try:
            # timeout 避免一直卡住，设为 180 秒以适应 1080p 视频下载
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=180, encoding="utf-8")
            if target_file.exists():
                logger.info(f"Successfully downloaded: {target_file}")
                return [AssetResult(
                    asset_path=target_file,
                    score=1.0,
                    source="youtube",
                    description=query,
                    asset_type="video"
                )]
        except Exception as e:
            logger.warning(f"Failed to download asset for query '{query}': {e}. Using fallback.")
            
        # 降级返回 fallback
        return [AssetResult(asset_path=self.fallback_asset, score=0.0, source="fallback", asset_type="image")]
