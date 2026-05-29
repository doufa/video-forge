from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ScriptScene:
    """分镜表中的一个场景"""
    index: int
    narration: str                          # 旁白文本
    asset_keywords: list[str]               # 素材检索关键词
    duration_hint: float | None = None      # 建议时长（秒），None 表示由 TTS 决定
    notes: str = ""                          # 备注（特效、转场等指示）


@dataclass
class Script:
    """结构化分镜脚本"""
    title: str
    scenes: list[ScriptScene]
    style: str = ""                          # 风格参考
    total_duration_hint: float | None = None


@dataclass
class TTSResult:
    """TTS 配音结果"""
    audio_path: Path
    duration_sec: float
    text: str                                # 原始文本


@dataclass
class WordTimestamp:
    """单个词的时间戳"""
    word: str
    start_sec: float
    end_sec: float


@dataclass
class TimestampResult:
    """字级时间戳对齐结果"""
    audio_path: Path
    words: list[WordTimestamp]


@dataclass
class AssetResult:
    """素材检索结果"""
    asset_path: Path
    score: float                             # 匹配分数 0-1
    source: str                              # "local" | "youtube" | "pexels"
    description: str = ""
    asset_type: str = "video"                # "video" | "image"


@dataclass
class AssetMetadata:
    """素材打标元数据"""
    asset_path: Path
    description: str
    tags: list[str]
    embedding: list[float] = field(default_factory=list)
    reviewed: bool = False


@dataclass
class RenderResult:
    """渲染结果"""
    video_path: Path
    duration_sec: float
    resolution: str                          # e.g. "1920x1080"


@dataclass
class SubtitleResult:
    """字幕导出结果"""
    srt_path: Path
    word_count: int


@dataclass
class QAIssue:
    """QA 发现的问题"""
    level: str                               # "basic" | "sync" | "semantic"
    description: str
    timestamp_sec: float | None = None
    severity: str = "warning"                # "warning" | "error"


@dataclass
class QAResult:
    """质量验证结果"""
    passed: bool
    issues: list[QAIssue] = field(default_factory=list)
    score: float = 1.0                       # 0-1 综合质量分
