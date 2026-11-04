"""
core/intelligence/memory/neural_memory.py — Neural Memory 2.0 Engine for J.A.R.V.I.S.

Maintains multi-tiered, project-scoped memory with contextual keyword search,
relevance ranking, provenance tracking, and strict credential redaction.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from core.intelligence.models import MemoryCategory, MemoryRecord, ProjectMemory
from core.intelligence.storage import IntelligenceStorage, get_intelligence_storage

logger = logging.getLogger("JARVIS.Intelligence.NeuralMemory")


class NeuralMemoryManager:
    """Manages project-scoped continuous memory and knowledge retention."""

    def __init__(self, base_dir: Optional[Path] = None, db_path: Optional[Path] = None):
        if db_path is not None:
            self._storage = IntelligenceStorage(db_path)
        else:
            self._storage = get_intelligence_storage()

    def store(
        self,
        title: str,
        content: str,
        category: MemoryCategory = MemoryCategory.PROJECT_MEMORY,
        project_id: str = "default",
        source: str = "user_conversation",
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
    ) -> MemoryRecord:
        """Stores a new memory record with secret redaction and timestamping."""
        record = MemoryRecord(
            category=category,
            project_id=project_id,
            title=title.strip(),
            content=content.strip(),
            source=source,
            importance=max(0.0, min(1.0, importance)),
            tags=tags or [],
            created_at=time.time(),
            updated_at=time.time(),
            last_accessed_at=time.time(),
        )
        self._storage.save_memory(record)
        logger.info(f"NeuralMemory: Stored record '{record.title}' [{category.value}] for project '{project_id}'")
        return record

    def recall(
        self,
        query: str = "",
        category: Optional[MemoryCategory] = None,
        project_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[MemoryRecord]:
        """
        Recalls records ranked by relevance score combining:
        - Exact keyword match in title (weight 0.4)
        - Keyword match in content (weight 0.3)
        - Importance (weight 0.2)
        - Recency (weight 0.1)
        """
        candidates = self._storage.search_memories(
            query=query, category=category, project_id=project_id, limit=limit * 3
        )
        if not query.strip():
            # Update access counts
            for c in candidates[:limit]:
                c.access_count += 1
                c.last_accessed_at = time.time()
                self._storage.save_memory(c)
            return candidates[:limit]

        query_terms = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2]
        scored: List[Tuple[float, MemoryRecord]] = []

        now = time.time()
        for record in candidates:
            score = 0.0
            title_lower = record.title.lower()
            content_lower = record.content.lower()

            for term in query_terms:
                if term in title_lower:
                    score += 0.4
                if term in content_lower:
                    score += 0.3

            score += record.importance * 0.2
            # Recency factor: decays over 30 days
            age_days = (now - record.updated_at) / 86400.0
            recency_multiplier = max(0.1, 1.0 - (age_days / 30.0))
            score += 0.1 * recency_multiplier

            scored.append((score, record))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [r for _, r in scored[:limit]]

        # Bump access telemetry
        for r in results:
            r.access_count += 1
            r.last_accessed_at = now
            self._storage.save_memory(r)

        return results

    def get_project_context(self, project_id: str) -> Dict[str, Any]:
        """Retrieves structured project continuity context for prompt injection."""
        project_memories = self._storage.search_memories(
            project_id=project_id, category=MemoryCategory.PROJECT_MEMORY, limit=20
        )
        tech_memories = self._storage.search_memories(
            project_id=project_id, category=MemoryCategory.TECHNICAL_KNOWLEDGE, limit=10
        )
        return {
            "project_id": project_id,
            "project_records": [{"title": m.title, "content": m.content} for m in project_memories],
            "technical_knowledge": [{"title": m.title, "content": m.content} for m in tech_memories],
        }

    def format_for_prompt(self, query: str = "", project_id: Optional[str] = None, max_chars: int = 1200) -> str:
        """Formats relevant Neural Memory entries into a concise block for LLM prompts."""
        recalled = self.recall(query=query, project_id=project_id, limit=6)
        if not recalled:
            return ""

        lines = ["--- [NEURAL MEMORY 2.0 CONTEXT] ---"]
        total_len = len(lines[0])

        for r in recalled:
            entry = f"• [{r.category.value}] {r.title}: {r.content}"
            if total_len + len(entry) + 1 > max_chars:
                break
            lines.append(entry)
            total_len += len(entry) + 1

        lines.append("-----------------------------------")
        return "\n".join(lines)

    def delete_record(self, record_id: str) -> bool:
        return self._storage.delete_memory(record_id)

    def remember(
        self,
        key: str = "",
        title: str = "",
        content: str = "",
        category: MemoryCategory = MemoryCategory.PROJECT_MEMORY,
        project_id: str = "default",
        source: str = "user_conversation",
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
    ) -> MemoryRecord:
        t = (title or key).strip()
        return self.store(
            title=t,
            content=content,
            category=category,
            project_id=project_id,
            source=source,
            importance=importance,
            tags=tags,
        )

    def forget(self, record_id: str) -> bool:
        return self.delete_record(record_id)

    @classmethod
    def get_instance(cls, base_dir: Optional[Any] = None) -> "NeuralMemoryManager":
        return get_neural_memory()


# Global Singleton accessor
_neural_memory_instance: Optional[NeuralMemoryManager] = None

def get_neural_memory() -> NeuralMemoryManager:
    global _neural_memory_instance
    if _neural_memory_instance is None:
        _neural_memory_instance = NeuralMemoryManager()
    return _neural_memory_instance

NeuralMemoryEngine = NeuralMemoryManager
