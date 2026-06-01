"""
api/endpoints.py — Production endpoints with Qdrant Cloud + MLflow aware singletons.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from src.api.dependencies import verify_api_key
from src.config import Settings, get_settings
from src.core.logger import read_history
from src.core.utils import extract_text_from_bytes
from src.services.llm_service import LLMService
from src.services.mlflow_tracker import MLflowTracker
from src.services.orchestrator import MatchOrchestrator
from src.services.vector_service import VectorService

logger = logging.getLogger(__name__)
router = APIRouter()

_vector_service: Optional[VectorService] = None
_llm_service: Optional[LLMService] = None
_mlflow_tracker: Optional[MLflowTracker] = None
_orchestrator: Optional[MatchOrchestrator] = None


def _get_orchestrator(settings: Settings = Depends(get_settings)) -> MatchOrchestrator:
    global _vector_service, _llm_service, _mlflow_tracker, _orchestrator

    if _orchestrator is None:
        logger.info("Bootstrapping production service singletons …")

        _vector_service = VectorService(
            collection_name=settings.qdrant_collection_name,
            embedding_model=settings.embedding_model,
           # embedding_dimension=settings.embedding_dimension,
            qdrant_url=settings.qdrant_url,
            qdrant_api_key=settings.qdrant_api_key,
            storage_path=settings.qdrant_storage_path,
        )

        _llm_service = LLMService(api_key=settings.google_api_key, model=settings.gemini_model)

        _mlflow_tracker = MLflowTracker(
            tracking_uri=settings.mlflow_tracking_uri,
            experiment_name=settings.mlflow_experiment_name,
            enabled=settings.mlflow_enabled,
        )

        _orchestrator = MatchOrchestrator(
            vector_service=_vector_service,
            llm_service=_llm_service,
            history_csv_path=settings.history_csv_path,
            mlflow_tracker=_mlflow_tracker,
        )
        logger.info("All production singletons ready.")

    return _orchestrator


async def _resolve_job_text(
    job_description_text: Optional[str],
    job_description_file: Optional[UploadFile],
) -> str:
    if job_description_text and job_description_text.strip():
        return job_description_text.strip()
    if job_description_file and job_description_file.filename:
        try:
            return extract_text_from_bytes(await job_description_file.read(), job_description_file.filename)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Could not parse JD file: {exc}") from exc
    raise HTTPException(status_code=422, detail="Job description required via text or file.")


@router.get("/health", summary="Liveness check")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "AI Resume Matcher v2 — Production"}


@router.post("/match", summary="Single resume RAG match", dependencies=[Depends(verify_api_key)])
async def match_resume(
    resume_file: Annotated[UploadFile, File()],
    job_description_text: Annotated[Optional[str], Form()] = None,
    job_description_file: Annotated[Optional[UploadFile], File()] = None,
    orchestrator: MatchOrchestrator = Depends(_get_orchestrator),
) -> JSONResponse:
    if not resume_file.filename:
        raise HTTPException(status_code=422, detail="Resume file must have a filename.")

    resume_bytes = await resume_file.read()
    if not resume_bytes:
        raise HTTPException(status_code=400, detail="Resume file is empty.")

    job_text = await _resolve_job_text(job_description_text, job_description_file)
    if len(job_text) < 20:
        raise HTTPException(status_code=422, detail="Job description too short (min 20 chars).")

    try:
        result: dict[str, Any] = orchestrator.run(
            resume_bytes=resume_bytes, resume_filename=resume_file.filename, job_text=job_text
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Pipeline error for '%s'.", resume_file.filename)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return JSONResponse(content=result)


@router.post("/match/batch", summary="Batch RAG match", dependencies=[Depends(verify_api_key)])
async def match_resumes_batch(
    resume_files: Annotated[List[UploadFile], File()],
    job_description_text: Annotated[Optional[str], Form()] = None,
    job_description_file: Annotated[Optional[UploadFile], File()] = None,
    orchestrator: MatchOrchestrator = Depends(_get_orchestrator),
) -> JSONResponse:
    if not resume_files:
        raise HTTPException(status_code=422, detail="At least one resume required.")
    if len(resume_files) > 20:
        raise HTTPException(status_code=422, detail="Maximum 20 resumes per batch.")

    job_text = await _resolve_job_text(job_description_text, job_description_file)
    if len(job_text) < 20:
        raise HTTPException(status_code=422, detail="Job description too short.")

    resumes: list[dict[str, Any]] = []
    for upload in resume_files:
        if not upload.filename:
            continue
        try:
            raw = await upload.read()
        except Exception:
            raw = b""
        resumes.append({"filename": upload.filename, "bytes": raw})

    if not resumes:
        raise HTTPException(status_code=400, detail="No readable resume files found.")

    try:
        results = orchestrator.run_batch(resumes=resumes, job_text=job_text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Batch pipeline error.")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    successful = [r for r in results if r.get("rank") is not None]
    failed = [r for r in results if r.get("rank") is None]

    return JSONResponse(content={
        "total": len(results), "successful": len(successful), "failed": len(failed),
        "job_description_snippet": job_text[:200], "results": results,
    })


@router.get("/history", summary="Match history", dependencies=[Depends(verify_api_key)])
async def get_history(limit: int = 50, settings: Settings = Depends(get_settings)) -> JSONResponse:
    if not (1 <= limit <= 500):
        raise HTTPException(status_code=422, detail="limit must be 1–500.")
    rows = read_history(csv_path=settings.history_csv_path, limit=limit)
    return JSONResponse(content={"count": len(rows), "records": rows})



@router.delete(
    "/history",
    summary="Clear match history",
    dependencies=[Depends(verify_api_key)]
)
async def clear_history(
    settings: Settings = Depends(get_settings)
) -> JSONResponse:

    try:

        import os

        if os.path.exists(settings.history_csv_path):
            os.remove(settings.history_csv_path)

        return JSONResponse(
            content={
                "message": "History cleared successfully."
            }
        )

    except Exception as exc:

        logger.exception("Failed to clear history.")

        raise HTTPException(
            status_code=500,
            detail="Could not clear history."
        ) from exc
