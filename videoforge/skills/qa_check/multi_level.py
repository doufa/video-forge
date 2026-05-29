from __future__ import annotations

from videoforge.models import QAResult
from videoforge.skills.base import QACheckSkill


class MultiLevelQAProvider(QACheckSkill):
    def __init__(self, config: dict) -> None:
        self.config = config

    def check(self, data: dict) -> QAResult:
        """Run multi-level QA checks."""
        raise NotImplementedError
