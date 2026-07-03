"""Draft an office-action response from a structured analysis.

For each rejected claim we retrieve the claim text, cited-reference passages, and MPEP guidance,
then ask the model to argue and/or amend — grounded strictly in that retrieved context. Output is
a ``ResponseDraft`` whose every argument carries its supporting sources, ready for verification.
"""

from __future__ import annotations

import logging

from src.generation.llm_client import LLMClient
from src.generation.prompt_templates import DRAFT_RESPONSE_ARGUMENT, SUGGEST_AMENDMENTS
from src.models.schemas import (
    ClaimRejection,
    OfficeActionAnalysis,
    ResponseArgument,
    ResponseDraft,
)

logger = logging.getLogger(__name__)


def _reference_blocks(rejection: ClaimRejection) -> str:
    # Fold in passages from both the cited references and the examiner's limitation mappings
    # (the LLM analysis extracts "col. 4, lines 23-45"-style passages into the mappings).
    passages_by_ref: dict[str, list[str]] = {}
    for ref in rejection.cited_references:
        passages_by_ref.setdefault(ref.patent_number, []).extend(ref.relevant_passages)
    for m in rejection.limitation_mappings:
        if m.mapped_to_reference and m.reference_passage:
            passages_by_ref.setdefault(m.mapped_to_reference, []).append(
                f"{m.reference_passage} — mapped to: {m.limitation_text}"
            )
    blocks = []
    for ref, passages in passages_by_ref.items():
        body = "\n".join(dict.fromkeys(passages)) or "(no passages provided)"
        blocks.append(f'<cited_reference ref="{ref}">\n{body}\n</cited_reference>')
    return "\n".join(blocks) or "<cited_reference>(none)</cited_reference>"


def _claim_context(rejection: ClaimRejection) -> str:
    """The claim limitations the examiner mapped (used when the full claim text isn't retrieved)."""
    lims = [m.limitation_text for m in rejection.limitation_mappings if m.limitation_text]
    if not lims:
        return "(claim text not retrieved)"
    return "Claim limitations at issue (as identified by the examiner):\n" + "\n".join(
        f"- {t}" for t in lims
    )


def draft_response(
    analysis: OfficeActionAnalysis,
    analysis_id: str,
    strategy: str = "argue",
    *,
    claim_texts: dict[int, str] | None = None,
    mpep_context: dict[int, str] | None = None,
    llm: LLMClient | None = None,
) -> ResponseDraft:
    """Produce a per-claim response draft.

    ``claim_texts`` and ``mpep_context`` supply the retrieved context per claim number; when
    omitted, placeholders are used (the model will report INSUFFICIENT_CONTEXT for missing parts).
    """
    claim_texts = claim_texts or {}
    mpep_context = mpep_context or {}
    llm = llm or LLMClient()

    arguments: list[ResponseArgument] = []
    for rejection in analysis.rejections:
        # Prefer explicitly retrieved claim text; otherwise fall back to the examiner's mapped
        # limitations from the (LLM-enriched) analysis so the model has grounded content.
        claim_text = claim_texts.get(rejection.claim_number) or _claim_context(rejection)
        refs = _reference_blocks(rejection)

        if strategy in ("argue", "both"):
            arguments.append(
                _argue(llm, rejection, claim_text, refs, mpep_context)
            )
        if strategy in ("amend", "both"):
            arguments.append(
                _amend(llm, rejection, claim_text, refs)
            )

    return ResponseDraft(
        analysis_id=analysis_id,
        application_number=analysis.application_number,
        strategy=strategy,
        arguments=arguments,
    )


def _argue(llm, rejection, claim_text, refs, mpep_context) -> ResponseArgument:
    prompt = DRAFT_RESPONSE_ARGUMENT
    mpep = mpep_context.get(rejection.claim_number, "")
    mpep_block = f"<mpep>\n{mpep}\n</mpep>" if mpep else "<mpep>(none retrieved)</mpep>"
    user = prompt.render(
        claim_number=rejection.claim_number,
        claim_text=claim_text,
        rejection_basis=rejection.rejection_basis.value,
        rejection_text=_rejection_summary(rejection),
        reference_blocks=refs,
        mpep_blocks=mpep_block,
    )
    data = llm.complete_json(prompt.system, user)
    return ResponseArgument(
        claim_number=rejection.claim_number,
        rejection_basis=rejection.rejection_basis,
        strategy="argue",
        argument_text=data.get("argument_text", ""),
        supporting_sources=data.get("supporting_sources", []),
        confidence=float(data.get("confidence", 0.0)),
    )


def _amend(llm, rejection, claim_text, refs) -> ResponseArgument:
    prompt = SUGGEST_AMENDMENTS
    user = prompt.render(
        claim_number=rejection.claim_number,
        claim_text=claim_text,
        specification_support="(specification not retrieved)",
        reference_blocks=refs,
    )
    data = llm.complete_json(prompt.system, user)
    return ResponseArgument(
        claim_number=rejection.claim_number,
        rejection_basis=rejection.rejection_basis,
        strategy="amend",
        argument_text=data.get("distinction", ""),
        supporting_sources=[data.get("source", "")] if data.get("source") else [],
        suggested_amendment=data.get("suggested_amendment"),
        confidence=float(data.get("confidence", 0.0)),
    )


def _rejection_summary(rejection: ClaimRejection) -> str:
    refs = ", ".join(r.patent_number for r in rejection.cited_references) or "(no references)"
    return (
        f"Claim {rejection.claim_number} rejected under §{rejection.rejection_basis.value} "
        f"over {refs}."
    )
