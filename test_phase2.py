import logging
import sys
from pprint import pprint

from videoforge.config import load_config
from videoforge.skills.script_writer.deepseek_rag import DeepSeekRAGProvider
from videoforge.skills.tts_generate.edge_tts_provider import EdgeTTSProvider
from videoforge.skills.timestamp_align.whisperx_provider import WhisperXProvider

sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def main():
    print("=== Phase 2 Pipeline Test ===")
    
    # 1. 加载配置
    config = load_config()
    
    # 2. 初始化 Providers
    print("\n--- 初始化 Providers ---")
    script_writer = DeepSeekRAGProvider(config.get("skills", {}).get("script_writer", {}))
    tts_generator = EdgeTTSProvider(config.get("skills", {}).get("tts_generate", {}))
    aligner = WhisperXProvider(config.get("skills", {}).get("timestamp_align", {}))
    
    # 3. 编剧 (Script Writer) 测试
    print("\n--- 1. Script Writer ---")
    topic = "量子力学里的薛定谔的猫是怎么回事？"
    points = [
        "薛定谔的猫是一个思想实验",
        "为了解释微观世界的叠加态",
        "盒子打开前，猫处于生与死的叠加状态",
        "观察者打开盒子的瞬间，状态坍缩"
    ]
    script = script_writer.generate(topic, points)
    print("\n[生成的脚本]")
    print(f"Title: {script.title}")
    print(f"Style: {script.style}")
    for i, scene in enumerate(script.scenes):
        print(f"Scene {scene.index}:")
        print(f"  旁白: {scene.narration}")
        print(f"  画面关键词: {scene.asset_keywords}")
        if i >= 1: # 仅打印前两个场景避免过长
            break
            
    # 取第一句旁白进行配音
    narration_text = script.scenes[0].narration
    print(f"\n--- 2. TTS Generation ---")
    print(f"Text to speech: {narration_text}")
    tts_result = tts_generator.generate(text=narration_text)
    
    print(f"Generated Audio Path: {tts_result.audio_path}")
    
    # 4. 时间戳对齐 (Timestamp Aligner) 测试
    print("\n--- 3. Timestamp Alignment ---")
    align_result = aligner.align(str(tts_result.audio_path), narration_text)
    print(f"Aligned Words count: {len(align_result.words)}")
    for word in align_result.words:
        print(f"  [{word.start_sec:.2f} -> {word.end_sec:.2f}] {word.word}")
        
    print("\n=== Test Completed ===")

if __name__ == "__main__":
    main()
