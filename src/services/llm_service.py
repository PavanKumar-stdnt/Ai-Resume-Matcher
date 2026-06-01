"""
services/llm_service.py — True RAG Gemini wrapper.

v2 changes:
  • evaluate_with_retrieved_chunks() — the primary RAG method. Receives only
    the top-K retrieved chunks (not the full document) and instructs Gemini to
    ground its evaluation STRICTLY in that retrieved context.
  • The old evaluate_match() is kept as a fallback for single-file ad-hoc use.
"""

from __future__ import annotations

import logging
from typing import Any

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class LLMService:
    """Thin, stateless facade over the Google GenAI client."""

    def __init__(self, api_key: str, model: str) -> None:
        self._model = model
        self._client = genai.Client(api_key=api_key)
        logger.info("LLMService initialised — model='%s'.", model)

    # ─────────────────────────────────────────────────────────────────────────
    # Primary RAG method  ← TRUE RAG: LLM grounded in retrieved chunks only
    # ─────────────────────────────────────────────────────────────────────────

    def evaluate_with_retrieved_chunks(
        self,
        retrieved_chunks: list[dict[str, Any]],
        job_description: str,
        resume_filename: str,
    ) -> str:
        """Evaluate match using ONLY the top-K retrieved resume chunks.

        This is the true RAG generation step:
          • The context injected into the prompt is strictly the retrieved
            chunks — not the full resume — so the LLM is grounded in the
            most semantically relevant sections.
          • Each chunk is numbered and labelled with its relevance score so
            Gemini can weight its importance.
          • The prompt explicitly forbids the model from inferring anything
            outside the provided context.

        Parameters
        ----------
        retrieved_chunks : list[dict]
            Top-K chunks from VectorService.retrieve_top_k(). Each has keys:
            ``text``, ``score``, ``chunk_index``, ``word_count``.
        job_description : str
            Full job description text.
        resume_filename : str
            Used in the prompt for traceability.

        Returns
        -------
        str
            Raw Gemini response with SCORE:/ANALYSIS: tokens.

        Raises
        ------
        RuntimeError
            If the API call fails or returns an empty response.
        """
        if not retrieved_chunks:
            raise RuntimeError(
                "No retrieved chunks provided to evaluate_with_retrieved_chunks()."
            )

        prompt = self._build_rag_prompt(
            retrieved_chunks, job_description, resume_filename
        )

        logger.debug(
            "Sending RAG prompt to Gemini — %d chunks, model='%s'.",
            len(retrieved_chunks),
            self._model,
        )

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=2048,
                    candidate_count=1,
                ),
            )
        except Exception as exc:
            raise RuntimeError(f"Gemini API call failed: {exc}") from exc

        raw_text: str = ""
        if response and response.text:
            raw_text = response.text.strip()

        if not raw_text:
            raise RuntimeError(
                "Gemini returned an empty response. "
                "Check your API key, quota, and model availability."
            )

        logger.debug("Gemini responded with %d chars.", len(raw_text))
        return raw_text

    # ─────────────────────────────────────────────────────────────────────────
    # Fallback method (kept for backward compatibility / ad-hoc use)
    # ─────────────────────────────────────────────────────────────────────────

    def evaluate_match(self, resume_text: str, job_description: str) -> str:
        """Fallback: evaluate using the full resume text (non-RAG path)."""
        prompt = self._build_full_doc_prompt(resume_text, job_description)
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=2048,
                    candidate_count=1,
                ),
            )
        except Exception as exc:
            raise RuntimeError(f"Gemini API call failed: {exc}") from exc

        raw_text = response.text.strip() if response and response.text else ""
        if not raw_text:
            raise RuntimeError("Gemini returned an empty response.")
        return raw_text

    # ─────────────────────────────────────────────────────────────────────────
    # Prompt builders
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_rag_prompt(
        retrieved_chunks: list[dict[str, Any]],
        job_description: str,
        resume_filename: str,
    ) -> str:
        """Build the RAG evaluation prompt from retrieved chunks.

        Each chunk is presented as a numbered, scored excerpt so Gemini
        knows which sections were most semantically similar to the JD.
        """
        # Build the retrieved context block
        context_lines: list[str] = []
        for i, chunk in enumerate(retrieved_chunks, start=1):
            context_lines.append(
                f"[EXCERPT {i} | Chunk #{chunk['chunk_index']} "
                f"| Relevance: {chunk['score']:.1f}/100 "
                f"| Words: {chunk['word_count']}]\n"
                f"{chunk['text']}"
            )
        context_block = "\n\n────────────────────────\n\n".join(context_lines)

        jd_excerpt = job_description[:3000]

        return f"""You are an elite technical recruiter with 15 years of experience \
evaluating candidates for software engineering and AI/ML roles.

IMPORTANT: You are operating in RAG (Retrieval-Augmented Generation) mode. \
You have been given ONLY the most relevant excerpts from the candidate's resume \
(retrieved via semantic similarity search). You must base your evaluation \
STRICTLY on the provided excerpts. Do NOT infer or assume skills not present \
in the retrieved context.

════════════════════════════════════════════════════════════
CANDIDATE FILE: {resume_filename}
RETRIEVED RESUME EXCERPTS ({len(retrieved_chunks)} most relevant sections):
════════════════════════════════════════════════════════════

{context_block}

════════════════════════════════════════════════════════════
JOB DESCRIPTION:
════════════════════════════════════════════════════════════

{jd_excerpt}

════════════════════════════════════════════════════════════
EVALUATION INSTRUCTIONS (RAG MODE):
════════════════════════════════════════════════════════════

Analyse the candidate's fit based ONLY on the retrieved excerpts above.
Evaluate across these dimensions:
1. Technical skills overlap — what tools, languages, frameworks are explicitly mentioned
2. Domain expertise alignment — industry and problem domain match
3. Seniority and experience level fit — years, roles, responsibilities
4. Education and certifications — degree, certifications explicitly stated
5. Project and achievement relevance — specific projects that align with the JD
6. Gaps — skills required by JD that are NOT mentioned in the retrieved excerpts

CRITICAL FORMAT REQUIREMENT:
Your response MUST begin with exactly these two lines, no preamble:
SCORE: [integer between 0 and 100]
ANALYSIS: [Your detailed multi-paragraph breakdown. Reference specific excerpts \
by number when making claims. Flag any inferences as uncertain since only partial \
resume context was retrieved.]

SCORE must be a plain integer. No units, no percentage signs, no decimals.
"""

    @staticmethod
    def _build_full_doc_prompt(resume_text: str, job_description: str) -> str:
        """Fallback prompt using full resume text (non-RAG path)."""
        return f"""You are an elite technical recruiter with 15 years of experience.

════════════════════════════════════════
RESUME CONTENT:
════════════════════════════════════════
{resume_text[:6000]}

════════════════════════════════════════
JOB DESCRIPTION:
════════════════════════════════════════
{job_description[:3000]}

════════════════════════════════════════
EVALUATION INSTRUCTIONS:
════════════════════════════════════════
Analyse the match across: technical skills, domain expertise, seniority fit,
education relevance, project alignment, and recruiter-flagged gaps.

CRITICAL FORMAT:
SCORE: [integer 0-100]
ANALYSIS: [Detailed multi-paragraph breakdown]

SCORE must be a plain integer only.
"""
