import logging
import re
from pathlib import Path

from videoforge.models import TimestampResult, WordTimestamp
from videoforge.skills.base import TimestampAlignSkill

logger = logging.getLogger(__name__)


class WhisperXProvider(TimestampAlignSkill):
    """
    轻量级时间戳对齐实现 (原设计为 WhisperX)。
    在 MVP 阶段，由于我们采用了 Edge-TTS，可以直接解析与其同名的 .vtt 字幕文件来获取词组级时间戳，
    从而彻底免去 PyTorch + CUDA 环境的配置要求。
    """
    
    def __init__(self, config: dict):
        self.config = config.get("whisperx", {})
        
    def _parse_vtt_time(self, time_str: str) -> float:
        """解析 VTT 时间戳 '00:00:01.234' 为秒数 1.234"""
        parts = time_str.strip().split(':')
        if len(parts) == 3:
            h, m, s = parts
        elif len(parts) == 2:
            h = 0
            m, s = parts
        else:
            return 0.0
            
        return int(h) * 3600 + int(m) * 60 + float(s)

    def align(self, audio_path: str, text: str, **kwargs) -> TimestampResult:
        logger.info(f"Aligning timestamps for: {audio_path}")
        audio_p = Path(audio_path)
        
        # 寻找同名 VTT 文件 (由 EdgeTTSProvider 生成)
        vtt_path = audio_p.with_suffix('.vtt')
        words = []
        
        if vtt_path.exists():
            logger.info(f"Found VTT file: {vtt_path}, parsing timestamps...")
            with open(vtt_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            # 简单的 VTT 正则解析
            # 格式例如:
            # 00:00:00.100 --> 00:00:01.500 (VTT) 或 00:00:00,100 --> 00:00:01,500 (SRT)
            pattern = re.compile(r"(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})\n(.*?)(?=\n\n|\Z)", re.DOTALL)
            
            for match in pattern.finditer(content):
                start_str, end_str, word_text = match.groups()
                word_text = word_text.strip()
                if not word_text:
                    continue
                    
                start_str = start_str.replace(',', '.')
                end_str = end_str.replace(',', '.')
                
                start_sec = self._parse_vtt_time(start_str)
                end_sec = self._parse_vtt_time(end_str)
                
                words.append(WordTimestamp(
                    word=word_text,
                    start_sec=start_sec,
                    end_sec=end_sec
                ))
        else:
            logger.warning(f"No VTT file found at {vtt_path}. Falling back to single chunk.")
            # 兜底方案：如果没有找到 VTT，将整句话作为一个整体 (假定 0-5 秒)
            words.append(WordTimestamp(
                word=text,
                start_sec=0.0,
                end_sec=5.0 
            ))
            
        return TimestampResult(
            audio_path=audio_p,
            words=words
        )
