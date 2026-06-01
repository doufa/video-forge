"""SQLite 数据库存储

存储素材元数据、项目信息等。所有路径以相对路径存储。
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from videoforge.utils.paths import PROJECT_ROOT


@dataclass
class Asset:
    """素材记录"""
    id: int | None = None
    path: str = ""
    asset_type: str = "video"
    source: str = "local"
    original_query: str = ""
    original_url: str = ""
    filename_original: str = ""
    description: str = ""
    tags: list[str] | None = None
    embedding: bytes | None = None
    duration_sec: float | None = None
    width: int | None = None
    height: int | None = None
    file_size: int | None = None
    reviewed: bool = False
    created_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "asset_type": self.asset_type,
            "source": self.source,
            "original_query": self.original_query,
            "original_url": self.original_url,
            "filename_original": self.filename_original,
            "description": self.description,
            "tags": self.tags or [],
            "duration_sec": self.duration_sec,
            "width": self.width,
            "height": self.height,
            "file_size": self.file_size,
            "reviewed": self.reviewed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Database:
    """SQLite 项目与元数据存储"""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = PROJECT_ROOT / "data" / "videoforge.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> "Database":
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_tables()
        return self

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "Database":
        return self.connect()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def _init_tables(self) -> None:
        """创建基础表结构"""
        assert self._conn is not None
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                asset_type TEXT DEFAULT 'video',
                source TEXT DEFAULT 'local',
                original_query TEXT DEFAULT '',
                original_url TEXT DEFAULT '',
                filename_original TEXT DEFAULT '',
                description TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                embedding BLOB,
                duration_sec REAL,
                width INTEGER,
                height INTEGER,
                file_size INTEGER,
                reviewed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(asset_type);
            CREATE INDEX IF NOT EXISTS idx_assets_source ON assets(source);
            CREATE INDEX IF NOT EXISTS idx_assets_reviewed ON assets(reviewed);

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                topic TEXT,
                status TEXT DEFAULT 'draft',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS rag_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_channel TEXT,
                source_url TEXT,
                topic_domain TEXT,
                structure TEXT,
                techniques TEXT,
                embedding BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self._conn.commit()

    def add_asset(self, asset: Asset) -> int:
        """添加素材记录，返回新记录的 ID"""
        assert self._conn is not None
        cursor = self._conn.execute(
            """
            INSERT INTO assets (
                path, asset_type, source, original_query, original_url,
                filename_original, description, tags, embedding,
                duration_sec, width, height, file_size, reviewed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                asset.path,
                asset.asset_type,
                asset.source,
                asset.original_query,
                asset.original_url,
                asset.filename_original,
                asset.description,
                json.dumps(asset.tags or [], ensure_ascii=False),
                asset.embedding,
                asset.duration_sec,
                asset.width,
                asset.height,
                asset.file_size,
                1 if asset.reviewed else 0,
            ),
        )
        self._conn.commit()
        return cursor.lastrowid

    def get_asset(self, asset_id: int) -> Asset | None:
        """根据 ID 获取素材"""
        assert self._conn is not None
        row = self._conn.execute(
            "SELECT * FROM assets WHERE id = ?", (asset_id,)
        ).fetchone()
        return self._row_to_asset(row) if row else None

    def get_asset_by_path(self, path: str) -> Asset | None:
        """根据路径获取素材"""
        assert self._conn is not None
        row = self._conn.execute(
            "SELECT * FROM assets WHERE path = ?", (path,)
        ).fetchone()
        return self._row_to_asset(row) if row else None

    def update_asset(self, asset: Asset) -> bool:
        """更新素材记录"""
        assert self._conn is not None
        if asset.id is None:
            return False
        cursor = self._conn.execute(
            """
            UPDATE assets SET
                path = ?, asset_type = ?, source = ?, original_query = ?,
                original_url = ?, filename_original = ?, description = ?,
                tags = ?, embedding = ?, duration_sec = ?, width = ?,
                height = ?, file_size = ?, reviewed = ?
            WHERE id = ?
            """,
            (
                asset.path,
                asset.asset_type,
                asset.source,
                asset.original_query,
                asset.original_url,
                asset.filename_original,
                asset.description,
                json.dumps(asset.tags or [], ensure_ascii=False),
                asset.embedding,
                asset.duration_sec,
                asset.width,
                asset.height,
                asset.file_size,
                1 if asset.reviewed else 0,
                asset.id,
            ),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def delete_asset(self, asset_id: int) -> bool:
        """删除素材记录"""
        assert self._conn is not None
        cursor = self._conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def list_assets(
        self,
        asset_type: str | None = None,
        source: str | None = None,
        reviewed: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Asset]:
        """列出素材，支持过滤"""
        assert self._conn is not None
        conditions = []
        params: list[Any] = []

        if asset_type:
            conditions.append("asset_type = ?")
            params.append(asset_type)
        if source:
            conditions.append("source = ?")
            params.append(source)
        if reviewed is not None:
            conditions.append("reviewed = ?")
            params.append(1 if reviewed else 0)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"""
            SELECT * FROM assets
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_asset(row) for row in rows]

    def search_assets_by_tags(self, tags: list[str], match_all: bool = False) -> list[Asset]:
        """根据标签搜索素材"""
        assert self._conn is not None
        if not tags:
            return []

        if match_all:
            conditions = " AND ".join(f"tags LIKE ?" for _ in tags)
            params = [f'%"{tag}"%' for tag in tags]
        else:
            conditions = " OR ".join(f"tags LIKE ?" for _ in tags)
            params = [f'%"{tag}"%' for tag in tags]

        query = f"SELECT * FROM assets WHERE {conditions}"
        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_asset(row) for row in rows]

    def count_assets(self, asset_type: str | None = None) -> int:
        """统计素材数量"""
        assert self._conn is not None
        if asset_type:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM assets WHERE asset_type = ?", (asset_type,)
            ).fetchone()
        else:
            row = self._conn.execute("SELECT COUNT(*) FROM assets").fetchone()
        return row[0] if row else 0

    def get_total_size(self, asset_type: str | None = None) -> int:
        """统计素材总大小（字节）"""
        assert self._conn is not None
        if asset_type:
            row = self._conn.execute(
                "SELECT COALESCE(SUM(file_size), 0) FROM assets WHERE asset_type = ?",
                (asset_type,),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT COALESCE(SUM(file_size), 0) FROM assets"
            ).fetchone()
        return row[0] if row else 0

    def _row_to_asset(self, row: sqlite3.Row) -> Asset:
        """将数据库行转换为 Asset 对象"""
        tags_str = row["tags"] or "[]"
        try:
            tags = json.loads(tags_str)
        except json.JSONDecodeError:
            tags = []

        created_at = None
        if row["created_at"]:
            try:
                created_at = datetime.fromisoformat(row["created_at"])
            except ValueError:
                pass

        return Asset(
            id=row["id"],
            path=row["path"],
            asset_type=row["asset_type"],
            source=row["source"] or "local",
            original_query=row["original_query"] or "",
            original_url=row["original_url"] or "",
            filename_original=row["filename_original"] or "",
            description=row["description"] or "",
            tags=tags,
            embedding=row["embedding"],
            duration_sec=row["duration_sec"],
            width=row["width"],
            height=row["height"],
            file_size=row["file_size"],
            reviewed=bool(row["reviewed"]),
            created_at=created_at,
        )


def init_db() -> Database:
    """初始化数据库并返回连接"""
    db = Database()
    return db.connect()
