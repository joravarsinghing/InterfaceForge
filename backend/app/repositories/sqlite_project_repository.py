"""SQLite project repository for lightweight local persistence."""

import json
import os
import sqlite3
from typing import List, Optional

from app.core.config import settings
from app.models.schema import Project


class SQLiteProjectRepository:
    """Repository managing local SQLite storage for canonical project models."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        path = db_path or getattr(settings, "db_path", "artifacts/interfaceforge.db")
        self.db_path: str = str(path)
        self._shared_conn: Optional[sqlite3.Connection] = None
        if self.db_path == ":memory:":
            self._shared_conn = sqlite3.connect(":memory:")
            self._shared_conn.row_factory = sqlite3.Row
        self._bootstrap_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create and return a SQLite connection."""
        if self._shared_conn is not None:
            return self._shared_conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _bootstrap_db(self) -> None:
        """Initialize database directory and project table schema."""
        if self.db_path != ":memory:":
            db_dir = os.path.dirname(os.path.abspath(self.db_path))
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    project_token TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    current_schema_revision INTEGER NOT NULL,
                    current_model_revision INTEGER,
                    last_known_good_model_revision INTEGER,
                    data_json TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save(self, project: Project) -> Project:
        """Create or update a project record in SQLite database."""
        data_json = project.model_dump_json()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO projects (
                    project_id, project_token, schema_version, state,
                    created_at, updated_at, current_schema_revision,
                    current_model_revision, last_known_good_model_revision,
                    data_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    project_token = excluded.project_token,
                    schema_version = excluded.schema_version,
                    state = excluded.state,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    current_schema_revision = excluded.current_schema_revision,
                    current_model_revision = excluded.current_model_revision,
                    last_known_good_model_revision = excluded.last_known_good_model_revision,
                    data_json = excluded.data_json
                """,
                (
                    project.project_id,
                    project.project_token,
                    project.schema_version,
                    project.state.value if hasattr(project.state, "value") else str(project.state),
                    project.created_at,
                    project.updated_at,
                    project.current_schema_revision,
                    project.current_model_revision,
                    project.last_known_good_model_revision,
                    data_json,
                ),
            )
            conn.commit()
        return project

    def get(self, project_id: str) -> Optional[Project]:
        """Fetch a project by project_id from SQLite database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data_json FROM projects WHERE project_id = ?", (project_id,))
            row = cursor.fetchone()
            if not row:
                return None
            data_dict = json.loads(row["data_json"])
            return Project.model_validate(data_dict)

    def delete(self, project_id: str) -> bool:
        """Delete a project from SQLite database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
            conn.commit()
            return cursor.rowcount > 0

    def list_all(self) -> List[Project]:
        """List all projects from SQLite database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data_json FROM projects ORDER BY updated_at DESC")
            rows = cursor.fetchall()
            return [Project.model_validate(json.loads(row["data_json"])) for row in rows]
