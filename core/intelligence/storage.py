"""
core/intelligence/storage.py — Transactional SQLite persistence engine for J.A.R.V.I.S. Intelligence Platform.

Uses Python standard library sqlite3 with Write-Ahead Logging (WAL) for high-performance,
thread-safe, zero-dependency persistence of missions, neural memories, skills, research, and audit logs.
Enforces strict secret redaction to ensure credentials never enter the database.
"""
from __future__ import annotations

from dataclasses import asdict
import json
import logging
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import (
    AuditRecord,
    MemoryCategory,
    MemoryRecord,
    Mission,
    MissionArtifact,
    MissionStatus,
    MissionStep,
    ResearchClaim,
    ResearchReport,
    ResearchSource,
    SkillDefinition,
    SkillStatus,
    SkillStep,
    StepStatus,
)

logger = logging.getLogger("JARVIS.Intelligence.Storage")

_SECRET_PATTERN = re.compile(r"(?i)(api[_-]?key|token|secret|password|bearer|auth|credential)")


def redact_secrets(data: Any) -> Any:
    """Recursively scrubs API keys, tokens, and credentials from dictionaries/lists/strings."""
    if isinstance(data, str):
        cleaned = re.sub(r"sk-[a-zA-Z0-9_\-]{15,}", "[REDACTED_API_KEY]", data)
        cleaned = re.sub(r"(?i)(password|secret|token)\s*[:=]\s*[^\s,;]+", r"\1=[REDACTED]", cleaned)
        return cleaned
    elif isinstance(data, dict):
        clean = {}
        for k, v in data.items():
            if _SECRET_PATTERN.search(str(k)):
                clean[k] = "[REDACTED]"
            else:
                clean[k] = redact_secrets(v)
        return clean
    elif isinstance(data, list):
        return [redact_secrets(item) for item in data]
    return data


class IntelligenceStorage:
    """Thread-safe SQLite storage for the J.A.R.V.I.S. Intelligence Platform."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            base_dir = Path(__file__).resolve().parent.parent.parent
            db_path = base_dir / "memory" / "intelligence.db"
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self) -> None:
        with self._lock, self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    migrated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS missions (
                    mission_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    original_instruction TEXT,
                    project_id TEXT DEFAULT 'default',
                    status TEXT NOT NULL,
                    current_step_index INTEGER DEFAULT 0,
                    requires_approval INTEGER DEFAULT 0,
                    approval_token TEXT,
                    final_report TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    data_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS mission_steps (
                    step_id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    description TEXT NOT NULL,
                    capability TEXT NOT NULL,
                    status TEXT NOT NULL,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 2,
                    data_json TEXT NOT NULL,
                    started_at REAL,
                    completed_at REAL,
                    FOREIGN KEY(mission_id) REFERENCES missions(mission_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS neural_memories (
                    record_id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    project_id TEXT DEFAULT 'default',
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source TEXT,
                    confidence REAL DEFAULT 1.0,
                    importance REAL DEFAULT 0.5,
                    sensitivity TEXT DEFAULT 'internal',
                    tags_json TEXT,
                    access_count INTEGER DEFAULT 0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    last_accessed_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS skills (
                    skill_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    version TEXT DEFAULT '1.0.0',
                    category TEXT DEFAULT 'general',
                    status TEXT NOT NULL,
                    risk_level TEXT DEFAULT 'low',
                    requires_confirmation INTEGER DEFAULT 0,
                    definition_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS research_reports (
                    report_id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    executive_summary TEXT,
                    data_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS audit_logs (
                    event_id TEXT PRIMARY KEY,
                    timestamp REAL NOT NULL,
                    event_type TEXT NOT NULL,
                    component TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    security_flag INTEGER DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_missions_status ON missions(status);
                CREATE INDEX IF NOT EXISTS idx_memories_cat_proj ON neural_memories(category, project_id);
                CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_logs(timestamp);
                """
            )
            # Record initial schema version 1
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM schema_version WHERE version = 1")
            if cur.fetchone()[0] == 0:
                conn.execute("INSERT INTO schema_version (version, migrated_at) VALUES (1, ?)", (time.time(),))
            conn.commit()

    # ── Mission Persistence ───────────────────────────────────────────────────

    def save_mission(self, mission: Mission) -> None:
        mission.updated_at = time.time()
        data_clean = redact_secrets(mission.to_dict())
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO missions (
                    mission_id, title, objective, original_instruction, project_id,
                    status, current_step_index, requires_approval, approval_token,
                    final_report, created_at, updated_at, data_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mission.mission_id,
                    mission.title,
                    mission.objective,
                    mission.original_instruction,
                    mission.project_id or "default",
                    mission.status.value,
                    mission.current_step_index,
                    1 if mission.requires_approval else 0,
                    mission.approval_token,
                    mission.final_report,
                    mission.created_at,
                    mission.updated_at,
                    json.dumps(data_clean, ensure_ascii=False),
                ),
            )
            for step in mission.steps:
                step_data = redact_secrets(step.to_dict())
                conn.execute(
                    """
                    INSERT OR REPLACE INTO mission_steps (
                        step_id, mission_id, description, capability, status,
                        retry_count, max_retries, data_json, started_at, completed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        step.step_id,
                        mission.mission_id,
                        step.description,
                        step.capability,
                        step.status.value,
                        step.retry_count,
                        step.max_retries,
                        json.dumps(step_data, ensure_ascii=False),
                        step.started_at,
                        step.completed_at,
                    ),
                )
            conn.commit()

    def get_mission(self, mission_id: str) -> Optional[Mission]:
        with self._lock, self._get_connection() as conn:
            row = conn.execute("SELECT data_json FROM missions WHERE mission_id = ?", (mission_id,)).fetchone()
            if not row:
                return None
            data = json.loads(row["data_json"])
            return Mission.from_dict(data)

    def list_missions(self, limit: int = 50, project_id: Optional[str] = None) -> List[Mission]:
        with self._lock, self._get_connection() as conn:
            if project_id:
                rows = conn.execute(
                    "SELECT data_json FROM missions WHERE project_id = ? ORDER BY updated_at DESC LIMIT ?",
                    (project_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT data_json FROM missions ORDER BY updated_at DESC LIMIT ?", (limit,)
                ).fetchall()
            return [Mission.from_dict(json.loads(r["data_json"])) for r in rows]

    # ── Neural Memory Persistence ─────────────────────────────────────────────

    def save_memory(self, record: MemoryRecord) -> None:
        record.updated_at = time.time()
        record.content = str(redact_secrets(record.content))
        record.content = redact_secrets(record.content)
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO neural_memories (
                    record_id, category, project_id, title, content, source,
                    confidence, importance, sensitivity, tags_json, access_count,
                    created_at, updated_at, last_accessed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.record_id,
                    record.category.value,
                    record.project_id,
                    record.title,
                    record.content,
                    record.source,
                    record.confidence,
                    record.importance,
                    record.sensitivity,
                    json.dumps(record.tags, ensure_ascii=False),
                    record.access_count,
                    record.created_at,
                    record.updated_at,
                    record.last_accessed_at,
                ),
            )
            conn.commit()

    def get_memory(self, record_id: str) -> Optional[MemoryRecord]:
        with self._lock, self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM neural_memories WHERE record_id = ? OR title = ?", (record_id, record_id)
            ).fetchone()
            if not row:
                return None
            return self._row_to_memory(row)

    def search_memories(
        self,
        query: str = "",
        category: Optional[MemoryCategory] = None,
        project_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[MemoryRecord]:
        with self._lock, self._get_connection() as conn:
            sql = "SELECT * FROM neural_memories WHERE 1=1"
            params: List[Any] = []
            if category:
                sql += " AND category = ?"
                params.append(category.value)
            if project_id:
                sql += " AND project_id = ?"
                params.append(project_id)
            if query.strip():
                terms = [t.strip() for t in query.split() if len(t.strip()) > 1]
                if terms:
                    term_clauses = []
                    for t in terms:
                        term_clauses.append("(title LIKE ? OR content LIKE ?)")
                        kw = f"%{t}%"
                        params.extend([kw, kw])
                    sql += f" AND ({' OR '.join(term_clauses)})"
            sql += " ORDER BY importance DESC, updated_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_memory(r) for r in rows]

    def delete_memory(self, record_id: str) -> bool:
        with self._lock, self._get_connection() as conn:
            res = conn.execute("DELETE FROM neural_memories WHERE record_id = ? OR title = ?", (record_id, record_id))
            conn.commit()
            return res.rowcount > 0

    def record_audit(self, action: str, target: str = "", outcome: str = "", details: Optional[Dict[str, Any]] = None) -> None:
        d = dict(details or {})
        if target:
            d["target"] = target
        if outcome:
            d["outcome"] = outcome
        rec = AuditRecord(
            event_type="audit",
            component="System",
            action=action,
            details=d,
        )
        self.log_audit(rec)

    def get_recent_audit_records(self, limit: int = 50) -> List[AuditRecord]:
        return self.get_audit_trail(limit=limit)

    def clear_audit_records(self, older_than_days: int = 30) -> int:
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            if older_than_days <= 0:
                cursor.execute("DELETE FROM audit_logs")
            else:
                cutoff = time.time() - (older_than_days * 86400)
                cursor.execute("DELETE FROM audit_logs WHERE timestamp < ?", (cutoff,))
            conn.commit()
            return cursor.rowcount

    def _row_to_memory(self, row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            record_id=row["record_id"],
            category=MemoryCategory(row["category"]),
            project_id=row["project_id"],
            title=row["title"],
            content=row["content"],
            source=row["source"],
            confidence=row["confidence"],
            importance=row["importance"],
            sensitivity=row["sensitivity"],
            tags=json.loads(row["tags_json"]) if row["tags_json"] else [],
            access_count=row["access_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_accessed_at=row["last_accessed_at"],
        )

    # ── Skill Persistence ─────────────────────────────────────────────────────

    def save_skill(self, skill: SkillDefinition) -> None:
        skill.updated_at = time.time()
        data_clean = redact_secrets(skill.to_dict())
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO skills (
                    skill_id, name, description, version, category, status,
                    risk_level, requires_confirmation, definition_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    skill.skill_id,
                    skill.name,
                    skill.description,
                    skill.version,
                    skill.category,
                    skill.status.value,
                    skill.risk_level,
                    1 if skill.requires_confirmation else 0,
                    json.dumps(data_clean, ensure_ascii=False),
                    skill.created_at,
                    skill.updated_at,
                ),
            )
            conn.commit()

    def get_skill(self, skill_id: str) -> Optional[SkillDefinition]:
        with self._lock, self._get_connection() as conn:
            row = conn.execute("SELECT definition_json FROM skills WHERE skill_id = ?", (skill_id,)).fetchone()
            if not row:
                return None
            return SkillDefinition.from_dict(json.loads(row["definition_json"]))

    def list_skills(self, status: Optional[SkillStatus] = None) -> List[SkillDefinition]:
        with self._lock, self._get_connection() as conn:
            if status:
                rows = conn.execute("SELECT definition_json FROM skills WHERE status = ?", (status.value,)).fetchall()
            else:
                rows = conn.execute("SELECT definition_json FROM skills ORDER BY name ASC").fetchall()
            return [SkillDefinition.from_dict(json.loads(r["definition_json"])) for r in rows]

    # ── Research Report Persistence ───────────────────────────────────────────

    def save_research_report(self, report: ResearchReport) -> None:
        d = {
            "report_id": report.report_id,
            "topic": report.topic,
            "executive_summary": report.executive_summary,
            "sections": report.sections,
            "sources": [asdict(s) for s in report.sources],
            "claims": [asdict(c) for c in report.claims],
            "identified_uncertainties": report.identified_uncertainties,
            "created_at": report.created_at,
        }
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO research_reports (
                    report_id, topic, executive_summary, data_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    report.report_id,
                    report.topic,
                    report.executive_summary,
                    json.dumps(redact_secrets(d), ensure_ascii=False),
                    report.created_at,
                ),
            )
            conn.commit()

    def get_research_report(self, report_id: str) -> Optional[ResearchReport]:
        with self._lock, self._get_connection() as conn:
            row = conn.execute(
                "SELECT data_json FROM research_reports WHERE report_id = ?", (report_id,)
            ).fetchone()
            if not row:
                return None
            data = json.loads(row["data_json"])
            sources = [ResearchSource(**s) for s in data.get("sources", [])]
            claims = [ResearchClaim(**c) for c in data.get("claims", [])]
            return ResearchReport(
                report_id=data["report_id"],
                topic=data["topic"],
                executive_summary=data["executive_summary"],
                sections=data.get("sections", {}),
                sources=sources,
                claims=claims,
                identified_uncertainties=data.get("identified_uncertainties", []),
                created_at=data.get("created_at", time.time()),
            )

    # ── Audit Trail ───────────────────────────────────────────────────────────

    def log_audit(self, record: AuditRecord) -> None:
        details_clean = redact_secrets(record.details)
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO audit_logs (
                    event_id, timestamp, event_type, component, actor,
                    action, details_json, security_flag
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.event_id,
                    record.timestamp,
                    record.event_type,
                    record.component,
                    record.actor,
                    record.action,
                    json.dumps(details_clean, ensure_ascii=False),
                    1 if record.security_flag else 0,
                ),
            )
            conn.commit()

    def get_audit_trail(self, limit: int = 100, component: Optional[str] = None) -> List[AuditRecord]:
        with self._lock, self._get_connection() as conn:
            if component:
                rows = conn.execute(
                    "SELECT * FROM audit_logs WHERE component = ? ORDER BY timestamp DESC LIMIT ?",
                    (component, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?", (limit,)
                ).fetchall()
            records = []
            for r in rows:
                records.append(
                    AuditRecord(
                        event_id=r["event_id"],
                        timestamp=r["timestamp"],
                        event_type=r["event_type"],
                        component=r["component"],
                        actor=r["actor"],
                        action=r["action"],
                        details=json.loads(r["details_json"]),
                        security_flag=bool(r["security_flag"]),
                    )
                )
            return records


# Global Singleton accessor
_storage_instance: Optional[IntelligenceStorage] = None
_storage_lock = threading.Lock()


def get_intelligence_storage() -> IntelligenceStorage:
    global _storage_instance
    with _storage_lock:
        if _storage_instance is None:
            _storage_instance = IntelligenceStorage()
        return _storage_instance
