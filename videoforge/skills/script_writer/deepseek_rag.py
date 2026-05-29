from __future__ import annotations

from videoforge.models import Script
from videoforge.skills.base import ScriptWriterSkill


class DeepSeekRAGProvider(ScriptWriterSkill):
    def __init__(self, config: dict) -> None:
        self.config = config

    def generate(self, prompt: str) -> Script:
        """Generate a script from a prompt using DeepSeek RAG."""
        # TODO: implement DeepSeek RAG script generation
        raise NotImplementedError
