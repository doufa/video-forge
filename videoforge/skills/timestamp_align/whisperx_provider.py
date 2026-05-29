from __future__ import annotations

from videoforge.models import TimestampResult
from videoforge.skills.base import TimestampAlignSkill


class WhisperXProvider(TimestampAlignSkill):
    def __init__(self, config: dict) -> None:
        self.config = config

    def align(self, audio_path: str) -> TimestampResult:
        """Align timestamps for audio using WhisperX."""
        raise NotImplementedError
