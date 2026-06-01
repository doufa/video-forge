import json
import logging
import shutil
import subprocess
from pathlib import Path

from videoforge.models import RenderResult
from videoforge.skills.base import VideoRenderSkill

logger = logging.getLogger(__name__)

class HyperFramesProvider(VideoRenderSkill):
    """基于 HyperFrames CLI 的视频渲染实现"""

    def __init__(self, config: dict):
        if "skills" in config:
            video_render_config = config["skills"].get("video_render", {})
        elif "video_render" in config:
            video_render_config = config["video_render"]
        else:
            video_render_config = config
        
        self.config = video_render_config
        hf_config = video_render_config.get("hyperframes", {})
        self.templates_dir = hf_config.get("template_dir", "templates/hyperframes")
        self.resolution = hf_config.get("resolution", "1920x1080")
        self.project_root = video_render_config.get("project_root", str(Path.cwd()))

    def render(self, template_name: str, data: dict) -> RenderResult:
        """
        1. 将素材复制到模板 assets/ 目录
        2. 将数据写入 data.js
        3. 调用 hyperframes render
        4. 找到生成的视频并和音频混音
        """
        template_dir = Path(self.templates_dir) / template_name
        
        if not template_dir.exists():
            raise FileNotFoundError(f"Template directory not found: {template_dir}")

        # 模板的 assets 目录（hyperframes.json 中配置的路径）
        template_assets_dir = template_dir / "assets"
        template_assets_dir.mkdir(parents=True, exist_ok=True)

        scenes = data.get("scenes", [])

        # 1. 将素材复制到模板 assets/ 目录，替换路径为相对路径
        for i, scene in enumerate(scenes):
            if "asset_path" in scene and scene["asset_path"]:
                orig_asset = scene["asset_path"]
                
                # 跳过已经是远程 URL 的
                if orig_asset.startswith("http://") or orig_asset.startswith("https://"):
                    continue

                # 解析源文件路径
                if orig_asset.startswith("file:///"):
                    src_path = Path(orig_asset.replace("file:///", "").replace("%20", " "))
                else:
                    src_path = Path(orig_asset)

                if src_path.exists():
                    dst_path = template_assets_dir / src_path.name
                    if not dst_path.exists() or dst_path.stat().st_size != src_path.stat().st_size:
                        logger.info(f"Copying asset: {src_path.name} -> {dst_path}")
                        shutil.copy2(src_path, dst_path)
                    # 使用相对于模板目录的路径
                    scene["asset_path"] = f"assets/{src_path.name}"
                else:
                    # 如果原路径不存在，但模板 assets 目录里已经有了同名文件，我们也认为它是有效的，直接重用
                    local_in_template = template_assets_dir / src_path.name
                    if local_in_template.exists():
                        scene["asset_path"] = f"assets/{src_path.name}"
                    else:
                        logger.warning(f"Asset not found: {src_path}, using fallback")
                        scene["asset_path"] = "assets/fallback.jpg"

        # 2. 拼接所有场景的视频素材为 concat_master.mp4
        self._concat_scene_videos(scenes, template_assets_dir)

        # 3. 写入 data.js
        data_file = template_dir / "data.js"
        
        # 处理 data 中的 pathlib.Path 对象以便 JSON 序列化
        def serialize_paths(obj):
            if isinstance(obj, Path):
                return str(obj.as_posix())
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
            
        json_str = json.dumps(data, indent=2, ensure_ascii=False, default=serialize_paths)
        data_file.write_text(f"window.__VIDEOFORGE_DATA__ = {json_str};", encoding="utf-8")
        logger.info(f"Generated {data_file}")

        # 4. 调用 HyperFrames CLI 渲染视频
        import os
        npx = "npx.cmd" if os.name == "nt" else "npx"
        cmd = [npx, "--yes", "hyperframes@0.6.55", "render"]
        logger.info(f"Running HyperFrames CLI: {' '.join(cmd)} at {template_dir}")
        
        subprocess.run(cmd, cwd=template_dir, check=True)

        # 5. 寻找生成的 mp4 文件 (通常在 renders/ 目录下)
        renders_dir = template_dir / "renders"
        if not renders_dir.exists():
            raise FileNotFoundError(f"Renders directory not found: {renders_dir}")
            
        mp4_files = list(renders_dir.glob("*.mp4"))
        if not mp4_files:
            raise FileNotFoundError("No rendered video found.")
            
        # 找最新生成的文件
        rendered_video = max(mp4_files, key=lambda p: p.stat().st_mtime)

        # 6. 使用 ffmpeg 混音
        final_output = Path("output") / f"{template_name}_output.mp4"
        final_output.parent.mkdir(parents=True, exist_ok=True)
        
        self._mux_audio(rendered_video, scenes, final_output)
        
        duration_sec = data.get("total_duration", 0.0) + 3.0
        return RenderResult(
            video_path=final_output,
            duration_sec=duration_sec,
            resolution=self.resolution
        )

    def _concat_scene_videos(self, scenes: list[dict], assets_dir: Path):
        """
        将各场景的视频素材拼接成 concat_master.mp4，供 HyperFrames 模板使用。
        每个场景的视频会被裁剪到对应的 duration 长度。
        """
        output_file = assets_dir / "concat_master.mp4"

        # 收集有效的视频素材
        video_segments = []
        for scene in scenes:
            asset_path = scene.get("asset_path", "")
            duration = scene.get("duration", 5.0)

            if not asset_path:
                continue

            # 处理相对路径
            if asset_path.startswith("assets/"):
                full_path = assets_dir.parent / asset_path
            else:
                full_path = Path(asset_path)

            # 检查是否为视频文件
            if full_path.exists() and full_path.suffix.lower() in ['.mp4', '.webm', '.mov', '.avi', '.mkv']:
                video_segments.append({
                    "path": full_path,
                    "duration": duration
                })
            else:
                logger.warning(f"Asset not found or not a video: {full_path}")

        if not video_segments:
            logger.warning("No video segments to concatenate, skipping concat_master.mp4 generation")
            return

        logger.info(f"Concatenating {len(video_segments)} video segments into concat_master.mp4...")

        # 使用 ffmpeg filter_complex 进行拼接
        # 步骤：每个视频先裁剪到指定时长，然后缩放到统一分辨率，最后拼接
        inputs = []
        filter_parts = []
        concat_inputs = []

        for i, seg in enumerate(video_segments):
            inputs.extend(["-i", str(seg["path"])])
            # 对每个输入：截取时长 + 缩放到 1920x1080 + 设置帧率
            filter_parts.append(
                f"[{i}:v]trim=duration={seg['duration']},setpts=PTS-STARTPTS,"
                f"scale=1920:1080:force_original_aspect_ratio=decrease,"
                f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=60,format=yuv420p[v{i}]"
            )
            concat_inputs.append(f"[v{i}]")

        # 拼接所有视频流
        filter_parts.append(f"{''.join(concat_inputs)}concat=n={len(video_segments)}:v=1:a=0[outv]")
        filter_complex = ";".join(filter_parts)

        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-an",  # 无音频，音频后面单独混合
            str(output_file)
        ]

        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
            logger.info(f"Successfully created concat_master.mp4: {output_file}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to concatenate videos: {e.stderr}")
            raise RuntimeError(f"Video concatenation failed: {e.stderr}") from e

    def _mux_audio(self, video_path: Path, scenes: list[dict], output_path: Path):
        """将生成的多个配音与无声视频合成在一起"""
        
        # 生成一个 filter_complex 脚本
        # 1. 组合所有的音频，通过 adelay 延迟播放
        # [0:a]adelay=1000|1000[a0]; [1:a]adelay=2000|2000[a1]; [a0][a1]amix=inputs=2[aout]
        
        inputs = []
        filter_parts = []
        amix_inputs = []
        
        logger.info("Muxing audio with ffmpeg...")
        
        for i, scene in enumerate(scenes):
            if "audio_path" in scene and scene["audio_path"]:
                audio = Path(scene["audio_path"])
                if audio.exists():
                    inputs.extend(["-i", str(audio)])
                    # delay in ms (add 3s for the title screen at the beginning)
                    title_offset_ms = 3000
                    delay_ms = int(scene.get("start_time", 0) * 1000) + title_offset_ms
                    input_idx = len(inputs) // 2 # 0 是 video，所以音频是从 1 开始
                    
                    filter_parts.append(f"[{input_idx}:a]adelay={delay_ms}|{delay_ms}[a{i}];")
                    amix_inputs.append(f"[a{i}]")
        
        if not amix_inputs:
            # 如果完全没有声音，直接拷贝视频
            shutil.copy2(video_path, output_path)
            return
            
        # 构建 amix
        filter_parts.append(f"{''.join(amix_inputs)}amix=inputs={len(amix_inputs)}:normalize=0[aout]")
        filter_complex = " ".join(filter_parts)
        
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            str(output_path)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
            logger.info(f"Muxing completed: {output_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg muxing failed: {e.stderr}")
            # fall back
            shutil.copy2(video_path, output_path)
