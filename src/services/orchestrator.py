"""
services/orchestrator.py — Production orchestrator with MLflow tracking.

Changes vs v2:
  • MLflowTracker injected — every run logged as an MLflow experiment run.
  • Tracks: params (model names, chunk config), metrics (all 3 scores, timing),
    artifacts (retrieved chunks JSON, LLM analysis text).
  • VectorService initialised with cloud-aware constructor.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any
from contextlib import contextmanager

from src.core.logger import append_match_record
from src.core.utils import CHUNK_OVERLAP, CHUNK_SIZE, extract_text_from_bytes
from src.services.llm_service import LLMService
from src.services.mlflow_tracker import MLflowTracker
from src.services.vector_service import VectorService

logger = logging.getLogger(__name__)

_SCORE_PATTERN: re.Pattern[str] = re.compile(
    r"SCORE\s*:\s*([0-9]{1,3}(?:\.[0-9]+)?)", re.IGNORECASE
)
_ANALYSIS_PATTERN: re.Pattern[str] = re.compile(
    r"ANALYSIS\s*:\s*(.+)", re.IGNORECASE | re.DOTALL
)

_VECTOR_WEIGHT: float = 0.35
_LLM_WEIGHT: float = 0.65


@dataclass
class MatchState:
    resume_bytes: bytes
    resume_filename: str
    job_text: str
    resume_text: str = ""
    stage1_complete: bool = False
    resume_id: str = ""
    chunks_indexed: int = 0
    stage2a_complete: bool = False
    retrieved_chunks: list[dict[str, Any]] = field(default_factory=list)
    vector_score: float = 0.0
    stage2b_complete: bool = False
    llm_raw_response: str = ""
    llm_score: float = 0.0
    llm_analysis: str = ""
    stage3_complete: bool = False
    final_score: float = 0.0
    elapsed_seconds: float = 0.0
    warnings: list[str] = field(default_factory=list)


class MatchOrchestrator:
    def __init__(
        self,
        vector_service: VectorService,
        llm_service: LLMService,
        history_csv_path: str,
        mlflow_tracker: MLflowTracker | None = None,
    ) -> None:
        self._vector = vector_service
        self._llm = llm_service
        self._csv_path = history_csv_path
        self._mlflow = mlflow_tracker

    # ── Single run ────────────────────────────────────────────────────────────

    def run(
        self, resume_bytes: bytes, resume_filename: str, job_text: str
    ) -> dict[str, Any]:
        state = MatchState(
            resume_bytes=resume_bytes,
            resume_filename=resume_filename,
            job_text=job_text.strip(),
            resume_id=str(uuid.uuid4()),
        )

        tracker = self._mlflow
        context = tracker.start_run(resume_filename) if tracker else _noop_context()

        with context as run_id:
            t0 = time.time()

            # Log params before pipeline starts
            if tracker and run_id:
                tracker.log_params(
                    {
                        "embedding_model": self._vector.embedding_model,
                        "collection_name": self._vector.collection_name,
                        "chunk_size": CHUNK_SIZE,
                        "chunk_overlap": CHUNK_OVERLAP,
                        "vector_weight": _VECTOR_WEIGHT,
                        "llm_weight": _LLM_WEIGHT,
                        "resume_filename": resume_filename,
                        "job_description_snippet": job_text[:200],
                    }
                )

            try:
                self._stage1_parse(state)
                self._stage2a_index(state)
                self._stage2b_retrieve(state)
                self._stage3_llm(state)
                self._compute_final_score(state)
                self._log_history(state)
            finally:
                if state.resume_id and state.chunks_indexed > 0:
                    self._vector.delete_resume(state.resume_id)

            state.elapsed_seconds = round(time.time() - t0, 2)

            # Log metrics + artifacts to MLflow
            if tracker and run_id:
                tracker.log_metrics(
                    {
                        "vector_score": state.vector_score,
                        "llm_score": state.llm_score,
                        "final_score": state.final_score,
                        "chunks_indexed": float(state.chunks_indexed),
                        "chunks_retrieved": float(len(state.retrieved_chunks)),
                        "elapsed_seconds": state.elapsed_seconds,
                    }
                )
                tracker.log_chunks(state.retrieved_chunks)
                tracker.log_analysis(state.llm_analysis)
                tracker.set_tag("run_id_internal", state.resume_id)

        logger.info(
            "Pipeline END — final_score=%.2f, elapsed=%.2fs",
            state.final_score,
            state.elapsed_seconds,
        )
        return self._build_result(state)

    # ── Batch run ─────────────────────────────────────────────────────────────

    def run_batch(
        self, resumes: list[dict[str, Any]], job_text: str
    ) -> list[dict[str, Any]]:
        if not resumes:
            raise ValueError("run_batch() received an empty resume list.")
        cleaned_jd = job_text.strip()
        if len(cleaned_jd) < 20:
            raise ValueError("Job description too short (minimum 20 characters).")

        results: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for idx, resume in enumerate(resumes, start=1):
            filename = resume.get("filename", f"resume_{idx}")
            raw_bytes = resume.get("bytes", b"")
            if not raw_bytes:
                errors.append(
                    {
                        "resume_filename": filename,
                        "error": "Empty file.",
                        "final_score": 0.0,
                    }
                )
                continue
            logger.info("[Batch %d/%d] Processing '%s' …", idx, len(resumes), filename)
            try:
                results.append(
                    self.run(
                        resume_bytes=raw_bytes,
                        resume_filename=filename,
                        job_text=cleaned_jd,
                    )
                )
            except Exception as exc:
                logger.error("[Batch] Failed for '%s': %s", filename, exc)
                errors.append(
                    {
                        "resume_filename": filename,
                        "error": str(exc),
                        "final_score": 0.0,
                        "vector_score": 0.0,
                        "llm_score": 0.0,
                        "analysis": "",
                        "warnings": [str(exc)],
                    }
                )

        results.sort(key=lambda r: r.get("final_score", 0.0), reverse=True)
        for rank, r in enumerate(results, start=1):
            r["rank"] = rank
        for e in errors:
            e["rank"] = None

        return results + errors

    # ── Stages ────────────────────────────────────────────────────────────────

    def _stage1_parse(self, state: MatchState) -> None:
        state.resume_text = extract_text_from_bytes(
            state.resume_bytes, state.resume_filename
        )
        state.stage1_complete = True

    def _stage2a_index(self, state: MatchState) -> None:
        point_ids = self._vector.index_resume(
            state.resume_text, state.resume_filename, state.resume_id
        )
        state.chunks_indexed = len(point_ids)
        state.stage2a_complete = True

    def _stage2b_retrieve(self, state: MatchState) -> None:
        try:
            state.retrieved_chunks = self._vector.retrieve_top_k(
                state.job_text, state.resume_id
            )
            state.vector_score = self._vector.compute_vector_score(
                state.job_text, state.resume_id
            )
            state.stage2b_complete = True
        except Exception as exc:
            state.warnings.append(f"Retrieval failed: {exc}")
            state.vector_score = 0.0
            state.stage2b_complete = True

    def _stage3_llm(self, state: MatchState) -> None:
        if state.retrieved_chunks:
            raw = self._llm.evaluate_with_retrieved_chunks(
                state.retrieved_chunks, state.job_text, state.resume_filename
            )
        else:
            state.warnings.append("No chunks retrieved; using full-text fallback.")
            raw = self._llm.evaluate_match(state.resume_text, state.job_text)
        state.llm_raw_response = raw
        state.llm_score, state.llm_analysis = self._parse_llm_response(raw)
        state.stage3_complete = True

    @staticmethod
    def _parse_llm_response(raw: str) -> tuple[float, str]:
        score = 50.0
        analysis = raw
        m = _SCORE_PATTERN.search(raw)
        if m:
            try:
                score = max(0.0, min(100.0, float(m.group(1))))
            except ValueError:
                pass
        a = _ANALYSIS_PATTERN.search(raw)
        if a:
            analysis = a.group(1).strip()
        return score, analysis

    @staticmethod
    def _compute_final_score(state: MatchState) -> None:
        state.final_score = round(
            state.vector_score * _VECTOR_WEIGHT + state.llm_score * _LLM_WEIGHT, 2
        )

    def _log_history(self, state: MatchState) -> None:
        try:
            append_match_record(
                csv_path=self._csv_path,
                resume_filename=state.resume_filename,
                job_description_snippet=state.job_text[:120],
                vector_similarity_score=state.vector_score,
                llm_analysis_score=state.llm_score,
                final_score=state.final_score,
                collection_name=self._vector.collection_name,
                embedding_model=self._vector.embedding_model,
            )
        except OSError as exc:
            state.warnings.append(f"History logging failed: {exc}")

    @staticmethod
    def _build_result(state: MatchState) -> dict[str, Any]:
        return {
            "resume_filename": state.resume_filename,
            "vector_score": state.vector_score,
            "llm_score": state.llm_score,
            "final_score": state.final_score,
            "analysis": state.llm_analysis,
            "chunks_indexed": state.chunks_indexed,
            "chunks_retrieved": len(state.retrieved_chunks),
            "retrieved_chunk_scores": [
                {"chunk_index": c["chunk_index"], "score": c["score"]}
                for c in state.retrieved_chunks
            ],
            "elapsed_seconds": state.elapsed_seconds,
            "warnings": state.warnings,
            "stages": {
                "parsing": state.stage1_complete,
                "rag_indexing": state.stage2a_complete,
                "rag_retrieval": state.stage2b_complete,
                "llm_evaluation": state.stage3_complete,
            },
        }


# ── No-op context manager for when MLflow is disabled ────────────────────────
# from contextlib import contextmanager


@contextmanager
def _noop_context():
    yield None
