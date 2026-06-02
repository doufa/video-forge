"""
VideoForge Demo: 食盐在水中的溶解过程

这个脚本演示 VideoForge 的完整视频生产流程：
1. 编剧 - LLM 生成结构化分镜脚本
2. 配音 - Edge-TTS 生成中文语音
3. 时间戳对齐 - WhisperX 获取字级时间戳
4. 素材检索 - YouTube 自动搜索下载相关视频
5. 渲染合成 - HyperFrames 生成最终 MP4

使用前请确保：
1. 安装依赖: pip install -e .
2. 安装 HyperFrames: npm install hyperframes
3. 配置 .env 文件（LLM API Key）
"""

import logging
import sys
from pathlib import Path

from videoforge.config import load_config
from videoforge.pipeline.runner import PipelineRunner
from videoforge.skills.asset_search.ytdlp_provider import YTDLPSearchProvider
from videoforge.skills.script_writer.deepseek_rag import DeepSeekRAGProvider
from videoforge.skills.timestamp_align.whisperx_provider import WhisperXProvider
from videoforge.skills.tts_generate.edge_tts_provider import EdgeTTSProvider
from videoforge.skills.video_render.hyperframes_provider import HyperFramesProvider

# 配置日志
sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


def main():
    print("=" * 60)
    print("  VideoForge Demo - 食盐在水中的溶解过程")
    print("=" * 60)

    # ========== 1. 定义主题和知识点 ==========
    topic = "食盐在水中的溶解过程"

    knowledge_points = [
        "食盐的化学成分是氯化钠，由钠离子和氯离子组成",
        "水分子是极性分子，氧端带负电，氢端带正电",
        "水分子包围并拉扯晶体表面的离子，这叫水合作用",
        "钠离子和氯离子被水分子包围，脱离晶格进入溶液",
        "溶解是可逆的，达到饱和后不再溶解更多食盐",
    ]

    print(f"\n📚 主题: {topic}")
    print(f"📝 知识点数量: {len(knowledge_points)}")
    for i, point in enumerate(knowledge_points, 1):
        print(f"   {i}. {point}")

    # ========== 2. 加载配置 ==========
    print("\n🔧 加载配置...")
    config = load_config()
    skills_config = config.get("skills", {})

    # ========== 3. 初始化各 Provider ==========
    print("🚀 初始化 Pipeline 组件...")

    script_writer = DeepSeekRAGProvider(skills_config.get("script_writer", {}))
    print("   ✓ 编剧模块 (DeepSeek RAG)")

    tts_generator = EdgeTTSProvider(skills_config.get("tts_generate", {}))
    print("   ✓ 配音模块 (Edge-TTS)")

    aligner = WhisperXProvider(skills_config.get("timestamp_align", {}))
    print("   ✓ 时间戳对齐模块 (WhisperX)")

    asset_search = YTDLPSearchProvider(skills_config.get("asset_search", {}))
    print("   ✓ 素材检索模块 (yt-dlp)")

    video_render = HyperFramesProvider(skills_config.get("video_render", {}))
    print("   ✓ 渲染模块 (HyperFrames)")

    # ========== 4. 创建 Pipeline Runner ==========
    runner = PipelineRunner(
        script_writer=script_writer,
        tts_generator=tts_generator,
        aligner=aligner,
        asset_search=asset_search,
        video_render=video_render
    )

    # ========== 5. 执行全链路生产 ==========
    print("\n" + "=" * 60)
    print("  开始视频生产流水线")
    print("=" * 60)

    try:
        state = runner.run(topic, knowledge_points)

        # ========== 6. 输出结果 ==========
        print("\n" + "=" * 60)
        print("  ✅ 视频生产完成!")
        print("=" * 60)

        if state.render_result:
            video_path = Path(state.render_result.video_path)
            print(f"\n📹 输出视频: {video_path}")
            print(f"   文件大小: {video_path.stat().st_size / 1024 / 1024:.1f} MB")

        if state.script:
            print(f"\n📄 脚本场景数: {len(state.script.scenes)}")
            for scene in state.script.scenes:
                print(f"   Scene {scene.index}: {scene.narration[:30]}...")

        print(f"\n🎵 生成的音频文件: {len(state.tts_results)}")
        print(f"🎬 下载的素材: {sum(len(v) for v in state.assets.values())}")

    except Exception as e:
        logger.error(f"Pipeline 执行失败: {e}")
        raise


if __name__ == "__main__":
    main()
