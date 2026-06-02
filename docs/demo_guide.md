# VideoForge Demo 使用指南

本文档以"食盐在水中的溶解过程"为例，演示 VideoForge 的完整视频生产流程。

---

## 前置准备

### 1. 安装 Python 依赖

```bash
pip install -e .
```

主要依赖包括：
- `edge-tts` - 微软免费 TTS
- `whisperx` - 字级时间戳对齐
- `yt-dlp` - YouTube/Bilibili 素材下载
- `openai` - LLM API 调用
- `pyyaml`, `python-dotenv` - 配置管理

### 2. 安装 HyperFrames（渲染引擎）

```bash
npm install hyperframes
```

### 3. 配置 API Key

创建 `.env` 文件：

```env
# LLM 编剧（推荐使用硅基流动 DeepSeek）
SCRIPT_LLM_BASE_URL=https://api.siliconflow.cn/v1
SCRIPT_LLM_MODEL=deepseek-ai/DeepSeek-V3
SCRIPT_LLM_API_KEY=your_api_key_here

# 可选：Gemini 视觉模型（用于素材打标和 QA）
VISION_LLM_API_KEY=your_gemini_api_key
```

**免费/低成本 LLM 选项：**
- 硅基流动 DeepSeek-V3：https://siliconflow.cn （注册送额度）
- 阿里云百炼 Qwen-Max：https://bailian.console.aliyun.com
- OpenAI 兼容 API 均可

---

## Demo 执行

### 方式一：运行完整 Demo

```bash
python demo_salt_dissolve.py
```

### 方式二：自定义主题

修改 `demo_salt_dissolve.py` 中的 `topic` 和 `knowledge_points`：

```python
topic = "你的主题"
knowledge_points = [
    "知识点1",
    "知识点2",
    "知识点3",
]
```

### 方式三：使用 test_e2e.py

```bash
python test_e2e.py
```

默认主题是"为什么说光速无法超越？"

---

## 流水线步骤详解

### Step 1: 编剧 (ScriptWriter)

**输入：** 主题 + 知识点列表  
**输出：** 结构化 JSON 分镜表

```json
{
  "title": "食盐在水中的溶解过程",
  "scenes": [
    {
      "index": 1,
      "narration": "食盐，也就是我们常说的氯化钠...",
      "asset_keywords": ["salt crystal", "sodium chloride structure"]
    },
    ...
  ]
}
```

**工作原理：**
- 调用 LLM API（DeepSeek/Qwen）
- Prompt 要求生成适合科普视频的叙事结构
- 自动生成英文素材关键词（用于后续 YouTube 搜索）

### Step 2: 配音 (TTS)

**输入：** 每个场景的旁白文本  
**输出：** MP3 音频文件 + VTT 时间戳

```
output/
  ├── scene_1.mp3
  ├── scene_1.vtt
  ├── scene_2.mp3
  └── ...
```

**配音选项：**
- `edge_tts`（默认）：免费，质量中等
- `cosyvoice`：本地部署，支持情感
- `elevenlabs`：付费，高质量

### Step 3: 时间戳对齐 (WhisperX)

**输入：** 音频文件 + 原始文本  
**输出：** 字级时间戳

```python
[
  {"word": "食盐", "start": 0.0, "end": 0.5},
  {"word": "也就是", "start": 0.5, "end": 0.9},
  ...
]
```

**用途：** 渲染时实现字幕逐字高亮效果

### Step 4: 素材检索 (AssetSearch)

**输入：** 场景的 `asset_keywords`  
**输出：** 下载的视频/图片文件

**检索策略：**
1. 本地 FAISS 向量检索（如果有本地素材库）
2. YouTube/Bilibili 自动搜索下载（yt-dlp）
3. 降级：纯色占位图

**示例：**
- 关键词 `salt dissolving water` → 下载相关科普动画
- 关键词 `water molecule animation` → 下载水分子结构动画

### Step 5: 渲染合成 (HyperFrames)

**输入：** 音频 + 视频素材 + 时间戳 + 模板  
**输出：** 最终 MP4 视频

**模板特性：**
- HTML/CSS/GSAP 动效
- 动态字幕（逐字高亮）
- 转场效果
- 背景视频/图片叠加

---

## 输出目录结构

```
output/
├── 2026-06-02_153000_食盐在水中的溶解过程/
│   ├── script.json          # 分镜脚本
│   ├── scene_1.mp3          # 场景1配音
│   ├── scene_1.vtt          # 场景1时间戳
│   ├── scene_1_asset.mp4    # 场景1素材
│   ├── scene_2.mp3
│   ├── ...
│   └── final.mp4            # 最终视频
└── assets/                   # 下载的素材缓存
    └── ...
```

---

## 常见问题

### Q: LLM 返回格式错误

检查 Prompt 是否正确，或更换模型。DeepSeek-V3 对 JSON 输出支持较好。

### Q: yt-dlp 下载失败

可能原因：
- 网络问题（YouTube 需要代理）
- 视频已删除或受限

解决：系统会自动降级到占位图，不影响流程完成。

### Q: WhisperX 报错

确保已安装 `torch` 和正确的 CUDA 版本（如有 GPU）。CPU 模式也可运行但较慢。

### Q: HyperFrames 渲染失败

检查：
- Node.js 是否安装
- `npm install hyperframes` 是否成功
- 模板文件是否存在

---

## 进阶用法

### 使用本地素材库

1. 将素材放入 `assets/` 目录
2. 运行索引：
   ```bash
   python -m videoforge.cli scan
   python -m videoforge.cli tag
   ```
3. 修改 `config.yaml` 中 `asset_search.provider` 为 `local_faiss`

### 提取叙事模板

从优质科普视频学习叙事结构：

```bash
python -m videoforge.cli template extract --url "https://youtube.com/watch?v=xxx" --save
```

### 查看素材库状态

```bash
python -m videoforge.cli stats
```

---

## 示例输出

运行 `demo_salt_dissolve.py` 后的预期输出：

```
============================================================
  VideoForge Demo - 食盐在水中的溶解过程
============================================================

📚 主题: 食盐在水中的溶解过程
📝 知识点数量: 5
   1. 食盐的化学成分是氯化钠，由钠离子和氯离子组成
   2. 水分子是极性分子，氧端带负电，氢端带正电
   ...

🔧 加载配置...
🚀 初始化 Pipeline 组件...
   ✓ 编剧模块 (DeepSeek RAG)
   ✓ 配音模块 (Edge-TTS)
   ✓ 时间戳对齐模块 (WhisperX)
   ✓ 素材检索模块 (yt-dlp)
   ✓ 渲染模块 (HyperFrames)

============================================================
  开始视频生产流水线
============================================================

14:30:01 [INFO] === Stage 1: Script Writing ===
14:30:05 [INFO] === Stage 2 & 3: TTS and Alignment ===
14:30:10 [INFO] Processing TTS for scene 1...
...
14:30:30 [INFO] === Stage 4: Asset Search ===
14:30:35 [INFO] Searching assets for scene 1: ['salt crystal', 'NaCl structure']
...
14:31:00 [INFO] === Stage 5: Video Render ===
14:31:15 [INFO] Pipeline completed successfully!

============================================================
  ✅ 视频生产完成!
============================================================

📹 输出视频: output/final.mp4
   文件大小: 12.3 MB

📄 脚本场景数: 5
   Scene 1: 食盐，也就是氯化钠，是由钠离子和...
   Scene 2: 水分子是一种极性分子...
   ...

🎵 生成的音频文件: 5
🎬 下载的素材: 5
```

---

*最后更新：2026-06-02*
