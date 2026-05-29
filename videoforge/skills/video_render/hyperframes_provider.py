import json
import logging
import shutil
import subprocess
from pathlib import Path

from videoforge.models import RenderResult
from videoforge.skills.base import VideoRenderSkill

logger = logging.getLogger(__name__)


class HyperFramesProvider(VideoRenderSkill):
    """视频渲染 Skill - 基于 HyperFrames 实现"""

    def __init__(self, config: dict):
        self.config = config
        self.hyperframes_version = config.get("hyperframes_version", "0.6.55")

    def render(self, template: str, data: dict, **kwargs) -> RenderResult:
        """
        根据 HTML 模板和注入的数据，调用 hyperframes CLI 渲染视频。
        """
        # 确定模板目录
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        template_dir = project_root / "templates" / "hyperframes" / template
        
        if not template_dir.exists():
            raise FileNotFoundError(f"Template directory not found: {template_dir}")

        # 临时工作区 (可以将数据注入到模板目录，但在生产环境应复制到临时目录)
        # 为 MVP，我们直接在 template 目录下运行，将数据写为一个 data.json 给 HTML 读取
        data_file = template_dir / "data.js"
        
        # 处理 data 中的 pathlib.Path 对象以便 JSON 序列化
        def serialize_paths(obj):
            if isinstance(obj, Path):
                return str(obj.absolute())
            if isinstance(obj, dict):
                return {k: serialize_paths(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [serialize_paths(v) for v in obj]
            if hasattr(obj, '__dict__'):
                return serialize_paths(obj.__dict__)
            return obj

        serialized_data = serialize_paths(data)
        with open(data_file, "w", encoding="utf-8") as f:
            f.write("window.__VIDEOFORGE_DATA__ = ")
            json.dump(serialized_data, f, ensure_ascii=False, indent=2)
            f.write(";\n")

        logger.info(f"Rendering template {template}...")
        
        cmd = [
            "npx", 
            "--yes", 
            f"hyperframes@{self.hyperframes_version}", 
            "render",
        ]
        
        try:
            process = subprocess.run(
                cmd,
                cwd=str(template_dir),
                check=True,
                capture_output=True,
                text=True,
                shell=True,
                encoding="utf-8",
                errors="replace"
            )
            logger.info("HyperFrames output:\n" + (process.stdout or ""))
        except subprocess.CalledProcessError as e:
            logger.error("HyperFrames render failed:\n" + e.stderr)
            raise RuntimeError(f"Render failed: {e.stderr}") from e

        renders_dir = template_dir / "renders"
        if not renders_dir.exists():
            raise FileNotFoundError(f"Renders directory not found: {renders_dir}")
            
        mp4_files = list(renders_dir.glob("*.mp4"))
        if not mp4_files:
            raise FileNotFoundError(f"No rendered mp4 found in {renders_dir}")
            
        output_mp4 = max(mp4_files, key=lambda p: p.stat().st_mtime)
        final_output = project_root / "output" / f"{template}_output.mp4"
        
        # 使用 ffmpeg 将各个场景的音频合并到视频中
        # 视频本身有3秒的片头（根据 index.html 的设定）
        scenes = serialized_data.get("scenes", [])
        if not scenes:
            shutil.copy2(output_mp4, final_output)
            return RenderResult(video_path=final_output, duration_sec=serialized_data.get("total_duration", 0), resolution="1920x1080")
            
        logger.info("Muxing audio with ffmpeg...")
        ffmpeg_cmd = ["ffmpeg", "-y", "-i", str(output_mp4)]
        
        filter_complex = []
        amix_inputs = []
        
        # 视频是输入 0
        for i, scene in enumerate(scenes):
            audio_path = scene.get("audio_path")
            if not audio_path:
                continue
                
            ffmpeg_cmd.extend(["-i", str(audio_path)])
            input_idx = len(amix_inputs) + 1 # 1-based audio inputs
            # index.html 中片头占了3秒，所以每个音频要延迟 start_time + 3 秒
            delay_ms = int((scene.get("start_time", 0) + 3.0) * 1000)
            
            # adelay expects delay in ms
            filter_complex.append(f"[{input_idx}:a]adelay={delay_ms}|{delay_ms}[a{input_idx}]")
            amix_inputs.append(f"[a{input_idx}]")
            
        if amix_inputs:
            inputs_str = "".join(amix_inputs)
            # amix defaults to 2 inputs, must specify inputs=N
            filter_complex.append(f"{inputs_str}amix=inputs={len(amix_inputs)}:duration=longest[aout]")
            ffmpeg_cmd.extend(["-filter_complex", ";".join(filter_complex)])
            ffmpeg_cmd.extend(["-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", str(final_output)])
            
            try:
                subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True, encoding="utf-8")
                logger.info(f"Muxing completed: {final_output}")
            except subprocess.CalledProcessError as e:
                logger.error(f"FFmpeg muxing failed: {e.stderr}")
                logger.info(f"Fallback to copying visual-only video to {final_output}")
                shutil.copy2(output_mp4, final_output)
        else:
            shutil.copy2(output_mp4, final_output)
        
        return RenderResult(
            video_path=final_output,
            duration_sec=serialized_data.get("total_duration", 0) + 3.0,
            resolution="1920x1080"
        )
