from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field

from videoforge.models import Script, ScriptScene
from videoforge.skills.base import ScriptWriterSkill

logger = logging.getLogger(__name__)

# 定义 Pydantic 模型用于强化 JSON Schema 输出 (如果模型支持 Structured Outputs)
# 这里仅作定义和 prompt 辅助
class SceneSchema(BaseModel):
    index: int = Field(description="场景序号，从 1 开始")
    narration: str = Field(description="当前场景的旁白文本")
    asset_keywords: list[str] = Field(description="用于在素材库搜索画面的 1-3 个英文关键词")
    notes: str = Field(description="备注信息，如特效、转场指示")

class ScriptSchema(BaseModel):
    title: str = Field(description="视频标题")
    style: str = Field(description="视频整体风格，如 '幽默科普', '硬核科技'")
    scenes: list[SceneSchema] = Field(description="分镜列表")


class DeepSeekRAGProvider(ScriptWriterSkill):
    """基于 OpenAI 标准 API (如 DeepSeek, Qwen) 的 RAG 编剧实现"""
    
    def __init__(self, config: dict):
        self.config = config.get("llm", {})
        self.api_key = self.config.get("api_key")
        self.base_url = self.config.get("base_url")
        self.model_name = self.config.get("model", "deepseek-ai/DeepSeek-V3")
        
        if not self.api_key:
            logger.warning("SCRIPT_LLM_API_KEY 未配置，编剧模块可能无法工作。")
            
        self.client = OpenAI(
            api_key=self.api_key or "mock",
            base_url=self.base_url
        )
        
    def generate(self, topic: str, knowledge_points: list[str], **kwargs) -> Script:
        logger.info(f"Generating script for topic: {topic}")
        
        # 1. 组装 Prompt
        points_str = "\n".join(f"- {p}" for p in knowledge_points)
        system_prompt = (
            "你是一个拥有百万粉丝的 B 站/YouTube 金牌科普视频编剧。你的任务是根据给定的主题和知识点，"
            "撰写一个引人入胜的视频分镜脚本。\n"
            "叙事结构建议：提出悬念 -> 趣味比喻 -> 核心原理解释 -> 升华总结。\n\n"
            "【强制输出格式】\n"
            "你必须输出合法的 JSON 格式，不要包含任何 Markdown 标记 (如 ```json) 之外的其他文本。\n"
            "JSON 结构必须符合以下格式：\n"
            "{\n"
            '  "title": "视频标题",\n'
            '  "style": "风格描述",\n'
            '  "scenes": [\n'
            "    {\n"
            '      "index": 1,\n'
            '      "narration": "第一句旁白",\n'
            '      "asset_keywords": ["space", "stars", "zoom"],\n'
            '      "notes": "特效或画面提示"\n'
            "    }\n"
            "  ]\n"
            "}"
        )
        
        user_prompt = f"视频主题：{topic}\n核心知识点：\n{points_str}"
        
        # 2. 调用 LLM
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            # 如果是支持 response_format 的模型可以开启 JSON Mode
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        if not content:
            raise ValueError("LLM 返回内容为空")
            
        # 3. 清理与解析 JSON
        # 处理可能被 Markdown 块包裹的情况
        content = content.strip()
        if content.startswith("```"):
            lines = content.splitlines()
            if lines[0].startswith("```"): lines.pop(0)
            if lines[-1].startswith("```"): lines.pop(-1)
            content = "\n".join(lines)
            
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"解析 LLM 返回的 JSON 失败: {content}")
            raise RuntimeError(f"Script JSON decode error: {e}") from e
            
        # 4. 组装模型
        scenes = []
        for s in data.get("scenes", []):
            scene = ScriptScene(
                index=s.get("index", 0),
                narration=s.get("narration", ""),
                asset_keywords=s.get("asset_keywords", []),
                notes=s.get("notes", "")
            )
            scenes.append(scene)
            
        return Script(
            title=data.get("title", topic),
            scenes=scenes,
            style=data.get("style", "")
        )
