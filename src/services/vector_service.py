"""
services/vector_service.py — Qdrant Cloud + local disk dual-mode vector service.

Production change: connects to Qdrant Cloud when QDRANT_URL + QDRANT_API_KEY
are set; falls back to local disk otherwise (for development).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from qdrant_client import QdrantClient, models

# from qdrant_client.models import Distance, VectorParams

from src.core.utils import TextChunk, chunk_document

logger = logging.getLogger(__name__)

DEFAULT_TOP_K: int = 5


class VectorService:

    def __init__(
        self,
        collection_name: str,
        embedding_model: str,
        # Cloud mode
        qdrant_url: Optional[str] = None,
        qdrant_api_key: Optional[str] = None,
        # Local mode fallback
        storage_path: str = "./local_qdrant_storage",
    ) -> None:

        self._collection_name = collection_name
        self._embedding_model = embedding_model

        if qdrant_url and qdrant_api_key:
            logger.info("Connecting to Qdrant Cloud at '%s' …", qdrant_url)

            self._client = QdrantClient(
                url=qdrant_url,
                api_key=qdrant_api_key,
            )

            logger.info("Qdrant Cloud connection established.")

        else:
            logger.info("Using local Qdrant at '%s' …", storage_path)

            self._client = QdrantClient(path=storage_path)

        self._client.set_model(embedding_model)

        try:
            self._client.create_payload_index(
                collection_name=self._collection_name,
                field_name="resume_id",
                field_schema="keyword",
            )
        except Exception:
            pass
        # TEMPORARY — run only once
        # self._client.delete_collection(self._collection_name)

        # self._ensure_collection()

        logger.info(
            "VectorService ready — collection='%s', model='%s'",
            collection_name,
            embedding_model,
        )

    def index_resume(
        self, resume_text: str, resume_filename: str, resume_id: str
    ) -> list[str]:
        chunks: list[TextChunk] = chunk_document(resume_text, resume_filename)
        if not chunks:
            raise ValueError(f"Chunking produced zero chunks for '{resume_filename}'.")

        documents, metadatas, ids = [], [], []
        for chunk in chunks:
            pid = str(uuid.uuid4())
            documents.append(chunk.text)
            metadatas.append(
                {
                    "resume_id": resume_id,
                    "chunk_index": chunk.chunk_index,
                    "word_count": chunk.word_count,
                    "source_filename": resume_filename,
                    "point_id": pid,
                }
            )
            ids.append(pid)

        self._client.add(
            collection_name=self._collection_name,
            documents=documents,
            metadata=metadatas,
            ids=ids,
        )
        logger.info("Indexed %d chunks for resume_id='%s'.", len(chunks), resume_id)
        return ids

    def retrieve_top_k(
        self, job_text: str, resume_id: str, k: int = DEFAULT_TOP_K
    ) -> list[dict[str, Any]]:
        results = self._client.query(
            collection_name=self._collection_name,
            query_text=job_text,
            limit=k,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="resume_id", match=models.MatchValue(value=resume_id)
                    )
                ]
            ),
        )
        return [
            {
                "text": r.document,
                "score": self._cosine_to_percentage(r.score),
                "chunk_index": r.metadata.get("chunk_index", -1),
                "word_count": r.metadata.get("word_count", 0),
            }
            for r in results
        ]

    def compute_vector_score(
        self, job_text: str, resume_id: str, k: int = DEFAULT_TOP_K
    ) -> float:
        chunks = self.retrieve_top_k(job_text, resume_id, k=k)
        if not chunks:
            return 0.0
        return round(sum(c["score"] for c in chunks) / len(chunks), 2)

    def delete_resume(self, resume_id: str) -> None:
        try:
            self._client.delete(
                collection_name=self._collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="resume_id",
                                match=models.MatchValue(value=resume_id),
                            )
                        ]
                    )
                ),
            )
        except Exception as exc:
            logger.warning(
                "Could not delete chunks for resume_id='%s': %s", resume_id, exc
            )

    @property
    def collection_name(self) -> str:
        return self._collection_name

    @property
    def embedding_model(self) -> str:
        return self._embedding_model

    # def _ensure_collection(self) -> None:

    #   if not self._client.collection_exists(
    #      self._collection_name
    # ):

    #    self._client.create_collection(
    #       collection_name=self._collection_name,
    #      vectors_config=VectorParams(
    #         size=self._embedding_dimension,
    #        distance=Distance.COSINE,
    #   ),
    # )

    @staticmethod
    def _cosine_to_percentage(score: float) -> float:
        return round((max(-1.0, min(1.0, score)) + 1.0) / 2.0 * 100.0, 2)
