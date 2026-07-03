"""Shared pytest fixtures."""

import os

# Keep the test suite hermetic: force every LLM provider to look unconfigured so no test makes a
# live API call (the pipeline degrades to deterministic/offline paths). Env vars override .env,
# and this runs before src.config.get_settings() is first called during collection.
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""

import pytest  # noqa: E402


@pytest.fixture
def sample_office_action() -> str:
    return (
        "UNITED STATES PATENT AND TRADEMARK OFFICE\n"
        "Application No.: 16/123,456\n"
        "Examiner: JOHN Q. SMITH\n"
        "Art Unit: 2186\n"
        "Notification Date: 03/14/2023\n\n"
        "DETAILED ACTION\n"
        "This is a non-final office action.\n\n"
        "Claim Rejections - 35 USC § 103\n"
        "Claims 1-3 are rejected under 35 U.S.C. § 103 as being unpatentable over "
        "Anderson (US 9,876,543 B2) in view of Chen (US2019/0123456 A1).\n"
        "Regarding claim 1, Anderson discloses a processor configured to handle interrupt "
        "requests (col. 4, lines 23-45).\n"
    )
