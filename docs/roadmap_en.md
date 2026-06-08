# VideoForge Development Roadmap

[中文](roadmap.md)

## Project Vision

A "local-first" video automation workbench for educational content creators. Core differentiator: **No AI-generated visuals — intelligently retrieves and composes real footage** to ensure academic rigor.

---

## Implementation Principles

> **Validate core expressiveness first, then complete the intelligent pipeline, finally productionize**

---

## Phase 1: Rendering Pipeline Validation ✅ Complete

**Goal**: Verify HyperFrames can render "Huasheng Video" style outputs

| Item | Details |
|------|---------|
| **Estimated Time** | 1 week |
| **Actual Time** | Completed 2026-05-10 |
| **Tech Stack** | HyperFrames + GSAP + Tailwind CSS |

**Tech Choices Rationale**:
- HyperFrames: HTML-to-video, supports complex CSS animations, more flexible than FFmpeg compositing
- GSAP: Mature animation library, rich ecosystem, excellent performance
- Rejected: Remotion (requires React ecosystem), pure FFmpeg (weak animation capabilities)

**Deliverables**:
- [x] HTML/CSS video templates (dynamic subtitles, meme fly-ins, zoom transitions)
- [x] HyperFrames renderer integration
- [x] Manual data → MP4 output validation

---

## Phase 2: Competitor RAG Scriptwriting Pipeline ✅ Complete

**Goal**: Run the "competitor subtitles → extract structure → generate new script" RAG pipeline

| Item | Details |
|------|---------|
| **Estimated Time** | 2 weeks |
| **Actual Time** | Completed 2026-05-15 |
| **Tech Stack** | DeepSeek-V3 + Edge-TTS + WhisperX |

**Tech Choices Rationale**:
- DeepSeek-V3: Strong Chinese comprehension, stable JSON output, free credits via SiliconFlow
- Edge-TTS: Free Microsoft TTS, decent quality, zero cost
- WhisperX: Open-source word-level alignment, higher precision than vanilla Whisper
- Rejected: GPT-4 (expensive), Azure TTS (paid), vanilla Whisper (no word-level alignment)

**Deliverables**:
- [x] `ScriptWriterSkill` - DeepSeek RAG scriptwriting
- [x] `TTSSkill` - Edge-TTS voice generation
- [x] `TimestampAlignSkill` - WhisperX word-level timestamps
- [x] Structured JSON storyboard output

---

## Phase 3: Cloud Asset Retrieval ✅ Complete

**Goal**: Implement cloud-based asset auto-fetching (bypass local cold-start problem)

| Item | Details |
|------|---------|
| **Estimated Time** | 1 week |
| **Actual Time** | Completed 2026-05-20 |
| **Tech Stack** | yt-dlp + LLM keyword translation |

**Tech Choices Rationale**:
- yt-dlp: Supports 1000+ sites including YouTube/Bilibili, actively maintained
- LLM keyword translation: Chinese topic → English keywords, improves YouTube recall
- Rejected: Pexels API (limited asset types), custom crawlers (high maintenance)

**Deliverables**:
- [x] `YtdlpProvider` - YouTube/Bilibili asset download
- [x] English keyword prompt optimization
- [x] Fallback strategy (solid color placeholders)

---

## Phase 4: End-to-End Assembly & Rendering ✅ Complete

**Goal**: One-click sample educational video output

| Item | Details |
|------|---------|
| **Estimated Time** | 1 week |
| **Actual Time** | Completed 2026-05-22 |
| **Tech Stack** | Custom Pipeline Runner |

**Tech Choices Rationale**:
- Custom orchestrator: Simple and direct, avoids heavy frameworks like Airflow/Prefect
- YAML config-driven: Easy to adjust process order and parameters
- Rejected: LangGraph (state machine too complex), Airflow (high deployment cost)

**Deliverables**:
- [x] `PipelineRunner` core orchestrator
- [x] Script → TTS → Assets → Render full pipeline
- [x] `test_e2e.py` end-to-end tests

---

## Phase 5: Resource Library Infrastructure ✅ Complete

**Goal**: Establish local asset management system

| Item | Details |
|------|---------|
| **Estimated Time** | 1 week |
| **Actual Time** | Completed 2026-05-25 |
| **Tech Stack** | SQLite + JSON Sidecar |

**Tech Choices Rationale**:
- SQLite: Zero config, single file, perfect for local-first scenarios
- JSON Sidecar: Co-located with asset files, easy migration and backup
- Rejected: PostgreSQL (complex deployment), pure filesystem (inefficient queries)

**Deliverables**:
- [x] SQLite database (`storage/database.py`)
- [x] JSON Sidecar metadata (`storage/sidecar.py`)
- [x] Path utilities (`utils/paths.py`)

---

## Phase 6-7: CLIP Embeddings & FAISS Vector Search ✅ Complete

**Goal**: Make local assets "AI-searchable"

| Item | Details |
|------|---------|
| **Estimated Time** | 2 weeks |
| **Actual Time** | Completed 2026-05-28 |
| **Tech Stack** | OpenAI CLIP + FAISS |

**Tech Choices Rationale**:
- CLIP: Strong image-text alignment, supports Chinese/English text queries
- FAISS: Meta's high-performance vector search, GPU acceleration support
- Rejected: Pinecone (cloud service, privacy concerns), Milvus (complex deployment), Chroma (average performance)

**Deliverables**:
- [x] `CLIPEmbedder` - Video frame vectorization
- [x] `VectorStore` - FAISS index management
- [x] `LocalFaissProvider` - Local-first retrieval

---

## Phase 8-9: Auto-Ingest & RAG Templates ✅ Complete

**Goal**: Automated asset ingestion + narrative structure template library

| Item | Details |
|------|---------|
| **Estimated Time** | 2 weeks |
| **Actual Time** | Completed 2026-06-02 |
| **Tech Stack** | PySceneDetect + MD5/pHash + LLM structure extraction |

**Tech Choices Rationale**:
- PySceneDetect: Content-based scene splitting, smarter than fixed-interval slicing
- MD5 + pHash: Exact dedup + perceptual dedup, double protection
- LLM structure extraction: Learn narrative patterns from competitor videos
- Rejected: Fixed-duration slicing (wastes storage), MD5-only dedup (can't handle transcoding)

**Deliverables**:
- [x] `DedupService` - Duplicate detection
- [x] Auto-slice ingestion pipeline
- [x] `RAGTemplateExtractor` - Narrative structure extraction
- [x] Template library storage

---

## Phase 10: Web UI Workbench 🔜 Next Phase

**Goal**: Provide visual operation interface

| Item | Details |
|------|---------|
| **Estimated Time** | 4 weeks |
| **Tech Stack** | React + TypeScript + FastAPI + WebSocket |

**Tech Choices Rationale**:
- React: Mature ecosystem, rich component libraries (planning shadcn/ui)
- FastAPI: Python async framework, seamless integration with existing code
- WebSocket: Real-time rendering progress push
- Alternatives: Streamlit (rapid prototyping), Gradio (simple interactions)

**Planned Deliverables**:
- [ ] React + TypeScript frontend
- [ ] Project dashboard (create, list, status)
- [ ] Visual script editor (storyboard preview, drag-and-drop)
- [ ] Asset library panel (search, preview, tags)
- [ ] Rendering monitor & quality reports

---

## Phase 11: Agent Orchestration & Advanced Scheduling 📋 Planning

**Goal**: Intelligent Agent auto-decision making

| Item | Details |
|------|---------|
| **Estimated Time** | 3 weeks |
| **Tech Stack** | Claude API + Custom state machine (or LangGraph) |

**Tech Choices Rationale**:
- Claude API: Strong tool-calling capabilities, large context window
- Custom state machine preferred: Better control, easier debugging
- LangGraph alternative: Consider for complex flows

**Planned Deliverables**:
- [ ] Director Agent (intent parsing, task decomposition)
- [ ] State machine orchestration (interruptible, resumable)
- [ ] Error handling and fallback mechanisms
- [ ] Multi-Agent collaboration (Scriptwriter Agent, Reviewer Agent)

---

## Phase 12: Three-Tier QA System 📋 Planning

**Goal**: Prevent "blind box" outputs

| Item | Details |
|------|---------|
| **Estimated Time** | 2 weeks |
| **Tech Stack** | FFprobe + Whisper + Gemini Flash |

**Tech Choices Rationale**:
- FFprobe: Audio/video metadata detection, black screen/silence detection
- Whisper: ASR subtitle deviation comparison
- Gemini Flash: Multimodal consistency check, low cost

**Planned Deliverables**:
- [ ] Basic gate: FFprobe black screen/silence detection
- [ ] Sync gate: Whisper subtitle deviation validation
- [ ] Semantic gate: Multimodal consistency check (visuals vs narration)

---

## Long-term Vision (v2.0+)

| Feature | Description | Priority |
|---------|-------------|----------|
| Multi-language support | English, Japanese educational videos | P1 |
| Style transfer | Learn specific creator's editing style | P1 |
| Real-time preview | Edit and preview render effects simultaneously | P2 |
| Team collaboration | Shared asset library and templates | P2 |
| Plugin system | Third-party Skill/Provider extensions | P2 |
| Cloud deployment | Docker + K8s one-click deployment | P3 |

---

## Version Milestones

| Version | Goal | Status | Release Date |
|---------|------|--------|--------------|
| v0.1 | Rendering engine validation | ✅ | 2026-05-10 |
| v0.2 | Scriptwriting + TTS pipeline | ✅ | 2026-05-15 |
| v0.3 | Cloud assets + E2E | ✅ | 2026-05-22 |
| v0.4 | Local asset library + vector search | ✅ | 2026-05-28 |
| v0.5 | Auto-ingest + RAG templates | ✅ | 2026-06-02 |
| v0.6 | Web UI workbench | 🔜 | 2026-07 expected |
| v1.0 | Production ready | 📋 | 2026-Q4 expected |

---

## Contributing

Contributions welcome! Here are tasks suitable for new contributors:

### Good First Issues
- [ ] Add more TTS Providers (CosyVoice, Fish Audio)
- [ ] Improve CLI output format (progress bars, colors)
- [ ] Increase unit test coverage
- [ ] Improve error messages and logging

### Help Wanted
- [ ] Web UI frontend development (React)
- [ ] Windows compatibility testing and fixes
- [ ] Performance optimization (FAISS indexing, batch processing)

See the [Contributing Guide](../CONTRIBUTING.md) for how to get involved.

---

*Last updated: 2026-06-08*
