from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


class ProjectStore:
    """Append-oriented local project and sample registry."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT NOT NULL DEFAULT '',
                    created_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS samples (
                    sample_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(project_id),
                    sample_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    sample_role TEXT NOT NULL DEFAULT 'sample',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    latest_analysis_json TEXT,
                    added_utc TEXT NOT NULL,
                    UNIQUE(project_id, sample_name)
                );
                """
            )

    def create_project(self, name: str, description: str = "") -> str:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Project name cannot be empty")
        project_id = uuid.uuid4().hex
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO projects(project_id, name, description, created_utc) VALUES (?, ?, ?, ?)",
                (project_id, clean_name, description.strip(), datetime.now(timezone.utc).isoformat()),
            )
        return project_id

    def list_projects(self) -> pd.DataFrame:
        with self._connect() as connection:
            return pd.read_sql_query(
                "SELECT project_id, name, description, created_utc FROM projects ORDER BY created_utc, name",
                connection,
            )

    def add_sample(
        self,
        project_id: str,
        sample_name: str,
        file_path: str | Path,
        sample_role: str = "sample",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        clean_name = sample_name.strip()
        if not clean_name:
            raise ValueError("Sample name cannot be empty")
        sample_id = uuid.uuid4().hex
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO samples(
                    sample_id, project_id, sample_name, file_path, sample_role, metadata_json, added_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sample_id,
                    project_id,
                    clean_name,
                    str(Path(file_path).resolve()),
                    sample_role,
                    json.dumps(metadata or {}, sort_keys=True),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        return sample_id

    def list_samples(self, project_id: str) -> pd.DataFrame:
        with self._connect() as connection:
            return pd.read_sql_query(
                """
                SELECT sample_id, project_id, sample_name, file_path, sample_role,
                       metadata_json, latest_analysis_json, added_utc
                FROM samples WHERE project_id = ? ORDER BY added_utc, sample_name
                """,
                connection,
                params=(project_id,),
            )

    def record_analysis(self, sample_id: str, result: dict[str, Any]) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE samples SET latest_analysis_json = ? WHERE sample_id = ?",
                (json.dumps(result, sort_keys=True), sample_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Unknown sample_id: {sample_id}")
