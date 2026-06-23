"""POST /search-prior-art — vector search over indexed patents/MPEP."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.models.schemas import PriorArtSearchResult
from src.retrieval.patent_retriever import PatentRetriever

router = APIRouter(tags=["search"])


class SearchFilters(BaseModel):
    tech_center: str | None = None
    classification: str | None = None
    date_range: str | None = None


class SearchRequest(BaseModel):
    query: str
    top_k: int = 8
    is_claim_limitation: bool = False
    filters: SearchFilters = Field(default_factory=SearchFilters)


class SearchResponse(BaseModel):
    results: list[PriorArtSearchResult]


@router.post("/search-prior-art", response_model=SearchResponse)
def search_prior_art(req: SearchRequest) -> SearchResponse:
    retriever = PatentRetriever()
    filters = {
        k: v
        for k, v in {
            "classification": req.filters.classification,
            "tech_center": req.filters.tech_center,
        }.items()
        if v
    }
    results = retriever.retrieve(
        req.query,
        top_k=req.top_k,
        is_claim_limitation=req.is_claim_limitation,
        filters=filters or None,
    )
    return SearchResponse(results=results)
