"""Plant-patent monitoring as untrusted Evidence drafts.

Patents are Evidence (`source_type=patent_record`), not a parallel Signal
store. Signal remains a multi-evidence pattern object. Human review is the
trust gate; ingestion never publishes.
"""

from app.services.patent_monitor.service import (  # noqa: F401
    PatentMonitorService,
    PatentMonitorError,
    run_patent_monitor,
)
