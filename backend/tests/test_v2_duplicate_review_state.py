"""Tests for V2 duplicate policy state."""

from types import SimpleNamespace

from companion.v2_duplicate_review_state import v2_policy_state


def group(*, eligible=True, status="exact", offline=False, auto_selected=False):
    return SimpleNamespace(
        eligible=eligible,
        status=status,
        members=[SimpleNamespace(is_offline=offline)],
        auto_selected=auto_selected,
    )


def test_policy_state_keeps_auto_ready_distinct_from_actionable() -> None:
    assert v2_policy_state(group(eligible=False, auto_selected=True)) == "blocked"
    assert v2_policy_state(group(status="ineligible")) == "blocked"
    assert v2_policy_state(group(offline=True)) == "blocked"
    assert v2_policy_state(group(auto_selected=True)) == "auto_ready"
    assert v2_policy_state(group()) == "needs_review"
