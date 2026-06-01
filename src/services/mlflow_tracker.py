"""
services/mlflow_tracker.py — MLflow experiment tracking for every match run.

Tracks per-run metrics, parameters, and artifacts so you can:
  • Compare scoring results across model versions.
  • Monitor vector_score vs llm_score distributions over time.
  • Log the retrieved chunks as artifacts for auditability.
  • Tag runs by environment, model version, and resume filename.

Usage (called automatically by the orchestrator):
    tracker = MLflowTracker(settings)
    with tracker.start_run(resume_filename="john_doe.pdf") as run_id:
        tracker.log_params({...})
        tracker.log_metrics({...})
        tracker.log_chunks(retrieved_chunks)
"""

from __future__ import annotations

import json
import logging
import tempfile
from contextlib import contextmanager
from typing import Any, Generator

logger = logging.getLogger(__name__)

try:
    import mlflow
    MLFLOW_AVAILABLE = True
except ImportError:
    mlflow = None
    MLFLOW_AVAILABLE = False

class MLflowTracker:
    """Thin wrapper around MLflow for resume matching experiment tracking."""

    def __init__(self, tracking_uri: str, experiment_name: str, enabled: bool = True) -> None:
        self._enabled = enabled and MLFLOW_AVAILABLE
        self._experiment_name = experiment_name

        if self._enabled:
            mlflow.set_tracking_uri(tracking_uri)
            mlflow.set_experiment(experiment_name)
            logger.info(
                "MLflow tracking enabled — uri='%s', experiment='%s'",
                tracking_uri, experiment_name,
            )
        else:
            logger.info("MLflow tracking disabled.")

    @contextmanager
    def start_run(self, resume_filename: str, tags: dict[str, str] | None = None) -> Generator[str | None, None, None]:
        """Context manager that wraps one pipeline run as an MLflow run.

        Yields the run_id string (or None if disabled).

        Usage
        -----
        with tracker.start_run("resume.pdf") as run_id:
            tracker.log_params(...)
            tracker.log_metrics(...)
        """
        if not self._enabled:
            yield None
            return

        run_tags = {
            "resume_filename": resume_filename,
            "project": "ai-resume-matcher",
            **(tags or {}),
        }

        with mlflow.start_run(tags=run_tags) as run:
            logger.debug("MLflow run started: %s", run.info.run_id)
            try:
                yield run.info.run_id
            except Exception as exc:
                mlflow.set_tag("run_status", "failed")
                mlflow.set_tag("error", str(exc)[:500])
                raise
            else:
                mlflow.set_tag("run_status", "success")

    def log_params(self, params: dict[str, Any]) -> None:
        """Log pipeline configuration parameters."""
        if not self._enabled:
            return
        safe_params = {k: str(v)[:250] for k, v in params.items()}
        try:
            mlflow.log_params(safe_params)
        except Exception as exc:
            logger.warning("MLflow log_params failed: %s", exc)

    def log_metrics(self, metrics: dict[str, float]) -> None:
        """Log numeric scores and timing metrics."""
        if not self._enabled:
            return
        try:
            mlflow.log_metrics(metrics)
        except Exception as exc:
            logger.warning("MLflow log_metrics failed: %s", exc)

    def log_chunks(self, retrieved_chunks: list[dict[str, Any]]) -> None:
        """Log retrieved chunks as a JSON artifact for auditability."""
        if not self._enabled or not retrieved_chunks:
            return
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, encoding="utf-8"
            ) as f:
                json.dump(retrieved_chunks, f, indent=2, ensure_ascii=False)
                tmp_path = f.name
            mlflow.log_artifact(tmp_path, artifact_path="retrieved_chunks")
        except Exception as exc:
            logger.warning("MLflow log_chunks failed: %s", exc)

    def log_analysis(self, analysis_text: str) -> None:
        """Log the full LLM analysis text as a plain-text artifact."""
        if not self._enabled or not analysis_text:
            return
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, encoding="utf-8"
            ) as f:
                f.write(analysis_text)
                tmp_path = f.name
            mlflow.log_artifact(tmp_path, artifact_path="llm_analysis")
        except Exception as exc:
            logger.warning("MLflow log_analysis failed: %s", exc)

    def set_tag(self, key: str, value: str) -> None:
        if not self._enabled:
            return
        try:
            mlflow.set_tag(key, value[:250])
        except Exception as exc:
            logger.warning("MLflow set_tag failed: %s", exc)
