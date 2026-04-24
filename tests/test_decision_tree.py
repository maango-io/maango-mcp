"""Phase 1 — Exhaustive tests for _evaluate_compliance() decision tree.

Covers every branch of the 7-branch tree, every action → use-case mapping,
legacy ↔ canonical permission value normalisation, and priority ordering.
"""

from __future__ import annotations

import pytest

from maango_mcp.server import _evaluate_compliance
from tests.conftest import make_policy


# --- Branch 1: lookup error ---------------------------------------------------


def test_api_error_returns_lookup_error():
    policy = make_policy(error=True, error_message="timeout")
    result = _evaluate_compliance(policy, "train", "")
    assert result["allowed"] is False
    assert result["reason_code"] == "lookup_error"
    assert "timeout" in result["explanation"]


def test_api_error_with_status():
    policy = make_policy(error=True, error_message="unauthorized", status=401)
    result = _evaluate_compliance(policy, "train", "")
    assert result["reason_code"] == "lookup_error"


# --- Branch 2: domain not in registry ----------------------------------------


def test_not_found_returns_no_policy():
    policy = make_policy(found=False)
    result = _evaluate_compliance(policy, "train", "")
    assert result["allowed"] is False
    assert result["reason_code"] == "no_policy"
    assert "not consent" in result["explanation"]


# --- Branch 3: agent explicitly blocked --------------------------------------


def test_agent_in_blocked_bots_exact_match():
    policy = make_policy(blocked_bots=["GPTBot", "CCBot"])
    result = _evaluate_compliance(policy, "train", "GPTBot")
    assert result["allowed"] is False
    assert result["reason_code"] == "bot_blocked"


def test_agent_in_blocked_bots_case_insensitive():
    policy = make_policy(blocked_bots=["GPTBot"])
    for variant in ("gptbot", "GPTBOT", "GPTBot"):
        result = _evaluate_compliance(policy, "train", variant)
        assert result["reason_code"] == "bot_blocked", f"failed for variant: {variant}"


def test_agent_not_in_blocked_bots_passes():
    policy = make_policy(
        blocked_bots=["CCBot"],
        use_cases={"training": "allow"},
    )
    result = _evaluate_compliance(policy, "train", "GPTBot")
    assert result["allowed"] is True


def test_bot_block_overrides_use_case_allow():
    """Agent in blocked_bots → bot_blocked even if use_case allows the action."""
    policy = make_policy(
        blocked_bots=["GPTBot"],
        use_cases={"training": "allow", "search": "allow", "ai_input": "allow"},
    )
    result = _evaluate_compliance(policy, "train", "GPTBot")
    assert result["allowed"] is False
    assert result["reason_code"] == "bot_blocked"


def test_empty_agent_id_skips_bot_check():
    policy = make_policy(
        blocked_bots=["GPTBot"],
        use_cases={"training": "allow"},
    )
    result = _evaluate_compliance(policy, "train", "")
    # Empty agent_id should not match blocked list; falls through to use_case.
    assert result["allowed"] is True
    assert result["reason_code"] == "compliant"


# --- Branch 4: blocks_all_ai stance ------------------------------------------


def test_blocks_all_ai_stance_denies_all(block_all_policy):
    result = _evaluate_compliance(block_all_policy, "train", "")
    assert result["allowed"] is False
    assert result["reason_code"] == "stance_blocks_all"


def test_blocks_all_ai_denies_every_action(block_all_policy):
    for action in ("train", "scrape", "summarize", "search", "index", "cache"):
        result = _evaluate_compliance(block_all_policy, action, "")
        assert result["reason_code"] == "stance_blocks_all", f"failed for {action}"


def test_blocks_all_ai_even_if_use_case_says_allow():
    policy = make_policy(
        stance="blocks_all_ai",
        use_cases={"training": "allow"},
    )
    result = _evaluate_compliance(policy, "train", "")
    assert result["reason_code"] == "stance_blocks_all"


# --- Branch 5: per-use-case decision -----------------------------------------


def test_use_case_blocked_canonical():
    policy = make_policy(use_cases={"training": "block"})
    result = _evaluate_compliance(policy, "train", "")
    assert result["allowed"] is False
    assert result["reason_code"] == "action_blocked"
    assert result["use_case"] == "training"
    assert result["use_case_policy"] == "block"


def test_use_case_blocked_legacy():
    """Legacy plugins emit "blocked" (full word); must normalise to block."""
    policy = make_policy(use_cases={"training": "blocked"})
    result = _evaluate_compliance(policy, "train", "")
    assert result["reason_code"] == "action_blocked"


def test_use_case_allowed_canonical():
    policy = make_policy(use_cases={"training": "allow"})
    result = _evaluate_compliance(policy, "train", "")
    assert result["allowed"] is True
    assert result["reason_code"] == "compliant"


def test_use_case_allowed_legacy():
    policy = make_policy(use_cases={"training": "allowed"})
    result = _evaluate_compliance(policy, "train", "")
    assert result["allowed"] is True


# --- Action → use-case mapping -----------------------------------------------


@pytest.mark.parametrize(
    "action, use_case, expected_allowed",
    [
        ("train", "training", True),
        ("training", "training", True),
        ("scrape", "training", True),      # scrape maps to training
        ("search", "search", True),
        ("index", "search", True),          # index maps to search
        ("cache", "search", True),           # cache maps to search
        ("summarize", "ai_input", True),
        ("inference", "ai_input", True),
        ("ai_input", "ai_input", True),
    ],
)
def test_action_to_use_case_mapping(action, use_case, expected_allowed):
    policy = make_policy(use_cases={use_case: "allow"})
    result = _evaluate_compliance(policy, action, "")
    assert result["allowed"] is expected_allowed
    assert result.get("use_case") == use_case


def test_action_case_insensitive():
    policy = make_policy(use_cases={"training": "allow"})
    for action in ("TRAIN", "Train", "train", "TrAiN"):
        result = _evaluate_compliance(policy, action, "")
        assert result["reason_code"] == "compliant", f"failed for {action}"


# --- Branch 6: allows_all stance fallback ------------------------------------


def test_allows_all_stance_permits_when_use_case_unset(allow_all_policy):
    result = _evaluate_compliance(allow_all_policy, "train", "")
    assert result["allowed"] is True
    assert result["reason_code"] == "compliant"


def test_allows_all_but_use_case_explicitly_blocks():
    """Even under allows_all, an explicit use_case block wins."""
    policy = make_policy(
        stance="allows_all",
        use_cases={"training": "block"},
    )
    result = _evaluate_compliance(policy, "train", "")
    assert result["allowed"] is False
    assert result["reason_code"] == "action_blocked"


# --- Branch 7: unspecified fallback ------------------------------------------


def test_unknown_action_returns_unspecified():
    policy = make_policy(stance="selective", use_cases={"training": "allow"})
    result = _evaluate_compliance(policy, "dance", "")
    assert result["allowed"] is False
    assert result["reason_code"] == "unspecified"


def test_use_case_missing_from_policy_returns_unspecified():
    policy = make_policy(stance="selective", use_cases={})
    result = _evaluate_compliance(policy, "train", "")
    assert result["allowed"] is False
    assert result["reason_code"] == "unspecified"


def test_use_case_value_none_returns_unspecified():
    policy = make_policy(stance="selective", use_cases={"training": None})
    result = _evaluate_compliance(policy, "train", "")
    assert result["reason_code"] == "unspecified"


def test_found_with_no_stance_no_use_cases():
    policy = make_policy(stance=None, use_cases={})
    result = _evaluate_compliance(policy, "train", "")
    assert result["reason_code"] == "unspecified"


# --- Signals surfaced to output ----------------------------------------------


def test_signals_checked_in_output():
    policy = make_policy(
        stance="blocks_all_ai",
        signals={"robots_txt": True, "tdmrep": True, "ai_policy_json": False},
    )
    result = _evaluate_compliance(policy, "train", "")
    assert "robots_txt" in result["signals_checked"]
    assert "tdmrep" in result["signals_checked"]
    assert "ai_policy_json" not in result["signals_checked"]  # false = not checked


def test_signals_empty_when_no_signals():
    policy = make_policy(found=False)
    result = _evaluate_compliance(policy, "train", "")
    assert result["signals_checked"] == []


# --- Bot status in allowed list ----------------------------------------------


def test_bot_in_allowed_list_still_subject_to_use_case():
    policy = make_policy(
        allowed_bots=["GPTBot"],
        use_cases={"training": "block"},
    )
    result = _evaluate_compliance(policy, "train", "GPTBot")
    assert result["allowed"] is False  # use_case block wins
    assert result["reason_code"] == "action_blocked"
    assert result.get("bot_status") == "allowed"


def test_bot_in_allowed_list_and_use_case_allows():
    policy = make_policy(
        allowed_bots=["GPTBot"],
        use_cases={"training": "allow"},
    )
    result = _evaluate_compliance(policy, "train", "GPTBot")
    assert result["allowed"] is True
    assert result.get("bot_status") == "allowed"
