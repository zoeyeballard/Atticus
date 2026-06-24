"""Tests for deterministic rejection-block extraction (Step 7 failure modes)."""

from src.data import office_action_parser as oap
from src.models.schemas import RejectionBasis


def test_parse_claim_numbers_ranges_and_lists():
    assert oap.parse_claim_numbers("1-4") == [1, 2, 3, 4]
    assert oap.parse_claim_numbers("5, 7 and 9-11") == [5, 7, 9, 10, 11]
    assert oap.parse_claim_numbers("1") == [1]
    assert oap.parse_claim_numbers("3–5") == [3, 4, 5]  # en-dash


def test_grouped_range_rejection():
    text = (
        "Claims 1-4 are rejected under 35 U.S.C. § 103 as being unpatentable over "
        "Anderson (US 9,876,543 B2) in view of Chen (US2019/0123456 A1)."
    )
    rejections = oap.extract_rejections(text)
    nums = sorted(r.claim_number for r in rejections)
    assert nums == [1, 2, 3, 4]
    assert all(r.rejection_basis == RejectionBasis.SEC_103 for r in rejections)
    # Lowest claim in the block is treated as independent.
    assert next(r for r in rejections if r.claim_number == 1).is_independent is True
    assert next(r for r in rejections if r.claim_number == 2).is_independent is False
    # References are scoped to the block and attached to each claim.
    refs = {ref.patent_number for r in rejections for ref in r.cited_references}
    assert any("9876543" in n.replace(",", "") for n in refs)


def test_multiple_bases_same_claim():
    text = (
        "Claim 1 is rejected under 35 U.S.C. § 103 as obvious over Smith (US 9,000,000 B2).\n"
        "Claim 1 is rejected under 35 U.S.C. 112(b) as being indefinite.\n"
    )
    rejections = oap.extract_rejections(text)
    bases = {r.rejection_basis for r in rejections if r.claim_number == 1}
    assert RejectionBasis.SEC_103 in bases
    assert RejectionBasis.SEC_112_B in bases


def test_grouped_rejection_with_two_groups():
    text = (
        "Claims 1-4 are rejected under 35 U.S.C. § 103 as obvious over Smith (US 9,000,000 B2) "
        "in view of Jones (US 9,111,111 B2).\n"
        "Claims 5-8 are rejected under 35 U.S.C. § 103 as obvious over Smith in view of Jones "
        "and further in view of Brown (US 9,222,222 B2).\n"
    )
    rejections = oap.extract_rejections(text)
    nums = sorted(r.claim_number for r in rejections)
    assert nums == [1, 2, 3, 4, 5, 6, 7, 8]
    # Brown should only be attributed to the second block (claims 5-8).
    claim8 = next(r for r in rejections if r.claim_number == 8)
    claim1 = next(r for r in rejections if r.claim_number == 1)
    c8_refs = {n.replace(",", "") for ref in claim8.cited_references for n in [ref.patent_number]}
    c1_refs = {n.replace(",", "") for ref in claim1.cited_references for n in [ref.patent_number]}
    assert any("9222222" in n for n in c8_refs)
    assert not any("9222222" in n for n in c1_refs)


def test_112a_basis_detection():
    text = "Claim 2 is rejected under 35 U.S.C. § 112(a) as failing the written description."
    rejections = oap.extract_rejections(text)
    assert rejections[0].rejection_basis == RejectionBasis.SEC_112_A


# --- Real-world phrasings observed in live USPTO office actions (app 19531961, CTNF) ---
# These are the exact boilerplate variants that broke the first regex; keep them locked.


def test_real_no_isare_no_section_symbol():
    # "Claims 33-36 rejected under 35 U.S.C. 112(b)" — no "is/are", no § symbol.
    text = "Claims 33-36 rejected under 35 U.S.C. 112(b) or 35 U.S.C. 112 (pre-AIA), second paragraph"
    rejections = oap.extract_rejections(text)
    assert {r.claim_number for r in rejections} == {33, 34, 35, 36}
    assert all(r.rejection_basis == RejectionBasis.SEC_112_B for r in rejections)


def test_real_claim_s_and_is_are_slash():
    # "Claim(s) 21-24, 33-36 is/are rejected under 35 U.S.C. 102(a)(1)" — literal "(s)" and "is/are".
    text = "Claim(s) 21-24, 33-36 is/are rejected under 35 U.S.C. 102(a)(1) as being anticipated by Fink"
    rejections = oap.extract_rejections(text)
    assert {r.claim_number for r in rejections} == {21, 22, 23, 24, 33, 34, 35, 36}
    assert all(r.rejection_basis == RejectionBasis.SEC_102 for r in rejections)


def test_real_103_unpatentable_over():
    text = "Claim(s) 25-26 is/are rejected under 35 U.S.C. 103 as being unpatentable over Fink"
    rejections = oap.extract_rejections(text)
    assert {r.claim_number for r in rejections} == {25, 26}
    assert all(r.rejection_basis == RejectionBasis.SEC_103 for r in rejections)
