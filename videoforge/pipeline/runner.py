from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PipelineState:
    """Pipeline 执行状态，各 Skill 间通过此对象传递数据"""
    topic: str = ""
    knowledge_points: list[str] = field(default_factory=list)

    # 各阶段的输出，由对应 Skill 填充
    script: Any = None
    tts_results: list[Any] = field(default_factory=list)
    timestamps: list[Any] = field(default_factory=list)
    assets: dict[int, list[Any]] = field(default_factory=dict)  # scene_index -> assets
    render_result: Any = None
    subtitle_result: Any = None
    qa_result: Any = None

    # 错误追踪
    errors: list[str] = field(default_factory=list)


class PipelineRunner:
    """顺序执行 pipeline 各阶段的简单调度器"""

    def __init__(self, skills: dict[str, Any]):
        """
        Args:
            skills: Skill 名称到实例的映射，如 {"tts_generate": EdgeTTSProvider(...)}
        """
        self.skills = skills

    def run(self, topic: str, knowledge_points: list[str]) -> PipelineState:
        """执行完整 pipeline"""
        state = PipelineState(topic=topic, knowledge_points=knowledge_points)

        steps = [
            ("script_writer", self._step_script),
            ("tts_generate", self._step_tts),
            ("timestamp_align", self._step_timestamp),
            ("asset_search", self._step_assets),
            ("video_render", self._step_render),
            ("subtitle_export", self._step_subtitle),
            ("qa_check", self._step_qa),
        ]

        for step_name, step_fn in steps:
            if step_name not in self.skills:
                logger.warning("跳过未配置的 Skill: %s", step_name)
                continue
            try:
                logger.info("执行: %s", step_name)
                step_fn(state)
                logger.info("完成: %s", step_name)
            except Exception as e:
                error_msg = f"{step_name} 失败: {e}"
                logger.error(error_msg)
                state.errors.append(error_msg)
                break  # 顺序执行，失败即停止

        return state

    def _step_script(self, state: PipelineState) -> None:
        skill = self.skills["script_writer"]
        state.script = skill.generate(state.topic, state.knowledge_points)

    def _step_tts(self, state: PipelineState) -> None:
        skill = self.skills["tts_generate"]
        for scene in state.script.scenes:
            result = skill.generate(scene.narration)
            state.tts_results.append(result)

    def _step_timestamp(self, state: PipelineState) -> None:
        skill = self.skills["timestamp_align"]
        for tts_result in state.tts_results:
            result = skill.align(str(tts_result.audio_path), tts_result.text)
            state.timestamps.append(result)

    def _step_assets(self, state: PipelineState) -> None:
        skill = self.skills["asset_search"]
        for scene in state.script.scenes:
            query = " ".join(scene.asset_keywords)
            results = skill.search(query)
            state.assets[scene.index] = results

    def _step_render(self, state: PipelineState) -> None:
        skill = self.skills["video_render"]
        data = {
            "script": state.script,
            "tts_results": state.tts_results,
            "timestamps": state.timestamps,
            "assets": state.assets,
        }
        state.render_result = skill.render(template="default", data=data)

    def _step_subtitle(self, state: PipelineState) -> None:
        skill = self.skills["subtitle_export"]
        for ts in state.timestamps:
            state.subtitle_result = skill.export(ts, output_path="output/subtitles.srt")

    def _step_qa(self, state: PipelineState) -> None:
        skill = self.skills["qa_check"]
        state.qa_result = skill.check(str(state.render_result.video_path))
