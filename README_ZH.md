# VideoForge

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**知识科普视频自动化生产系统** —— 真实素材的智能检索与组合。

<p align="center">
  <img src="https://via.placeholder.com/800x400?text=VideoForge+Demo" alt="VideoForge Demo" width="600">
</p>

> 📹 面向知识区 UP 主的"本地优先"视频自动化工作台。  
> 核心差异化：**不用 AI 生成画面，而是智能检索和组合真实素材**，保证学科严谨性。

[English](README.md)

---

## ✨ 特性

- 🎬 **RAG 编剧**：基于竞品结构学习，自动生成分镜脚本
- 🎤 **多引擎配音**：Edge-TTS（免费）/ CosyVoice / ElevenLabs
- ⏱️ **字级时间戳**：WhisperX 精准对齐，实现逐字高亮
- 🔍 **智能素材检索**：本地 FAISS 向量检索 → YouTube/Bilibili 自动下载
- 🏷️ **自动打标**：CLIP + Gemini 视觉模型
- 🎥 **HTML 渲染**：HyperFrames + GSAP 动效（字幕、转场、梗图飞入）
- 📚 **素材库管理**：自动入库、去重、场景切分
- 🧩 **模块化设计**：Skill 可插拔，Provider 可替换

---

## 🚀 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+ (用于 HyperFrames 渲染)
- FFmpeg (可选，用于音视频处理)

### 安装

```bash
# 克隆仓库
git clone https://github.com/doufa/video-forge.git
cd video-forge

# 安装 Python 依赖
pip install -e ".[phase2]"

# 安装渲染引擎
npm install hyperframes
```

### 配置

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env，填入你的 API Key
# 推荐使用硅基流动 DeepSeek-V3（注册送额度）
```

### 运行 Demo

```bash
# 生成一个"食盐溶解"科普视频
python demo_salt_dissolve.py
```

详细使用说明请参考 [Demo 使用指南](docs/demo_guide.md)。

---

## 📐 架构

```
Pipeline Runner → Skill 调度（配置驱动，Provider 可插拔）
                    ├── script_writer    竞品 RAG 编剧
                    ├── tts_generate     配音生成（edge-tts / CosyVoice / ElevenLabs）
                    ├── timestamp_align  字级时间戳（WhisperX）
                    ├── asset_search     多源素材检索（本地 FAISS → yt-dlp → Pexels）
                    ├── asset_tag        素材自动打标（CLIP + Gemini）
                    ├── video_render     HyperFrames 渲染
                    ├── subtitle_export  SRT 字幕导出
                    └── qa_check         三级质量验证
```

---

## 📖 文档

| 文档 | 说明 |
|------|------|
| [Demo 使用指南](docs/demo_guide.md) | ⭐ 快速上手教程 |
| [开发路线图](docs/roadmap.md) | 项目规划与进度 |
| [方案设计](VideoForge：知识科普视频自动化生产系统方案设计%20(开工版).md) | 详细技术方案 |
| [贡献指南](CONTRIBUTING.md) | 如何参与贡献 |
| [更新日志](CHANGELOG.md) | 版本变更历史 |

---

## 🗺️ 路线图

| 版本 | 目标 | 状态 |
|------|------|------|
| v0.1 | 渲染引擎验证 | ✅ |
| v0.2 | 编剧 + 配音链路 | ✅ |
| v0.3 | 云端素材 + E2E | ✅ |
| v0.4 | 本地素材库 + 向量检索 | ✅ |
| v0.5 | 自动入库 + RAG 模板 | ✅ |
| v0.6 | Web UI 工作台 | 🔜 |
| v1.0 | 生产就绪 | 📋 |

查看 [完整路线图](docs/roadmap.md) 了解更多。

---

## 🤝 贡献

欢迎贡献代码、报告 Bug、提出建议！

- 📖 阅读 [贡献指南](CONTRIBUTING.md)
- 🐛 提交 [Bug 报告](../../issues/new?template=bug_report.yml)
- ✨ 提出 [功能建议](../../issues/new?template=feature_request.yml)
- 💬 参与 [讨论](../../discussions)

---

## 📄 许可证

本项目采用 [MIT License](LICENSE) 开源。

---

## 🙏 致谢

- [HyperFrames](https://hyperframes.ai/) - HTML 视频渲染引擎
- [Edge-TTS](https://github.com/rany2/edge-tts) - 免费 TTS 引擎
- [WhisperX](https://github.com/m-bain/whisperX) - 字级时间戳对齐
- [CLIP](https://github.com/openai/CLIP) - 视觉语义嵌入
- [FAISS](https://github.com/facebookresearch/faiss) - 向量检索引擎
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - 视频下载工具
