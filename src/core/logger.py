"""
core/logger.py — Thread-safe append-only CSV history logger.

Every successful match run appends one row to a local CSV file that acts as a
lightweight tabular datastore.  The header row is written automatically on the
very first write.  All file I/O is protected by a module-level threading.Lock
so concurrent FastAPI worker threads never produce interleaved writes.
"""

from __future__ import annotations

import csv
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Module-level lock — shared across all calls in the same process.
# ─────────────────────────────────────────────────────────────────────────────
_write_lock = threading.Lock()

# Ordered column definitions for the CSV file.
_CSV_COLUMNS: tuple[str, ...] = (
    "timestamp_utc",
    "resume_filename",
    "job_description_snippet",
    "vector_similarity_score",
    "llm_analysis_score",
    "final_score",
    "collection_name",
    "embedding_model",
)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def append_match_record(
    *,
    csv_path: str,
    resume_filename: str,
    job_description_snippet: str,
    vector_similarity_score: float,
    llm_analysis_score: float,
    final_score: float,
    collection_name: str,
    embedding_model: str,
) -> None:
    """Append one matching-run record to the CSV history file.

    Parameters
    ----------
    csv_path:
        Absolute or relative path to the CSV datastore file.
    resume_filename:
        Name of the uploaded resume document.
    job_description_snippet:
        First 120 characters of the job description (stored for quick preview).
    vector_similarity_score:
        Cosine similarity score scaled to 0-100.
    llm_analysis_score:
        Score extracted from the Gemini LLM analysis (0-100).
    final_score:
        Weighted composite of vector + LLM scores (0-100).
    collection_name:
        Qdrant collection used for the query.
    embedding_model:
        FastEmbed model identifier used to embed the documents.

    Raises
    ------
    OSError
        If the file cannot be opened for writing (permissions, disk full, etc.).
    """
    record: dict[str, Any] = {
        "timestamp_utc": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
        "resume_filename": resume_filename,
        "job_description_snippet": job_description_snippet[:120].replace("\n", " "),
        "vector_similarity_score": round(vector_similarity_score, 4),
        "llm_analysis_score": round(llm_analysis_score, 4),
        "final_score": round(final_score, 4),
        "collection_name": collection_name,
        "embedding_model": embedding_model,
    }

    _write_csv_row(csv_path=csv_path, record=record)
    logger.info(
        "History record appended → file='%s' final_score=%.2f",
        resume_filename,
        final_score,
    )


def read_history(csv_path: str, limit: int = 100) -> list[dict[str, str]]:
    """Return up to *limit* rows from the CSV history file, newest-first.

    Parameters
    ----------
    csv_path:
        Path to the CSV history file.
    limit:
        Maximum number of rows to return.

    Returns
    -------
    list[dict[str, str]]
        List of row dictionaries with string values.  Empty list if the file
        does not yet exist.
    """
    path = Path(csv_path)
    if not path.exists():
        return []

    with _write_lock:
        try:
            with path.open(newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                rows = list(reader)
        except OSError as exc:
            logger.error("Could not read history CSV '%s': %s", csv_path, exc)
            return []

    # Reverse so newest rows appear first, then truncate.
    return rows[::-1][:limit]


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────


def _write_csv_row(csv_path: str, record: dict[str, Any]) -> None:
    """Write *record* to *csv_path*, creating the file + header if necessary."""
    path = Path(csv_path)

    with _write_lock:
        # Determine whether the file is brand-new (needs a header row).
        needs_header = not path.exists() or os.path.getsize(path) == 0

        # Ensure parent directories exist.
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with path.open("a", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(
                    fh,
                    fieldnames=_CSV_COLUMNS,
                    extrasaction="ignore",
                    lineterminator="\n",
                )
                if needs_header:
                    writer.writeheader()
                    logger.debug("CSV header written to '%s'.", csv_path)
                writer.writerow(record)
        except OSError as exc:
            logger.error("Failed to append to history CSV '%s': %s", csv_path, exc)
            raise
