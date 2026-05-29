from __future__ import annotations

from videoforge.models import SubtitleResult
from videoforge.skills.base import SubtitleExportSkill


class SRTExporter(SubtitleExportSkill):
    def __init__(self, config: dict) -> None:
        self.config = config

    def export(self, data: dict) -> SubtitleResult:
        """Export subtitles in SRT format."""
        raise NotImplementedError
