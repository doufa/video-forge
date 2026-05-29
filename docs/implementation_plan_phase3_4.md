# Phase 3 & 4 实施计划：云端素材与端到端渲染

该阶段的目标是响应用户要求：“本地现在没有资源。可以暂时跳过这一步，从云端来。然后做个示例视频出来”。
我们将放弃本地的轻量级向量检索（FAISS），转而实现通过免费开放 API 获取素材（Pexels），最后利用 `PipelineRunner` 将所有模块串联，一键输出示例科普视频。

## User Review Required

> [!WARNING]
> 为了实现云端获取素材，需要实现对免费图库 API（如 Pexels）的调用。
> Pexels 官方提供免费的开发者 API，需要提供 `PEXELS_API_KEY`。如果没有 API Key，我们将准备一个后备（Fallback）方案：随机使用预置的一段通用视频/颜色背景占位，以确保最后能跑出视频文件，不会中断。您是否有 Pexels API Key？如果没有，请同意我们采用后备占位方案。

## Proposed Changes

### Phase 3: 云端素材检索 (YouTube / Web Asset Search)
> **Pivot**: 放弃本地素材和弱质量的 Pexels 视频。采用直接利用 `yt-dlp` 搜索并下载 YouTube 等流媒体的高质量 B-roll 视频作为背景素材。

#### [NEW] `videoforge/skills/asset_search/ytdlp_provider.py`
- 继承 `AssetSearchSkill`。
- **功能**: 
  - 接收编剧生成的英文搜索词（如 `b-roll atom animation`）。
  - 利用 `yt-dlp` 的 `ytsearch1:` 功能自动搜索并下载排名第一的高质量素材（可控制下载分辨率以保证速度）。
  - （可选）若本地有 ffmpeg 环境，还可以配合 `--download-sections` 截取短片段，或在后续处理中截取前 N 秒。
  - **降级策略 (Fallback)**: 若由于网络原因（如 YouTube 无法访问）导致下载失败，返回一张纯色占位图片，保证 Pipeline 完整流转。

#### [MODIFY] `videoforge/skills/script_writer/deepseek_rag.py`
- 微调 Prompt，要求大模型在给出画面 `asset_keywords` 时，生成适合 YouTube 搜索的短促英文关键词（例如 `stock footage space` 或 `animation quantum`），避免太抽象的词语。

#### [MODIFY] `videoforge/skills/asset_tag/__init__.py`
- 实现一个 `DummyTagProvider`。因为目前全走云端搜索，无需本地对已有素材进行大模型分析。

---

### Phase 4: 端到端组装与渲染 (E2E Pipeline & Render)
将第一阶段的渲染器与第二阶段的编剧、配音模块结合，打通最后一公里。

#### [NEW] `videoforge/pipeline/runner.py`
- 核心调度器 `PipelineRunner`：
  1. 调用 `ScriptWriterSkill` 获取脚本 `Script`。
  2. 遍历脚本 `scenes`，拼接所有的旁白文本，调用 `TTSSkill` 生成全局音频与 VTT 时间戳。
  3. 遍历每个 `scenes`，调用 `AssetSearchSkill` 根据本句旁白提取到的关键词获取匹配的（云端）素材。
  4. 构建组装出 `RenderData`（包含各画面的出场时间、媒体路径等）。
  5. 传递给 `VideoRenderSkill` (HyperFramesProvider)。
  6. 导出包含画面、字幕、音频的最终 `.mp4` 文件。

#### [NEW] `test_e2e.py`
- 一键式测试脚本，通过简单的命令和 Topic 直接输出最终视频。

## Verification Plan
1. 确保在 `.env` 中添加 `PEXELS_API_KEY` （若有）。
2. 执行 `test_e2e.py`。
3. 检查控制台进度，观察视频是否正确生成于 `output/` 目录。
4. 播放生成的 `.mp4` 视频，检查字幕、配音、素材时长是否吻合。
