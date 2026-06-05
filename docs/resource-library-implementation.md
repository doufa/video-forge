# Resource Library 本地视频素材库实现小结 (2026-06-05)

## 概述

Resource Library 实现了一个完整的**本地视频素材库**：从 URL/本地导入视频 → 场景切分 → 字幕解析 → 关键帧抽取 → CLIP 嵌入 → FAISS 索引 → 混合语义检索。所有元数据存入 SQLite，向量存 FAISS，CLI 提供操作入口。

---

## 新增 / 修改文件总览

### 新增文件（9 个）

```
videoforge/resource_library/
├── __init__.py           # 包导出: ResourceIndexer, ResourceSearcher
├── models.py             # 5 个 dataclass 数据模型
├── downloader.py         # yt-dlp 视频下载 + 本地视频包装
├── subtitles.py          # VTT/SRT 解析 + 语言推断 + 字幕-片段关联
├── scene_splitter.py     # PySceneDetect 场景检测 + 固定窗口 fallback
├── frame_sampler.py      # ffmpeg 关键帧抽取
├── indexer.py            # ResourceIndexer: 核心索引流程
└── search.py             # ResourceSearcher: 混合 visual+text 检索
```

### 修改文件（2 个）

| 文件 | 行数变化 | 变更内容 |
|------|----------|----------|
| `videoforge/storage/database.py` | +255 | 新增 2 个 dataclass、2 个表、7 个 DB 方法 |
| `videoforge/cli.py` | +89 | 新增 4 个子命令 |

---

## 数据模型 (`models.py`)

| 类 | 用途 | 关键字段 |
|---|---|---|
| `TranscriptCue` | 字幕时间片 | `start_sec`, `end_sec`, `text`, `language`, `is_auto_generated` |
| `SceneSegment` | 场景片段（检索单元） | `start_sec`, `end_sec`, `keyframe_paths`, `tags`, `quality_score` |
| `DownloadedResource` | 已下载视频资源 | `video_path`, `subtitle_paths`, `source_url`, `title` |
| `IngestResult` | 导入摘要 | `asset_id`, `segments_created`, `transcripts_created`, `visual_vectors`, `text_vectors` |
| `ResourceSearchHit` | 检索结果项 | `asset_path`, `segment_id`, `score`, `match_type`, `transcript_text`, `keyframe_paths` |

`SceneSegment.duration_sec` 由 `end_sec - start_sec` 计算得出（`@property`），不存储。

---

## 数据库层 (`storage/database.py`)

### 新增 dataclass

```python
@dataclass
class AssetTranscript:      # 字幕片段记录
    id: int | None
    asset_id: int
    start_sec: float
    end_sec: float
    text: str
    language: str
    is_auto_generated: bool

@dataclass
class AssetSegment:         # 可检索素材片段
    id: int | None
    asset_id: int
    start_sec / end_sec / duration_sec: float
    transcript_text: str
    keyframe_paths: list[str] | None    # JSON 存储
    visual_embedding_id: str
    text_embedding_id: str
    tags: list[str] | None              # JSON 存储
    quality_score: float
    reviewed: bool
    created_at: datetime | None
```

### 新增表结构

```sql
-- 字幕片段表
CREATE TABLE IF NOT EXISTS asset_transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    start_sec REAL NOT NULL,
    end_sec REAL NOT NULL,
    text TEXT DEFAULT '',
    language TEXT DEFAULT '',
    is_auto_generated INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(asset_id) REFERENCES assets(id) ON DELETE CASCADE
);
CREATE INDEX idx_asset_transcripts_asset ON asset_transcripts(asset_id);
CREATE INDEX idx_asset_transcripts_time ON asset_transcripts(asset_id, start_sec, end_sec);

-- 检索片段表
CREATE TABLE IF NOT EXISTS asset_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    start_sec REAL NOT NULL,
    end_sec REAL NOT NULL,
    duration_sec REAL NOT NULL,
    transcript_text TEXT DEFAULT '',
    keyframe_paths TEXT DEFAULT '[]',           -- JSON 数组
    visual_embedding_id TEXT DEFAULT '',
    text_embedding_id TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',                      -- JSON 数组
    quality_score REAL DEFAULT 1.0,
    reviewed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(asset_id) REFERENCES assets(id) ON DELETE CASCADE
);
CREATE INDEX idx_asset_segments_asset ON asset_segments(asset_id);
CREATE INDEX idx_asset_segments_time ON asset_segments(asset_id, start_sec, end_sec);
```

`keyframe_paths` 和 `tags` 以 JSON TEXT 存储，通过 `_load_json_list()` 安全反序列化（防御 None、非法 JSON、非数组值）。

### 新增 DB 方法

| 方法 | 功能 |
|------|------|
| `clear_asset_resource_data(asset_id)` | 清除素材的字幕与片段元数据 |
| `add_asset_transcript(transcript)` | 添加字幕片段 |
| `list_asset_transcripts(asset_id)` | 按时间排序列出字幕 |
| `add_asset_segment(segment)` | 添加检索片段 |
| `update_asset_segment(segment)` | 更新检索片段 |
| `get_asset_segment(segment_id)` | 按 ID 获取片段 |
| `list_asset_segments(asset_id, limit, offset)` | 列出片段（支持按素材筛选 + 分页） |

---

## 各模块设计

### downloader.py — 视频下载与本地加载

- **`download_video_resource(url)`**: 调用 yt-dlp 下载视频（最高 1080p mp4），同时获取 info.json、字幕(vtt/srt)，通过 `find_related_files()` 按文件名前缀匹配关联文件
- **`local_video_resource(path, subtitle_paths)`**: 包装本地视频为 `DownloadedResource`，自动发现同名字幕文件
- **`slugify(value)`**: 文件名安全化（120 字符截断）

### subtitles.py — 字幕解析

- **`parse_subtitle_file(path)`**: 解析 VTT/SRT 格式，自动识别 BOM，跳过 NOTE/STYLE/REGION 行，清洗 HTML 标签和实体
- **`parse_timestamp(value)`**: 支持 `HH:MM:SS.mmm` 和 `MM:SS.mmm` 两种格式
- **`choose_preferred_subtitle(paths)`**: 评分排序：中文 > 英文 > 其他，人工字幕 > 自动字幕
- **`assign_transcripts_to_segments(cues, segments)`**: 按时间重叠（非完全包含）将字幕文本关联到场景片段
- **`infer_subtitle_language(path)`**: 从 yt-dlp 文件名推断语种（如 `video.zh.vtt` → `zh`）

### scene_splitter.py — 场景切分

- **`detect_scene_segments(video_path)`**: 优先使用 PySceneDetect ContentDetector 检测场景切换；失败时回退到 12 秒固定窗口
- **`normalize_segments(segments, ...)`**: 片段规范化：
  - 裁剪到视频时长范围
  - 合并 < 3 秒的短片段到前一个
  - 拆分 > 30 秒的长片段为 12 秒窗口
  - 空结果时用固定窗口 fallback
- **`fixed_window_segments(duration, window_sec)`**: 均匀切分（默认 12s/段）

### frame_sampler.py — 关键帧抽取

每段抽取 3 帧（首/中/尾各略偏移 0.5 秒避免黑边），调用 `ffmpeg -ss ... -frames:v 1 -q:v 2`，输出到 `data/resource_library/keyframes/asset_{id}/segment_{id}/`。

### indexer.py — 核心索引流程

**`ResourceIndexer.ingest_resource()` 完整流程：**

```
DownloadedResource
    │
    ├─(1) _load_preferred_subtitles()  ──→ 选择最佳字幕 → parse_subtitle_file → TranscriptCue[]
    │
    ├─(2) detect_scene_segments()      ──→ SceneSegment[]
    │      + assign_transcripts_to_segments() 关联字幕
    │
    ├─(3) _ensure_asset()              ──→ 在 DB 中查找或创建 Asset 记录
    │      + clear_asset_resource_data() 清除旧数据
    │
    ├─(4) 写入 DB
    │      ├─ 逐条 add_asset_transcript(cue)
    │      └─ 逐条 add_asset_segment(segment)
    │
    ├─(5) 关键帧抽取
    │      └─ sample_segment_keyframes() → update_asset_segment(keyframe_paths)
    │
    └─(6) _index_segments()            ──→ 构建 FAISS 向量索引
            ├─ _segment_visual_embedding()  CLIP 图像嵌入（平均池化 + L2 归一化）
            └─ _segment_text_embedding()    CLIP 文本嵌入
```

**`rebuild_segment_indexes()`**: 从 DB 全量读取 segment 数据，重建两个 FAISS 索引（先 `fresh=True` 清空后重新 add）。

**嵌入生成：**
- CLIP 图像嵌入通过 `videoforge.skills.asset_tag.clip_embedder.get_image_embedding()` 获取
- 多帧取均值 + L2 归一化 → 最终向量
- CLIP 文本嵌入通过 `get_text_embedding()` 获取
- CLIP 不可用时静默返回 `None`，对应索引操作跳过

### search.py — 混合语义检索

```python
class ResourceSearcher:
    def search(self, query: str, limit: int = 10) -> list[ResourceSearchHit]:
```

**检索流程：**
1. `get_text_embedding(query)` 生成 CLIP 文本向量
2. 同时查 `data/segment_visual_index` 和 `data/segment_text_index` 两个 FAISS 索引（各取 `limit × 2`）
3. 合并两路结果，按三段加权排序：

   ```
   final_score = 0.45 * visual_score + 0.45 * transcript_score + 0.10 * quality_score
   ```

4. **`match_type`** 判定：
   - visual > 0 且 text > 0 → `"hybrid"`
   - 仅 visual > 0 → `"visual"`
   - 仅 text > 0 → `"text"`

**`_compute_quality_bonus(segment)`** 评分偏好：
- 时长 8–20s: +0.2 | 5–30s: +0.1
- 转录文本 > 50 字: +0.2 | > 20 字: +0.1
- 关键帧 ≥ 3 张: +0.1
- 基础分 0.5，上限 1.0

---

## CLI 新增命令

```
# 从 URL 导入（YouTube/Bilibili 等，调用 yt-dlp）
python -m videoforge.cli ingest-url <url>

# 从本地文件导入
python -m videoforge.cli ingest-local <path> [--subtitle <vtt/srt>]

# 语义搜索片段
python -m videoforge.cli search-segments "<query>" [--limit 10]

# 重建 FAISS 索引（从 DB 重新构建）
python -m videoforge.cli rebuild-segment-index
```

---

## 与现有 LocalFAISSProvider 的关系

两套独立的 FAISS 索引，互不影响：

| | LocalFAISSProvider | ResourceSearcher |
|---|---|---|
| 索引路径 | `data/faiss_index` (VectorStore 默认) | `data/segment_visual_index` + `data/segment_text_index` |
| 索引粒度 | Asset 级 | Segment 级 |
| 用途 | 素材检索 | 片段检索（更精细） |

---

## 已知问题 / 边界情况

### 中高优先级

1. **SQLite 外键约束未启用** — `Database.__init__` 没有执行 `PRAGMA foreign_keys = ON;`，`ON DELETE CASCADE` 不会生效。删除 asset 后 transcripts 和 segments 变为孤儿数据。

2. **无数据库迁移机制** — `CREATE TABLE IF NOT EXISTS` 只在首次创建时生效。已存在数据库文件（旧版本）不会自动获得 `asset_transcripts` 和 `asset_segments` 表，新功能静默不可用。

3. **`clear_asset_resource_data` 的时机风险** — `ingest_resource` 中先清除旧数据后逐步写入新数据。如果 ingest 中途崩溃，asset 的字幕和片段已删但新数据不完整。建议用事务包裹。

### 中优先级

4. **`find_related_files` 文件前缀匹配** — 如果 output 目录有命名相似的文件（如 `demo.mp4` 和 `demo_trimmed.mp4`），`demo.mp4` 的关联文件搜索可能错误匹配到 `demo_trimmed` 的文件。

5. **全局索引路径** — `SEGMENT_VISUAL_INDEX` 和 `SEGMENT_TEXT_INDEX` 是模块级常量，多项目或测试并行时冲突。建议可配置化。

6. **`download_video_resource` 取最新文件** — 通过 mtime 排序取最新视频，多用户并发时不可靠。最好从 yt-dlp 输出模板精确匹配。

7. **`normalize_segments` 首段过短处理** — 第一个 segment 即使很短也保留（无前驱可并入）。这会出现在视频开头有黑场/静音时。

### 低优先级

8. CLIP embedding 是可选依赖（`try/except` 包裹 import），失败时日志仅 DEBUG 级别，用户不易察觉。
9. 项目完全没有单元测试。

---

## 依赖

已在 `pyproject.toml` 中覆盖或需安装：

| 依赖 | 用途 | 备注 |
|------|------|------|
| `faiss-cpu` >= 1.7.4 | 向量索引 | 必需 |
| `scenedetect` >= 0.6 | 场景检测 | 不可用时回退固定窗口 |
| CLIP (`openai/CLIP`) | 视觉+文本嵌入 | 不可用时跳过索引 |
| `torch` | CLIP 运行时 | CLIP 的依赖 |
| `yt-dlp` | 视频下载 | 仅 `ingest-url` 需要 |
| `ffmpeg` | 关键帧抽取 | 系统级依赖 |

---

## 验证步骤

```bash
# 编译检查
python -m compileall -q videoforge

# 查看 CLI
python -m videoforge.cli --help

# 单元测试（待实现，当前无测试）
# python -m pytest tests/

# 集成测试（需要有 test.mp4 和对应字幕）
python -m videoforge.cli ingest-local test.mp4
python -m videoforge.cli search-segments "水分子包围离子" --limit 3
python -m videoforge.cli rebuild-segment-index
```
