# Evaluation Methodology

Atticus exists to *not* hallucinate. This document defines how we measure that.

## Test set

Ground-truth cases live in `tests/evaluation/test_cases/` as JSON, one file per case. Each case
carries the raw office-action text and the expected structured analysis (rejection type, statutory
bases, cited references, and — where feasible — limitation→reference mappings).

Target composition (≥ 20 cases, TC 2100/2600):

| Bucket        | What it tests                                              |
| ------------- | ---------------------------------------------------------- |
| Easy          | Single-reference § 103, clean formatting                   |
| Medium        | Multi-reference § 103 "in view of", dependent claims       |
| Hard          | Mixed rejections (§ 101 Alice + § 103), § 112 definiteness |
| Adversarial   | Non-existent patents, rejections the OA does **not** contain |

The adversarial bucket is the most important: it verifies the system *refuses* to confirm things
that aren't there, rather than producing plausible fabrications.

## Metrics

| Metric                   | Definition                                                        |
| ------------------------ | ----------------------------------------------------------------- |
| Citation accuracy        | correct cited patent numbers / total cited                        |
| Rejection-type accuracy  | correct statutory-basis identification                            |
| Claim-mapping accuracy   | correct limitation → reference mappings                           |
| **Hallucination rate**   | fabricated claims / total atomic claims (verification layer)      |

**Success target:** hallucination rate **< 5%** on the ground-truth set.

## Procedure

1. `python scripts/run_evaluation.py` loads every case and runs the analysis + verification
   pipeline.
2. Each prediction is compared field-by-field against ground truth.
3. The hallucination rate is computed from the `VerificationReport`: any claim with status
   `FABRICATED` counts against it.

## Ablation: with vs. without verification

We report metrics both with the verification layer engaged and with it bypassed, to quantify how
much the decompose → citation-check → entailment pipeline reduces the hallucination rate. This is
the central claim of the project and must be measured, not asserted.

## Draft-level hallucination evaluation (`--mode draft`)

Parse accuracy measures whether Atticus reads the office action correctly. The **draft** eval
measures the harder, product-critical thing: whether the *generated response draft* makes claims it
can back up. It scores the drafter's output, not the OA.

**Pipeline** (`run_draft_evaluation`): for each application → full analysis → generate a response
draft (`strategy=argue`) → decompose the draft into atomic assertions → classify each → verify the
sourced ones.

**Assertion classes:**
- **SOURCED** — carries an inline `[Source: …]` citation.
- **LEGAL** — a statement of law / MPEP procedure (not an independently checkable factual claim).
- **ARGUMENT** — attorney-style reasoning (not independently verifiable).
- **FACTUAL (unsourced)** — a factual disclosure claim (“X discloses …”) with **no** citation. Per
  the grounding rules, a factual claim must carry a source; an unsourced one is a rule violation
  even if it happens to be true.

**Checks on each SOURCED assertion:**
1. **Existence** — does the cited document exist? (USPTO search API)
2. **Location** — does the cited location look valid (col/line for grants, ¶ for publications)?
3. **Entailment** — does the cited passage actually support the assertion? (ENTAILS / CONTRADICTS /
   NEUTRAL, via the verification model)

**Strict definitions (report metrics):**
- **Hallucination** = `fabricated document OR entailment CONTRADICTS`. These are the
  malpractice-grade failures — a cited source that doesn't exist, or one that says the opposite.
- **Review-needed** = `location invalid OR entailment NEUTRAL OR unsourced factual`. Not proven
  wrong, but a practitioner must check before filing.
- **Verified** = document exists, location plausible, passage entails the assertion.
- Rates: `hallucination_rate = (fabricated + contradicts) / sourced`;
  `review_rate = (neutral + location_invalid + factual_unsourced) / total`;
  `verified_rate = verified / sourced`.

Reports are written to `results/evaluations/draft_eval_<provider>_<timestamp>.json`. Entailment is
the token-dominant step, so a per-app entailment budget bounds cost; runs degrade gracefully under
provider rate limits (failed apps are recorded in the report's `errors` list, not crashed).

## Prompt versioning

Every prompt in `src/generation/prompt_templates.py` is versioned. Evaluation results are recorded
in `tests/evaluation/results/` alongside the prompt versions that produced them, so a regression
can always be traced to a specific prompt change.
