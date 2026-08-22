"""Independent in-memory repository backend used to prove the Phase 2 seam."""

from .repositories import MemoryRecordRepository, get_memory_repositories

__all__ = ["MemoryRecordRepository", "get_memory_repositories"]
