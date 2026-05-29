from __future__ import annotations

import os
import re
from pathlib import Path

import yaml
from dotenv import load_dotenv

_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _resolve_env_vars(value: str) -> str:
    """将 ${ENV_VAR} 替换为环境变量的值"""
    def _replace(match: re.Match) -> str:
        var_name = match.group(1)
        return os.environ.get(var_name, "")
    return _ENV_VAR_PATTERN.sub(_replace, value)


def _resolve_recursive(obj: dict | list | str) -> dict | list | str:
    """递归解析配置中的环境变量引用"""
    if isinstance(obj, str):
        return _resolve_env_vars(obj)
    if isinstance(obj, dict):
        return {k: _resolve_recursive(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_recursive(item) for item in obj]
    return obj


def load_config(config_path: str | Path | None = None) -> dict:
    """加载配置文件。优先加载 config.local.yaml，回退到 config.yaml。"""
    project_root = Path(__file__).resolve().parent.parent
    
    # 强制加载项目根目录的 .env 文件
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)

    if config_path:
        path = Path(config_path)
    else:
        local_path = project_root / "config.local.yaml"
        default_path = project_root / "config.yaml"
        path = local_path if local_path.exists() else default_path

    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")

    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return _resolve_recursive(config)
