# Phase 2: 编剧与配音链路任务清单

- `[/]` 1. **环境准备**
  - `[x]` 用户配置 `.env` 文件 (已配置小米大模型)
  - `[/]` 安装相关 Python 依赖 (`yt-dlp`, `faiss-cpu`, `openai`, `edge-tts`, `python-dotenv`)
- `[x]` 2. **实现 Script Writer (LLM 编剧模块)**
  - `[x]` 实现 `DeepSeekRAGProvider` (基于 OpenAI 兼容客户端调用)
  - `[x]` 设计 Prompt 和 JSON Schema 输出格式
  - `[x]` 封装并返回 `Script` 数据类
- `[x]` 3. **实现 TTS (语音生成模块)**
  - `[x]` 实现 `EdgeTTSProvider`
  - `[x]` 使用 `edge-tts` 命令行生成语音和 VTT 字幕文件
- `[x]` 4. **实现 Timestamp Aligner (时间戳对齐模块)**
  - `[x]` 更新 `whisperx_provider.py` (改为原生 `.vtt` 解析)
  - `[x]` 提取词组级/句级时间戳并返回 `TimestampResult`
- `[x]` 5. **串联测试**
  - `[x]` 编写 `test_phase2.py` 串联这三个核心模块
  - `[x]` 运行并验证输出：JSON 脚本 -> 语音文件 -> 时间戳对齐结果

## Phase 3: 云端素材检索与降级
- `[x]` 1. **修改 Prompt**
  - `[x]` 更新 `deepseek_rag.py`，要求大模型输出适合 yt-dlp 搜索的短促英文 keywords。
- `[x]` 2. **实现 YouTube 素材检索 (`YTDLPSearchProvider`)**
  - `[x]` 创建 `ytdlp_provider.py`，实现 `AssetSearchSkill`。
  - `[x]` 调用 `yt-dlp` 的 `ytsearch1:` 功能下载视频片段。
  - `[x]` 编写 Fallback 降级逻辑（下载失败时返回默认纯色图片）。
- `[x]` 3. **实现 Dummy 打标占位 (`DummyTagProvider`)**
  - `[x]` 创建 `dummy_tag.py`，直接返回空或占位 Tag。

## Phase 4: 端到端视频生产
- `[x]` 1. **实现 Pipeline 调度器 (`PipelineRunner`)**
  - `[x]` 编写 `runner.py` 串联 Phase 1-3，组装渲染载荷。
- `[x]` 2. **全链路测试 (`test_e2e.py`)**
  - `[x]` 编写一键测试脚本，生成完整的示例视频 `output/final_video.mp4`。
