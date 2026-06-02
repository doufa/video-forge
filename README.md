# VideoForge

知识科普视频自动化生产系统 —— 真实素材的智能检索与组合。

## 定位

面向知识区 UP 主的"本地优先"视频自动化工作台。与其他项目的根本区别：**不用 AI 生成画面，而是智能检索和组合真实素材**，保证学科严谨性。

## 架构

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

## 快速开始

```bash
# 安装基础依赖
pip install -e .

# Phase 1: HyperFrames 渲染验证
npm install hyperframes
npx hyperframes preview templates/hyperframes/demo.html
```

## 文档

- [Demo 使用指南](docs/demo_guide.md) ⭐ 快速上手
- [方案设计（开工版）](VideoForge：知识科普视频自动化生产系统方案设计%20(开工版).md)
- [开发路线图 (Roadmap)](docs/roadmap.md)
- [优化待办清单](docs/optimization_backlog.md)
- [Phase 1-2 分析与设计](docs/phase1_2_design.md)
- [Phase 3-4 实施计划](docs/phase3_4_implementation_plan.md)

## License

MIT
