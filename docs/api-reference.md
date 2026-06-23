# Atticus API Reference

Base URL: `http://localhost:8000`  ·  Prefix: `/api/v1`  ·  Interactive docs: `/docs`

All responses include an `X-Request-ID` header for tracing against logs and the audit trail.

---

## GET `/api/v1/health`

Liveness + configuration check.

**Response**

```json
{
  "status": "ok",
  "version": "0.1.0",
  "anthropic_configured": true,
  "uspto_configured": true,
  "generation_model": "claude-sonnet-4-6",
  "verification_model": "claude-haiku-4-5"
}
```

---

## POST `/api/v1/analyze`

Analyze an office action into a structured `OfficeActionAnalysis` plus a `VerificationReport`.
Provide **either** `application_number` (fetched from USPTO) **or** `office_action_text`.

**Request**

```json
{ "office_action_text": "Application No.: 16/123,456 ..." }
```

**Response**

```json
{
  "analysis_id": "ab12...",
  "analysis": { "application_number": "16/123,456", "rejection_type": "non-final", "rejections": [ ... ] },
  "verification": { "overall_confidence": 0.82, "needs_human_review": false, "claims": [ ... ] }
}
```

`422` if neither input is supplied; `404` if no office action is found for the application;
`502` on USPTO fetch failure.

---

## POST `/api/v1/draft-response`

Draft a response from a previously stored analysis.

**Request**

```json
{ "analysis_id": "ab12...", "strategy": "argue" }   // strategy: "argue" | "amend" | "both"
```

**Response** — a `ResponseDraft` with per-argument `supporting_sources` and `confidence`.

---

## POST `/api/v1/search-prior-art`

Vector search over indexed patents.

**Request**

```json
{
  "query": "processor handling interrupt requests via a priority queue",
  "top_k": 8,
  "is_claim_limitation": true,
  "filters": { "tech_center": "2100", "classification": "G06F" }
}
```

**Response** — `{ "results": [ { "patent_number", "relevance_score", "matched_chunk", ... } ] }`.

---

## POST `/api/v1/verify-claim`

Verify a single claim or citation. If `cited_source` text is supplied and the citation exists, an
entailment check confirms the source actually supports the characterization.

**Request**

```json
{ "claim_text": "Anderson discloses a priority queue (col. 4).", "cited_source": "..." }
```

**Response** — a single `VerifiedClaim` with `status`, `confidence`, and `explanation`.

---

## GET `/api/v1/audit-trail/{analysis_id}`

Full audit trail: what was retrieved, generated, verified, and flagged.

```json
{ "analysis_id": "ab12...", "events": [ { "step": "generated" }, { "step": "verified", "payload": { "confidence": 0.82 } } ] }
```
