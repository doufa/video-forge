"""
VideoForge Demo: 食盐为什么会消失在水中（使用本地素材库）

使用本地已有的素材，不从 YouTube 下载。
"""

import logging
import sys
from pathlib import Path

from videoforge.config import load_config
from videoforge.pipeline.runner import PipelineRunner
from videoforge.skills.asset_search.local_faiss import LocalFAISSProvider
from videoforge.skills.script_writer.deepseek_rag import DeepSeekRAGProvider
from videoforge.skills.timestamp_align.whisperx_provider import WhisperXProvider
from videoforge.skills.tts_generate.edge_tts_provider import EdgeTTSProvider
from videoforge.skills.video_render.hyperframes_provider import HyperFramesProvider

sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    print("=" * 60)
    print("  VideoForge Demo - 食盐为什么会消失在水中")
    print("  (使用本地素材库)")
    print("=" * 60)

    topic = "食盐为什么会消失在水中"

    knowledge_points = [
        "食盐的化学成分是氯化钠，由钠离子和氯离子通过离子键紧密结合",
        "水分子是极性分子，氧端带负电荷，氢端带正电荷",
        "水分子的正极吸引氯离子，负极吸引钠离子，这叫水合作用",
        "水分子不断拉扯晶体表面的离子，直到它们脱离晶格进入溶液",
        "溶解是可逆过程，饱和溶液中溶解和结晶达到动态平衡",
    ]

    print(f"\n📚 主题: {topic}")
    print(f"📝 知识点: {len(knowledge_points)} 个")
    for i, point in enumerate(knowledge_points, 1):
        print(f"   {i}. {point}")

    config = load_config()
    skills_config = config.get("skills", {})

    print("\n🚀 初始化组件...")
    script_writer = DeepSeekRAGProvider(skills_config.get("script_writer", {}))
    print("   ✓ 编剧 (DeepSeek RAG)")

    tts_generator = EdgeTTSProvider(skills_config.get("tts_generate", {}))
    print("   ✓ 配音 (Edge-TTS)")

    aligner = WhisperXProvider(skills_config.get("timestamp_align", {}))
    print("   ✓ 对齐 (WhisperX)")

    # 使用本地 FAISS 检索，不从 YouTube 下载
    asset_search_config = skills_config.get("asset_search", {}).copy()
    asset_search_config["fallback"] = None  # 禁用在线兜底
    asset_search = LocalFAISSProvider(asset_search_config)
    print("   ✓ 素材 (本地 FAISS)")

    video_render = HyperFramesProvider(skills_config.get("video_render", {}))
    print("   ✓ 渲染 (HyperFrames)")

    runner = PipelineRunner(
        script_writer=script_writer,
        tts_generator=tts_generator,
        aligner=aligner,
        asset_search=asset_search,
        video_render=video_render,
    )

    print("\n" + "=" * 60)
    print("  开始生产")
    print("=" * 60)

    try:
        state = runner.run(topic, knowledge_points)

        print("\n" + "=" * 60)
        print("  ✅ 完成!")
        print("=" * 60)

        if state.render_result:
            video_path = Path(state.render_result.video_path)
            print(f"\n📹 输出: {video_path}")
            if video_path.exists():
                print(f"   大小: {video_path.stat().st_size / 1024 / 1024:.1f} MB")

        if state.script:
            print(f"\n📄 场景数: {len(state.script.scenes)}")
            for scene in state.script.scenes:
                print(f"   [{scene.index}] {scene.narration[:40]}...")

        print(f"\n🎵 音频: {len(state.tts_results)} 个")
        print(f"🎬 素材: {sum(len(v) for v in state.assets.values())} 个")

    except Exception as e:
        logger.error(f"失败: {e}")
        raise


if __name__ == "__main__":
    main()
