"""Logging policy for expected evidence freshness gaps."""

from __future__ import annotations

import logging

_PENDING_PREFIXES = (
    "Integrity evidence pending:",
    "Similarity evidence pending:",
)


class _PendingEvidenceFilter(logging.Filter):
    """Keep expected missing/stale evidence diagnostic without warning noise."""

    marker = "immich-companion-pending-evidence-filter"

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno >= logging.WARNING and record.getMessage().startswith(_PENDING_PREFIXES):
            record.levelno = logging.DEBUG
            record.levelname = logging.getLevelName(logging.DEBUG)
        return True


def install_pending_evidence_logging_policy() -> None:
    """Downgrade freshness diagnostics; attempted-analysis failures remain warnings."""

    target = logging.getLogger("uvicorn.error")
    if any(getattr(item, "marker", None) == _PendingEvidenceFilter.marker for item in target.filters):
        return
    target.addFilter(_PendingEvidenceFilter())
