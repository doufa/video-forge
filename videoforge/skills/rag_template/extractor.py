"""叙事模板提取器

从 YouTube 视频字幕中提取叙事结构模板，用于 RAG 增强脚本生成。
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from videoforge.storage import Database
from videoforge.utils.paths import PROJECT_ROOT

logger = logging.getLogger(__name__)

TEMPLATE_EXTRACTION_PROMPT = """分析以下视频字幕，提取其叙事结构模板。

字幕内容：
{transcript}

请提取：
1. 叙事结构（按顺序列出每个部分的类型和描述）
2. 使用的叙事技巧

以 JSON 格式输出：
{{
  "structure": [
    {{"type": "hook", "description": "开场钩子的特点"}},
    {{"type": "setup", "description": "背景设定的特点"}},
    {{"type": "buildup", "description": "递进发展的特点"}},
    {{"type": "climax", "description": "高潮部分的特点"}},
    {{"type": "payoff", "description": "收尾的特点"}}
  ],
  "techniques": ["technique1", "technique2"],
  "topic_domain": "主题领域",
  "style_notes": "风格特点简述"
}}

注意：
- structure 中的 type 可以是: hook, setup, buildup, example, explanation, climax, payoff, summary, call_to_action
- techniques 可以是: visual_metaphor, gradual_reveal, question_answer, contrast, analogy, storytelling, data_driven, emotional_appeal
- 只输出 JSON，不要其他内容"""


@dataclass
class NarrativeTemplate:
    """叙事模板"""
    id: int | None = None
    source_channel: str = ""
    source_url: str = ""
    topic_domain: str = ""
    structure: list[dict] = field(default_factory=list)
    techniques: list[str] = field(default_factory=list)
    style_notes: str = ""
    embedding: bytes | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_channel": self.source_channel,
            "source_url": self.source_url,
            "topic_domain": self.topic_domain,
            "structure": self.structure,
            "techniques": self.techniques,
            "style_notes": self.style_notes,
        }

    def to_prompt_context(self) -> str:
        """转换为可注入 prompt 的上下文"""
        structure_desc = "\n".join(
            f"  {i+1}. [{s['type']}] {s['description']}"
            for i, s in enumerate(self.structure)
        )
        techniques_desc = ", ".join(self.techniques)

        return f"""参考叙事模板 ({self.topic_domain}):
结构:
{structure_desc}
技巧: {techniques_desc}
风格: {self.style_notes}"""


class TemplateExtractor:
    """叙事模板提取器"""

    def __init__(self, config: dict):
        self.config = config
        llm_config = config.get("skills", {}).get("asset_tag", {}).get("gemini", {})
        self.api_key = llm_config.get("api_key", "")
        self.model = llm_config.get("model", "gemini-2.0-flash")
        self.templates_dir = PROJECT_ROOT / "data" / "rag_templates"
        self.templates_dir.mkdir(parents=True, exist_ok=True)

    def download_subtitles(self, url: str) -> str | None:
        """下载 YouTube 视频字幕"""
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "subs"

            cmd = [
                sys.executable, "-m", "yt_dlp",
                url,
                "--write-subs",
                "--write-auto-subs",
                "--sub-lang", "zh,en",
                "--skip-download",
                "-o", str(output_path),
            ]

            try:
                subprocess.run(cmd, capture_output=True, timeout=60, check=True)

                for sub_file in Path(temp_dir).glob("*.vtt"):
                    return self._parse_vtt(sub_file)
                for sub_file in Path(temp_dir).glob("*.srt"):
                    return self._parse_srt(sub_file)

            except Exception as e:
                logger.error(f"Failed to download subtitles: {e}")

        return None

    def _parse_vtt(self, vtt_path: Path) -> str:
        """解析 VTT 字幕文件"""
        text_lines = []
        with open(vtt_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("WEBVTT"):
                    continue
                if "-->" in line:
                    continue
                if re.match(r"^\d+$", line):
                    continue
                line = re.sub(r"<[^>]+>", "", line)
                if line:
                    text_lines.append(line)

        return " ".join(text_lines)

    def _parse_srt(self, srt_path: Path) -> str:
        """解析 SRT 字幕文件"""
        text_lines = []
        with open(srt_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if re.match(r"^\d+$", line):
                    continue
                if "-->" in line:
                    continue
                text_lines.append(line)

        return " ".join(text_lines)

    def extract_template(self, transcript: str, source_url: str = "", source_channel: str = "") -> NarrativeTemplate | None:
        """从字幕文本提取叙事模板"""
        if not self.api_key:
            logger.error("Gemini API key not configured")
            return None

        if len(transcript) > 15000:
            transcript = transcript[:15000] + "..."

        prompt = TEMPLATE_EXTRACTION_PROMPT.format(transcript=transcript)

        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model)

            response = model.generate_content(prompt)
            response_text = response.text.strip()

            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if not json_match:
                logger.error("No JSON found in response")
                return None

            data = json.loads(json_match.group())

            template = NarrativeTemplate(
                source_channel=source_channel,
                source_url=source_url,
                topic_domain=data.get("topic_domain", ""),
                structure=data.get("structure", []),
                techniques=data.get("techniques", []),
                style_notes=data.get("style_notes", ""),
            )

            return template

        except ImportError:
            logger.error("google-generativeai not installed. Run: pip install google-generativeai")
            return None
        except Exception as e:
            logger.error(f"Template extraction failed: {e}")
            return None

    def extract_from_url(self, url: str, channel: str = "") -> NarrativeTemplate | None:
        """从 YouTube URL 提取模板"""
        logger.info(f"Downloading subtitles from {url}...")
        transcript = self.download_subtitles(url)

        if not transcript:
            logger.error("No subtitles available")
            return None

        logger.info(f"Extracting template from {len(transcript)} chars of transcript...")
        return self.extract_template(transcript, source_url=url, source_channel=channel)

    def save_template(self, template: NarrativeTemplate) -> int:
        """保存模板到数据库"""
        with Database() as db:
            cursor = db._conn.execute(
                """
                INSERT INTO rag_templates (
                    source_channel, source_url, topic_domain,
                    structure, techniques, embedding
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    template.source_channel,
                    template.source_url,
                    template.topic_domain,
                    json.dumps(template.structure, ensure_ascii=False),
                    json.dumps(template.techniques, ensure_ascii=False),
                    template.embedding,
                ),
            )
            db._conn.commit()
            template.id = cursor.lastrowid
            logger.info(f"Saved template ID {template.id}")
            return template.id

    def list_templates(self, topic_domain: str | None = None) -> list[NarrativeTemplate]:
        """列出所有模板"""
        with Database() as db:
            if topic_domain:
                rows = db._conn.execute(
                    "SELECT * FROM rag_templates WHERE topic_domain LIKE ?",
                    (f"%{topic_domain}%",)
                ).fetchall()
            else:
                rows = db._conn.execute("SELECT * FROM rag_templates").fetchall()

            templates = []
            for row in rows:
                templates.append(NarrativeTemplate(
                    id=row["id"],
                    source_channel=row["source_channel"] or "",
                    source_url=row["source_url"] or "",
                    topic_domain=row["topic_domain"] or "",
                    structure=json.loads(row["structure"] or "[]"),
                    techniques=json.loads(row["techniques"] or "[]"),
                    embedding=row["embedding"],
                ))
            return templates

    def get_template(self, template_id: int) -> NarrativeTemplate | None:
        """获取单个模板"""
        with Database() as db:
            row = db._conn.execute(
                "SELECT * FROM rag_templates WHERE id = ?", (template_id,)
            ).fetchone()

            if not row:
                return None

            return NarrativeTemplate(
                id=row["id"],
                source_channel=row["source_channel"] or "",
                source_url=row["source_url"] or "",
                topic_domain=row["topic_domain"] or "",
                structure=json.loads(row["structure"] or "[]"),
                techniques=json.loads(row["techniques"] or "[]"),
                embedding=row["embedding"],
            )

    def search_templates(self, query: str, top_k: int = 3) -> list[NarrativeTemplate]:
        """搜索相关模板（关键词匹配）"""
        templates = self.list_templates()
        if not templates:
            return []

        keywords = query.lower().split()
        scored = []

        for t in templates:
            score = 0
            searchable = f"{t.topic_domain} {' '.join(t.techniques)} {t.style_notes}".lower()
            for kw in keywords:
                if kw in searchable:
                    score += 1
            if score > 0:
                scored.append((t, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [t for t, _ in scored[:top_k]]
