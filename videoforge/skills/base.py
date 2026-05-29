from __future__ import annotations

from abc import ABC, abstractmethod

from videoforge.models import (
    AssetMetadata,
    AssetResult,
    QAResult,
    RenderResult,
    Script,
    SubtitleResult,
    TTSResult,
    TimestampResult,
)


class ScriptWriterSkill(ABC):
    """编剧 Skill：输入知识点，输出结构化分镜脚本"""

    @abstractmethod
    def generate(self, topic: str, knowledge_points: list[str], **kwargs) -> Script:
        ...


class TTSSkill(ABC):
    """配音生成 Skill"""

    @abstractmethod
    def generate(self, text: str, voice: str | None = None, **kwargs) -> TTSResult:
        ...


class TimestampAlignSkill(ABC):
    """字级时间戳对齐 Skill"""

    @abstractmethod
    def align(self, audio_path: str, text: str, **kwargs) -> TimestampResult:
        ...


class AssetSearchSkill(ABC):
    """素材检索 Skill"""

    @abstractmethod
    def search(self, query: str, top_k: int = 5, **kwargs) -> list[AssetResult]:
        ...


class AssetTagSkill(ABC):
    """素材打标 Skill"""

    @abstractmethod
    def tag(self, asset_path: str, **kwargs) -> AssetMetadata:
        ...


class VideoRenderSkill(ABC):
    """视频渲染 Skill"""

    @abstractmethod
    def render(self, template: str, data: dict, **kwargs) -> RenderResult:
        ...


class SubtitleExportSkill(ABC):
    """字幕导出 Skill"""

    @abstractmethod
    def export(self, timestamps: TimestampResult, output_path: str, **kwargs) -> SubtitleResult:
        ...


class QACheckSkill(ABC):
    """质量验证 Skill"""

    @abstractmethod
    def check(self, video_path: str, **kwargs) -> QAResult:
        ...
