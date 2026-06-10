from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from videoforge.models import (
    AssetResult,
    RenderResult,
    Script,
    TimestampResult,
    TTSResult,
)
from videoforge.skills.base import (
    AssetSearchSkill,
    AssetTagSkill,
    ScriptWriterSkill,
    TimestampAlignSkill,
    TTSSkill,
    VideoRenderSkill,
)

logger = logging.getLogger(__name__)


@dataclass
class PipelineState:
    """Pipeline 执行状态，各 Skill 间通过此对象传递数据"""
    topic: str = ""
    knowledge_points: list[str] = field(default_factory=list)

    # 各阶段的输出
    script: Script | None = None
    tts_results: list[TTSResult] = field(default_factory=list)
    timestamps: list[TimestampResult] = field(default_factory=list)
    assets: dict[int, list[AssetResult]] = field(default_factory=dict)  # scene_index -> assets
    render_result: RenderResult | None = None

    errors: list[str] = field(default_factory=list)


class PipelineRunner:
    """顺序执行 pipeline 各阶段的调度器"""

    def __init__(
        self,
        script_writer: ScriptWriterSkill,
        tts_generator: TTSSkill,
        aligner: TimestampAlignSkill,
        asset_search: AssetSearchSkill,
        video_render: VideoRenderSkill,
    ):
        self.script_writer = script_writer
        self.tts_generator = tts_generator
        self.aligner = aligner
        self.asset_search = asset_search
        self.video_render = video_render

    def run(self, topic: str, knowledge_points: list[str]) -> PipelineState:
        state = PipelineState(topic=topic, knowledge_points=knowledge_points)

        try:
            # 1. 编剧
            logger.info("=== Stage 1: Script Writing ===")
            state.script = self.script_writer.generate(topic, knowledge_points)

            # 2 & 3. 逐场景生成配音与时间戳
            logger.info("=== Stage 2 & 3: TTS and Alignment ===")
            for i, scene in enumerate(state.script.scenes):
                if i > 0:
                    time.sleep(2)  # 避免 edge-tts 限流
                logger.info(f"Processing TTS for scene {scene.index}...")
                tts_res = self.tts_generator.generate(scene.narration)
                state.tts_results.append(tts_res)

                # 获取字级对齐
                align_res = self.aligner.align(str(tts_res.audio_path), scene.narration)
                state.timestamps.append(align_res)

            # 4. 素材检索
            logger.info("=== Stage 4: Asset Search ===")
            for scene in state.script.scenes:
                logger.info(f"Searching assets for scene {scene.index}: {scene.asset_keywords}")
                
                # 提取关键字（只用第一个，如果 yt-dlp 太复杂的话；这里将关键词拼成一个长句或者选第一个）
                query = " ".join(scene.asset_keywords) if scene.asset_keywords else topic
                assets = self.asset_search.search(query, top_k=1)
                state.assets[scene.index] = assets

            # 5. 构建渲染载荷与渲染
            logger.info("=== Stage 5: Video Render ===")
            render_data = self._build_render_data(state)
            state.render_result = self.video_render.render("main_template", render_data)

            logger.info(f"Pipeline completed successfully! Video saved to: {state.render_result.video_path}")

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            state.errors.append(str(e))
            raise

        return state

    def _build_render_data(self, state: PipelineState) -> dict:
        """组装给 HyperFrames 的渲染数据"""
        data = {
            "title": state.script.title,
            "scenes": []
        }
        
        current_time = 0.0
        
        for i, scene in enumerate(state.script.scenes):
            tts = state.tts_results[i]
            ts = state.timestamps[i]
            assets = state.assets.get(scene.index, [])
            
            # 计算该场景的时长（根据 VTT 的最后一个字结束时间计算）
            scene_duration = 5.0 # default
            if ts.words:
                scene_duration = ts.words[-1].end_sec + 0.5 # 留半秒余量
            
            # 格式化时间戳，给字幕引擎使用
            words_data = [{"word": w.word, "start": w.start_sec, "end": w.end_sec} for w in ts.words]

            # 构建路径（使用正斜杠，兼容 HyperFrames 的 file:// 协议）
            asset_path = str(assets[0].asset_path).replace("\\", "/") if assets else "fallback.jpg"
            audio_path = str(tts.audio_path).replace("\\", "/") if tts else ""

            scene_data = {
                "index": scene.index,
                "narration": scene.narration,
                "asset_path": asset_path,
                "audio_path": audio_path,
                "duration": scene_duration,
                "start_time": current_time, # 在整个视频中的开始时间
                "words": words_data
            }
            
            data["scenes"].append(scene_data)
            current_time += scene_duration
            
        data["total_duration"] = current_time
        return data
