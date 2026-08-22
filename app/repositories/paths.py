"""Default filesystem locations for the JSON repository backend (V2 Phase
2B.1). Mirrors app/main.py's BASE_DIR/DATA_DIR/SCHEMAS_DIR constants
exactly, computed independently rather than imported from app.main so this
package stays import-independent of the application module (Part 8 -- no
route migration; this layer must be provably not wired into runtime yet).

Every concrete repository's constructor accepts its data directory as a
parameter defaulting to these constants, so tests can point a repository
at a temporary directory without touching live data
(docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md Part 6/7 -- contract tests and
Source-repository tests must use temporary data, never the live 1,882-record
dataset or the live 120-source registry)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = ROOT / "data"
SCHEMAS_DIR = ROOT / "schemas"
