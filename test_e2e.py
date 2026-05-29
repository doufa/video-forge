import logging
import sys

from videoforge.config import load_config
from videoforge.pipeline.runner import PipelineRunner
from videoforge.skills.asset_search.ytdlp_provider import YTDLPSearchProvider
from videoforge.skills.script_writer.deepseek_rag import DeepSeekRAGProvider
from videoforge.skills.timestamp_align.whisperx_provider import WhisperXProvider
from videoforge.skills.tts_generate.edge_tts_provider import EdgeTTSProvider
from videoforge.skills.video_render.hyperframes_provider import HyperFramesProvider

sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def main():
    print("=== VideoForge E2E Pipeline ===")
    
    # 1. 加载配置
    config = load_config()
    skills_config = config.get("skills", {})
    
    # 2. 初始化 Providers
    print("\n--- 初始化 Pipeline Runner ---")
    script_writer = DeepSeekRAGProvider(skills_config.get("script_writer", {}))
    tts_generator = EdgeTTSProvider(skills_config.get("tts_generate", {}))
    aligner = WhisperXProvider(skills_config.get("timestamp_align", {}))
    asset_search = YTDLPSearchProvider(skills_config.get("asset_search", {}))
    video_render = HyperFramesProvider(skills_config.get("video_render", {}))
    
    runner = PipelineRunner(
        script_writer=script_writer,
        tts_generator=tts_generator,
        aligner=aligner,
        asset_search=asset_search,
        video_render=video_render
    )
    
    # 3. 执行端到端生产
    topic = "为什么说光速无法超越？"
    points = [
        "光速是宇宙中的速度极限",
        "根据相对论，物体越快质量越大",
        "达到光速需要无穷大的能量",
        "除非静止质量为零（如光子）"
    ]
    
    print(f"\n--- 开始全链路视频生产：{topic} ---")
    state = runner.run(topic, points)
    
    print("\n=== E2E Test Completed ===")
    if state.render_result:
        print(f"最终视频输出路径: {state.render_result.video_path}")
    else:
        print("渲染失败！请检查错误日志。")

if __name__ == "__main__":
    main()
