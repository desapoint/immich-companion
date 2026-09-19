"""Contracts that keep bounded evidence visible and routine freshness quiet."""

from __future__ import annotations

import logging

from companion.duplicate_schema import SimilarityIndexCoverage
from companion.evidence_logging import install_pending_evidence_logging_policy


def test_similarity_coverage_exposes_bounded_and_unavailable_counts() -> None:
    coverage = SimilarityIndexCoverage(
        eligible_count=10,
        current_count=7,
        bounded_count=2,
        unavailable_count=1,
        missing_count=1,
        stale_count=1,
        complete=False,
        model_version="appearance-v1",
        feature_version=3,
        config_fingerprint="f" * 64,
    )

    payload = coverage.model_dump()
    assert payload["bounded_count"] == 2
    assert payload["unavailable_count"] == 1


def test_pending_evidence_freshness_is_not_a_warning() -> None:
    install_pending_evidence_logging_policy()
    logger = logging.getLogger("uvicorn.error")
    record = logger.makeRecord(
        logger.name,
        logging.WARNING,
        __file__,
        1,
        "Integrity evidence pending: asset_id=%s reason=%s",
        ("asset", "missing_report"),
        None,
    )

    for log_filter in logger.filters:
        log_filter.filter(record)

    assert record.levelno == logging.DEBUG
    assert record.levelname == "DEBUG"


def test_attempted_analysis_warning_remains_warning() -> None:
    install_pending_evidence_logging_policy()
    logger = logging.getLogger("uvicorn.error")
    record = logger.makeRecord(
        logger.name,
        logging.WARNING,
        __file__,
        1,
        "Candidate bounded detail unavailable: asset_id=%s reason=%s",
        ("asset", "decode_failed"),
        None,
    )

    for log_filter in logger.filters:
        log_filter.filter(record)

    assert record.levelno == logging.WARNING
