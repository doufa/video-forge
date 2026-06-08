# 贡献指南

[English](CONTRIBUTING_EN.md)

感谢你对 VideoForge 的关注！我们欢迎各种形式的贡献。

## 如何贡献

### 报告 Bug

1. 先在 [Issues](../../issues) 中搜索是否已有相同问题
2. 如果没有，创建新 Issue，使用 Bug Report 模板
3. 提供复现步骤、环境信息、错误日志

### 提出新功能

1. 先在 [Issues](../../issues) 或 [Discussions](../../discussions) 中讨论
2. 描述使用场景和预期效果
3. 等待维护者反馈后再开始开发

### 提交代码

1. Fork 本仓库
2. 创建功能分支：`git checkout -b feature/your-feature`
3. 编写代码和测试
4. 确保通过所有检查：
   ```bash
   # 代码格式检查
   ruff check .
   ruff format --check .
   
   # 运行测试
   pytest
   ```
5. 提交 PR，填写模板信息

## 开发环境设置

```bash
# 克隆仓库
git clone https://github.com/doufa/video-forge.git
cd video-forge

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装开发依赖
pip install -e ".[dev,phase2,phase3]"

# 安装 HyperFrames（渲染引擎）
npm install hyperframes

# 复制环境变量模板
cp .env.example .env
# 编辑 .env 填入你的 API Key
```

## 代码规范

### Python

- 使用 [Ruff](https://github.com/astral-sh/ruff) 进行格式化和 lint
- 行宽限制：100 字符
- 目标 Python 版本：3.11+
- 类型注解：鼓励但不强制

### 命名约定

- 文件名：`snake_case.py`
- 类名：`PascalCase`
- 函数/变量：`snake_case`
- 常量：`UPPER_SNAKE_CASE`

### 提交信息

遵循 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/) 规范：

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

类型：
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式（不影响逻辑）
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建/工具链

示例：
```
feat(script_writer): add support for custom prompt templates
fix(tts): handle edge-tts timeout on long text
docs: update demo guide with troubleshooting section
```

## 项目结构

```
videoforge/
├── skills/           # 各功能模块（编剧、配音、检索等）
│   ├── script_writer/
│   ├── tts_generate/
│   ├── asset_search/
│   └── ...
├── pipeline/         # 流水线调度
├── storage/          # 数据持久化（SQLite、FAISS）
├── resource_library/ # 资源库管理
├── utils/            # 工具函数
└── cli.py            # 命令行入口
```

## 测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_search.py

# 运行带覆盖率
pytest --cov=videoforge

# 运行端到端测试（需要 API Key）
pytest test_e2e.py -v
```

## 文档

- 代码注释使用中文或英文均可
- 公开 API 需要 docstring
- 复杂逻辑添加行内注释

## 许可证

贡献的代码将采用 [MIT License](LICENSE) 发布。

---

如有疑问，欢迎在 [Discussions](../../discussions) 中提问！
