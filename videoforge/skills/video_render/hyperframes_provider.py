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
        data_file = template_dir / "data.json"
        
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

        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(serialize_paths(data), f, ensure_ascii=False, indent=2)

        logger.info(f"Rendering template {template}...")
        
        # 调用 hyperframes render
        # npx --yes hyperframes@0.6.55 render
        cmd = [
            "npx", 
            "--yes", 
            f"hyperframes@{self.hyperframes_version}", 
            "render",
        ]
        
        try:
            # 需要在 shell 环境执行以识别 npx
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

        # 查找 renders 目录下最新生成的 mp4 文件
        renders_dir = template_dir / "renders"
        if not renders_dir.exists():
            raise FileNotFoundError(f"Renders directory not found: {renders_dir}")
            
        mp4_files = list(renders_dir.glob("*.mp4"))
        if not mp4_files:
            raise FileNotFoundError(f"No rendered mp4 found in {renders_dir}")
            
        # 获取最新创建的文件
        output_mp4 = max(mp4_files, key=lambda p: p.stat().st_mtime)
            
        # 复制到项目的 output 目录
        final_output = project_root / "output" / f"{template}_output.mp4"
        shutil.copy2(output_mp4, final_output)
        
        # 简单计算一个时长 (实际可由 ffprobe 或模板配置决定，MVP 暂写死一个值或从 HTML 里读)
        return RenderResult(
            video_path=final_output,
            duration_sec=0.0, # TODO: 从 data 或输出中读取
            resolution="1920x1080"
        )
