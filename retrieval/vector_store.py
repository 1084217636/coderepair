"""
本地持久化向量存储

使用 sqlite3 维护一个轻量向量库，按 collection 保存 chunk 向量和元数据。
当前目标不是高性能 ANN，而是给项目补上一条稳定、可持久化的向量 RAG 主链。
"""
from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

from core.logger import get_logger

logger = get_logger(__name__)


class SQLiteVectorStore:
    """基于 sqlite 的轻量向量存储。"""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger(__name__)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS collections (
                    name TEXT PRIMARY KEY,
                    manifest TEXT NOT NULL,
                    dimension INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vectors (
                    collection_name TEXT NOT NULL,
                    chunk_id TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    language TEXT NOT NULL,
                    start_line INTEGER NOT NULL,
                    end_line INTEGER NOT NULL,
                    summary TEXT,
                    chunk_kind TEXT DEFAULT '',
                    symbol TEXT DEFAULT '',
                    text TEXT NOT NULL,
                    vector_json TEXT NOT NULL,
                    PRIMARY KEY (collection_name, chunk_id)
                )
                """
            )
            existing_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(vectors)").fetchall()
            }
            if "chunk_kind" not in existing_columns:
                conn.execute("ALTER TABLE vectors ADD COLUMN chunk_kind TEXT DEFAULT ''")
            if "symbol" not in existing_columns:
                conn.execute("ALTER TABLE vectors ADD COLUMN symbol TEXT DEFAULT ''")

    def needs_reindex(self, collection_name: str, manifest: str, dimension: int) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT manifest, dimension FROM collections WHERE name = ?",
                (collection_name,),
            ).fetchone()
        if row is None:
            return True
        return row["manifest"] != manifest or row["dimension"] != dimension

    def replace_collection(
        self,
        collection_name: str,
        manifest: str,
        dimension: int,
        rows: Iterable[Dict[str, Any]],
    ) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM vectors WHERE collection_name = ?", (collection_name,))
            conn.execute(
                """
                INSERT INTO collections(name, manifest, dimension, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    manifest = excluded.manifest,
                    dimension = excluded.dimension,
                    updated_at = excluded.updated_at
                """,
                (collection_name, manifest, dimension, datetime.now().isoformat()),
            )
            conn.executemany(
                """
                INSERT INTO vectors(
                    collection_name, chunk_id, relative_path, language,
                    start_line, end_line, summary, chunk_kind, symbol, text, vector_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        collection_name,
                        row["chunk_id"],
                        row["relative_path"],
                        row["language"],
                        row["start_line"],
                        row["end_line"],
                        row.get("summary", ""),
                        row.get("chunk_kind", "chunk"),
                        row.get("symbol", ""),
                        row["text"],
                        json.dumps(row["vector"]),
                    )
                    for row in rows
                ],
            )
        self.logger.info(
            f"[VectorStore] 集合已刷新 | collection={collection_name} | db={self.db_path}"
        )

    def search(
        self,
        collection_name: str,
        query_vector: List[float],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT chunk_id, relative_path, language, start_line, end_line, summary, chunk_kind, symbol, text, vector_json
                FROM vectors
                WHERE collection_name = ?
                """,
                (collection_name,),
            ).fetchall()

        scored_results = []
        for row in rows:
            vector = json.loads(row["vector_json"])
            score = self._cosine_similarity(query_vector, vector)
            scored_results.append(
                {
                    "chunk_id": row["chunk_id"],
                    "relative_path": row["relative_path"],
                    "language": row["language"],
                    "start_line": row["start_line"],
                    "end_line": row["end_line"],
                    "summary": row["summary"],
                    "chunk_kind": row["chunk_kind"],
                    "symbol": row["symbol"],
                    "text": row["text"],
                    "vector_score": score,
                }
            )

        scored_results.sort(key=lambda item: item["vector_score"], reverse=True)
        return scored_results[:top_k]

    @staticmethod
    def _cosine_similarity(left: List[float], right: List[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        numerator = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return numerator / (left_norm * right_norm)
