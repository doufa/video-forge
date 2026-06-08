# VideoForge

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Automated Knowledge Video Production System** — Intelligent retrieval and composition of real footage.

<p align="center">
  <img src="https://via.placeholder.com/800x400?text=VideoForge+Demo" alt="VideoForge Demo" width="600">
</p>

> 📹 A "local-first" video automation workbench for educational content creators.  
> Core differentiator: **No AI-generated visuals — intelligently retrieves and composes real footage** to ensure academic rigor.

[中文](README_ZH.md)

---

## ✨ Features

- 🎬 **RAG Scriptwriting**: Learn from competitor structures, auto-generate storyboards
- 🎤 **Multi-engine TTS**: Edge-TTS (free) / CosyVoice / ElevenLabs
- ⏱️ **Word-level Timestamps**: WhisperX alignment for word-by-word highlighting
- 🔍 **Smart Asset Search**: Local FAISS vector search → YouTube/Bilibili auto-download
- 🏷️ **Auto-tagging**: CLIP + Gemini vision models
- 🎥 **HTML Rendering**: HyperFrames + GSAP effects (subtitles, transitions, meme overlays)
- 📚 **Asset Library**: Auto-ingest, deduplication, scene splitting
- 🧩 **Modular Design**: Pluggable Skills, swappable Providers

---

## 🚀 Quick Start

### Requirements

- Python 3.11+
- Node.js 18+ (for HyperFrames rendering)
- FFmpeg (optional, for audio/video processing)

### Installation

```bash
# Clone the repository
git clone https://github.com/doufa/video-forge.git
cd video-forge

# Install Python dependencies
pip install -e ".[phase2]"

# Install the rendering engine
npm install hyperframes
```

### Configuration

```bash
# Copy the config template
cp .env.example .env

# Edit .env and fill in your API keys
# Recommended: SiliconFlow DeepSeek-V3 (free credits on signup)
```

### Run the Demo

```bash
# Generate a "salt dissolving" educational video
python demo_salt_dissolve.py
```

See the [Demo Guide](docs/demo_guide.md) for detailed instructions.

---

## 📐 Architecture

```
Pipeline Runner → Skill Orchestration (config-driven, pluggable Providers)
                    ├── script_writer    RAG scriptwriting
                    ├── tts_generate     TTS (edge-tts / CosyVoice / ElevenLabs)
                    ├── timestamp_align  Word-level timestamps (WhisperX)
                    ├── asset_search     Multi-source search (local FAISS → yt-dlp → Pexels)
                    ├── asset_tag        Auto-tagging (CLIP + Gemini)
                    ├── video_render     HyperFrames rendering
                    ├── subtitle_export  SRT subtitle export
                    └── qa_check         3-tier quality verification
```

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [Demo Guide](docs/demo_guide.md) | ⭐ Quick start tutorial |
| [Roadmap](docs/roadmap.md) | Project planning & progress |
| [Design Doc](VideoForge：知识科普视频自动化生产系统方案设计%20(开工版).md) | Technical design (Chinese) |
| [Contributing](CONTRIBUTING.md) | How to contribute |
| [Changelog](CHANGELOG.md) | Version history |

---

## 🗺️ Roadmap

| Version | Goal | Status |
|---------|------|--------|
| v0.1 | Rendering engine validation | ✅ |
| v0.2 | Scriptwriting + TTS pipeline | ✅ |
| v0.3 | Cloud assets + E2E | ✅ |
| v0.4 | Local asset library + vector search | ✅ |
| v0.5 | Auto-ingest + RAG templates | ✅ |
| v0.6 | Web UI workbench | 🔜 |
| v1.0 | Production ready | 📋 |

See the [full roadmap](docs/roadmap.md) for details.

---

## 🤝 Contributing

Contributions are welcome! Whether it's code, bug reports, or feature suggestions.

- 📖 Read the [Contributing Guide](CONTRIBUTING.md)
- 🐛 Submit a [Bug Report](../../issues/new?template=bug_report.yml)
- ✨ Propose a [Feature Request](../../issues/new?template=feature_request.yml)
- 💬 Join the [Discussions](../../discussions)

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

## 🙏 Acknowledgments

- [HyperFrames](https://hyperframes.ai/) - HTML video rendering engine
- [Edge-TTS](https://github.com/rany2/edge-tts) - Free TTS engine
- [WhisperX](https://github.com/m-bain/whisperX) - Word-level timestamp alignment
- [CLIP](https://github.com/openai/CLIP) - Visual semantic embeddings
- [FAISS](https://github.com/facebookresearch/faiss) - Vector search engine
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Video download tool
