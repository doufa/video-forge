from __future__ import annotations

from videoforge.models import TTSResult
from videoforge.skills.base import TTSSkill


class EdgeTTSProvider(TTSSkill):
    def __init__(self, config: dict) -> None:
        self.config = config

    def generate(self, text: str) -> TTSResult:
        """Generate TTS audio from text using Edge TTS."""
        raise NotImplementedError
