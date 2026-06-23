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

## Prompt versioning

Every prompt in `src/generation/prompt_templates.py` is versioned. Evaluation results are recorded
in `tests/evaluation/results/` alongside the prompt versions that produced them, so a regression
can always be traced to a specific prompt change.
