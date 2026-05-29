import logging
import subprocess
from pathlib import Path
import time
import sys

from videoforge.models import TTSResult
from videoforge.skills.base import TTSSkill

logger = logging.getLogger(__name__)


class EdgeTTSProvider(TTSSkill):
    """基于 edge-tts 的配音生成，同时生成 VTT 字幕供后续对齐使用"""
    
    def __init__(self, config: dict):
        self.config = config.get("edge_tts", {})
        self.voice = self.config.get("voice", "zh-CN-YunxiNeural")
        
    def generate(self, text: str, voice: str | None = None, **kwargs) -> TTSResult:
        actual_voice = voice or self.voice
        
        # 准备输出目录
        output_dir = Path("output/audio")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp_str = str(int(time.time() * 1000))
        audio_path = output_dir / f"tts_{timestamp_str}.mp3"
        vtt_path = output_dir / f"tts_{timestamp_str}.vtt"
        text_path = output_dir / f"tts_{timestamp_str}.txt"
        
        # 写入文本文件，避免 Windows 命令行编码问题
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(text)
        
        logger.info(f"Generating TTS using voice {actual_voice} via CLI...")
        
        # 使用 CLI 调用 edge-tts
        cmd = [
            sys.executable, "-m", "edge_tts",
            "--file", str(text_path),
            "--voice", actual_voice,
            "--write-media", str(audio_path),
            "--write-subtitles", str(vtt_path)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8")
        except subprocess.CalledProcessError as e:
            logger.error(f"edge-tts failed: {e.stderr}")
            raise RuntimeError(f"TTS generation failed: {e.stderr}") from e
            
        logger.info(f"TTS generated: {audio_path}")
        logger.info(f"VTT generated: {vtt_path}")
        
        # 获取音频的大致总时长 (从 VTT 最后一个时间戳获取)
        duration = 0.0
        
        return TTSResult(
            audio_path=audio_path,
            duration_sec=duration,
            text=text
        )
