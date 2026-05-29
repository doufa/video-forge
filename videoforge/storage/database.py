from __future__ import annotations

import sqlite3
from pathlib import Path


class Database:
    """SQLite 项目与元数据存储"""

    def __init__(self, db_path: str | Path = "data/videoforge.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def _init_tables(self) -> None:
        """创建基础表结构"""
        assert self._conn is not None
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                topic TEXT,
                status TEXT DEFAULT 'draft',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL UNIQUE,
                asset_type TEXT DEFAULT 'video',
                description TEXT,
                tags TEXT,
                reviewed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self._conn.commit()
