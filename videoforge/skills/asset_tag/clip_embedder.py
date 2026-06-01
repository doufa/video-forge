"""CLIP 向量提取器

从视频/图片中提取 CLIP 向量，用于语义相似度检索。
支持懒加载模型，如果依赖不可用则降级为纯文本向量。
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger(__name__)

_clip_model = None
_clip_preprocess = None
_clip_available = None


def _check_clip_available() -> bool:
    """检查 CLIP 依赖是否可用"""
    global _clip_available
    if _clip_available is not None:
        return _clip_available
    try:
        import clip
        import torch
        _clip_available = True
    except ImportError:
        _clip_available = False
        logger.warning("CLIP dependencies not available. Install with: pip install git+https://github.com/openai/CLIP.git torch")
    return _clip_available


def _load_clip_model(model_name: str = "ViT-B/32"):
    """懒加载 CLIP 模型"""
    global _clip_model, _clip_preprocess
    if _clip_model is not None:
        return _clip_model, _clip_preprocess

    if not _check_clip_available():
        return None, None

    import clip
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Loading CLIP model {model_name} on {device}...")
    _clip_model, _clip_preprocess = clip.load(model_name, device=device)
    return _clip_model, _clip_preprocess


def extract_keyframes(video_path: str | Path, num_frames: int = 3) -> list[Path]:
    """从视频中提取关键帧（首/中/尾）

    Args:
        video_path: 视频文件路径
        num_frames: 提取帧数，默认3帧

    Returns:
        临时帧文件路径列表
    """
    video_path = Path(video_path)
    if not video_path.exists():
        return []

    import tempfile
    temp_dir = Path(tempfile.mkdtemp(prefix="clip_frames_"))

    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path)
            ],
            capture_output=True, text=True, timeout=30
        )
        duration = float(result.stdout.strip()) if result.stdout.strip() else 10.0
    except Exception:
        duration = 10.0

    frame_paths = []
    timestamps = [0.5]
    if num_frames >= 2:
        timestamps.append(duration / 2)
    if num_frames >= 3:
        timestamps.append(max(duration - 1, 0.5))

    for i, ts in enumerate(timestamps[:num_frames]):
        frame_path = temp_dir / f"frame_{i}.jpg"
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-ss", str(ts),
                    "-i", str(video_path),
                    "-frames:v", "1",
                    "-q:v", "2",
                    str(frame_path)
                ],
                capture_output=True, timeout=30
            )
            if frame_path.exists():
                frame_paths.append(frame_path)
        except Exception as e:
            logger.debug(f"Failed to extract frame at {ts}s: {e}")

    return frame_paths


def get_image_embedding(image_path: str | Path) -> np.ndarray | None:
    """提取单张图片的 CLIP 向量

    Returns:
        512维向量 (ViT-B/32) 或 None
    """
    model, preprocess = _load_clip_model()
    if model is None:
        return None

    import torch
    from PIL import Image

    try:
        image = preprocess(Image.open(image_path)).unsqueeze(0)
        device = next(model.parameters()).device
        image = image.to(device)

        with torch.no_grad():
            embedding = model.encode_image(image)
            embedding = embedding / embedding.norm(dim=-1, keepdim=True)
            return embedding.cpu().numpy().flatten()
    except Exception as e:
        logger.error(f"Failed to get image embedding: {e}")
        return None


def get_text_embedding(text: str) -> np.ndarray | None:
    """提取文本的 CLIP 向量

    Returns:
        512维向量 (ViT-B/32) 或 None
    """
    model, _ = _load_clip_model()
    if model is None:
        return None

    import clip
    import torch

    try:
        device = next(model.parameters()).device
        text_tokens = clip.tokenize([text], truncate=True).to(device)

        with torch.no_grad():
            embedding = model.encode_text(text_tokens)
            embedding = embedding / embedding.norm(dim=-1, keepdim=True)
            return embedding.cpu().numpy().flatten()
    except Exception as e:
        logger.error(f"Failed to get text embedding: {e}")
        return None


def get_video_embedding(video_path: str | Path, num_frames: int = 3) -> np.ndarray | None:
    """提取视频的 CLIP 向量（多帧平均）

    Args:
        video_path: 视频路径
        num_frames: 采样帧数

    Returns:
        512维向量 或 None
    """
    frame_paths = extract_keyframes(video_path, num_frames)
    if not frame_paths:
        logger.warning(f"No frames extracted from {video_path}")
        return None

    embeddings = []
    for frame_path in frame_paths:
        emb = get_image_embedding(frame_path)
        if emb is not None:
            embeddings.append(emb)
        frame_path.unlink(missing_ok=True)

    if frame_paths and frame_paths[0].parent.exists():
        try:
            frame_paths[0].parent.rmdir()
        except OSError:
            pass

    if not embeddings:
        return None

    mean_embedding = np.mean(embeddings, axis=0)
    mean_embedding = mean_embedding / np.linalg.norm(mean_embedding)
    return mean_embedding.astype(np.float32)


def get_asset_embedding(asset_path: str | Path) -> np.ndarray | None:
    """根据资产类型提取 CLIP 向量"""
    path = Path(asset_path)
    ext = path.suffix.lower()

    video_exts = {".mp4", ".webm", ".mkv", ".mov", ".avi"}
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

    if ext in video_exts:
        return get_video_embedding(path)
    elif ext in image_exts:
        return get_image_embedding(path)
    else:
        logger.warning(f"Unsupported asset type: {ext}")
        return None


def is_clip_available() -> bool:
    """检查 CLIP 是否可用"""
    return _check_clip_available()


def get_embedding_dim() -> int:
    """返回向量维度"""
    return 512  # ViT-B/32
