# Changelog

所有重要的版本变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [Unreleased]

### 计划中
- Web UI 工作台 (Phase 10)
- Agent 编排与高级调度 (Phase 11)
- 三级 QA 系统完善 (Phase 12)

---

## [0.5.0] - 2026-06-02

### Added
- **自动入库流程**：素材自动切片、去重、入库
- **RAG 模板提取器**：从优质视频中学习叙事结构
- **DedupService**：基于 MD5 + 感知哈希的重复检测
- **Resource Library**：完整的资源库管理模块
  - 视频下载器 (`downloader.py`)
  - 场景切分器 (`scene_splitter.py`)
  - 帧采样器 (`frame_sampler.py`)
  - 字幕提取器 (`subtitles.py`)
  - 语义搜索 (`search.py`)
- **CLI 命令**：`scan`, `tag`, `search`, `stats`, `template extract`
- 完整的单元测试和集成测试

---

## [0.4.0] - 2026-05-28

### Added
- **CLIP 嵌入器**：视频帧向量化
- **FAISS 向量存储**：本地向量索引管理
- **LocalFaissProvider**：本地优先的素材检索
- SQLite 数据库持久化
- JSON Sidecar 元数据管理
- 路径工具函数

---

## [0.3.0] - 2026-05-20

### Added
- **YtdlpProvider**：YouTube/Bilibili 素材自动下载
- **PipelineRunner**：核心流水线调度器
- 端到端测试 (`test_e2e.py`)
- 英文关键词 Prompt 优化
- 降级策略（纯色占位图）

### Changed
- 素材检索支持云端回退

---

## [0.2.0] - 2026-05-15

### Added
- **ScriptWriterSkill**：DeepSeek RAG 编剧模块
- **TTSSkill**：Edge-TTS 配音生成
- **TimestampAlignSkill**：WhisperX 字级时间戳对齐
- 结构化 JSON 分镜表输出
- `.env.example` 配置模板

---

## [0.1.0] - 2026-05-10

### Added
- 项目初始化
- **HyperFrames 渲染验证**：HTML/CSS 视频模板
- GSAP 动效集成（动态字幕、梗图飞入、缩放转场）
- 基础项目结构
- pyproject.toml 配置

---

[Unreleased]: https://github.com/doufa/video-forge/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/doufa/video-forge/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/doufa/video-forge/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/doufa/video-forge/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/doufa/video-forge/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/doufa/video-forge/releases/tag/v0.1.0
