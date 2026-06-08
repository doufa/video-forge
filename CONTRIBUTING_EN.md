# Contributing Guide

Thank you for your interest in VideoForge! We welcome contributions of all kinds.

## How to Contribute

### Reporting Bugs

1. Search [existing Issues](../../issues) first to avoid duplicates
2. If not found, create a new Issue using the Bug Report template
3. Provide reproduction steps, environment info, and error logs

### Proposing Features

1. Start a discussion in [Issues](../../issues) or [Discussions](../../discussions)
2. Describe your use case and expected behavior
3. Wait for maintainer feedback before starting development

### Submitting Code

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Write code and tests
4. Ensure all checks pass:
   ```bash
   # Code linting
   ruff check .
   ruff format --check .
   
   # Run tests
   pytest
   ```
5. Submit a PR using the template

## Development Setup

```bash
# Clone the repo
git clone https://github.com/doufa/video-forge.git
cd video-forge

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dev dependencies
pip install -e ".[dev,phase2,phase3]"

# Install HyperFrames (rendering engine)
npm install hyperframes

# Copy environment template
cp .env.example .env
# Edit .env with your API keys
```

## Code Standards

### Python

- Use [Ruff](https://github.com/astral-sh/ruff) for formatting and linting
- Line length limit: 100 characters
- Target Python version: 3.11+
- Type hints: encouraged but not required

### Naming Conventions

- File names: `snake_case.py`
- Class names: `PascalCase`
- Functions/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Code style (no logic changes)
- `refactor`: Refactoring
- `test`: Tests
- `chore`: Build/tooling

Examples:
```
feat(script_writer): add support for custom prompt templates
fix(tts): handle edge-tts timeout on long text
docs: update demo guide with troubleshooting section
```

## Project Structure

```
videoforge/
├── skills/           # Feature modules (scriptwriting, TTS, search, etc.)
│   ├── script_writer/
│   ├── tts_generate/
│   ├── asset_search/
│   └── ...
├── pipeline/         # Pipeline orchestration
├── storage/          # Data persistence (SQLite, FAISS)
├── resource_library/ # Asset library management
├── utils/            # Utility functions
└── cli.py            # CLI entry point
```

## Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_search.py

# Run with coverage
pytest --cov=videoforge

# Run E2E tests (requires API keys)
pytest test_e2e.py -v
```

## Documentation

- Code comments can be in Chinese or English
- Public APIs should have docstrings
- Complex logic should have inline comments

## License

Contributed code will be released under the [MIT License](LICENSE).

---

Questions? Feel free to ask in [Discussions](../../discussions)!
