"""Shared test fixtures + policy shape builders."""

from __future__ import annotations

import os
from typing import Any

import pytest

# Ensure tests never require a real API key (client supports anonymous mode).
os.environ.setdefault("MAANGO_API_KEY", "")
os.environ.setdefault("MAANGO_API_BASE_URL", "https://api.maango.test")


# --- Policy builders ----------------------------------------------------------


def make_policy(
    *,
    found: bool = True,
    stance: str | None = "selective",
    use_cases: dict[str, str] | None = None,
    blocked_bots: list[str] | None = None,
    allowed_bots: list[str] | None = None,
    signals: dict[str, bool] | None = None,
    error: bool = False,
    error_message: str = "",
    status: int | None = None,
) -> dict[str, Any]:
    """Build a ScanResult-shaped dict for tests."""
    if error:
        return {
            "error": True,
            "message": error_message or "mock error",
            **({"status": status} if status is not None else {}),
        }
    if not found:
        return {"found": False}
    return {
        "found": True,
        "stance": stance,
        "use_cases": use_cases or {},
        "bots": {
            "blocked": blocked_bots or [],
            "allowed": allowed_bots or [],
        },
        "signals": signals or {},
        "domain": "example.com",
    }


@pytest.fixture
def block_all_policy():
    return make_policy(stance="blocks_all_ai")


@pytest.fixture
def allow_all_policy():
    return make_policy(stance="allows_all")


@pytest.fixture
def selective_training_blocked():
    return make_policy(
        stance="selective",
        use_cases={"training": "block", "search": "allow", "ai_input": "allow"},
    )


@pytest.fixture
def selective_training_blocked_legacy():
    return make_policy(
        stance="selective",
        use_cases={"training": "blocked", "search": "allowed", "ai_input": "allowed"},
    )


@pytest.fixture
def with_blocked_bots():
    return make_policy(
        stance="selective",
        use_cases={"training": "allow", "search": "allow", "ai_input": "allow"},
        blocked_bots=["GPTBot", "CCBot", "ClaudeBot"],
    )
