"""
TrustGate Flex — Policy Engine Tests
13 scenarios verifying policy priority, score-based routing, and flag correctness.
"""

import pytest

from backend.services.policy_engine import decide


# ── Helpers ────────────────────────────────────────────
def _benign_context(**overrides) -> dict:
    """Baseline context that won't trigger any P01–P05 rule."""
    ctx = {
        "user_id": "test-user",
        "user_status": "ACTIVE",
        "user_baseline_download_rate": 5.0,
        "active_project_ids": ["proj-1"],
        "device_trust_score": 90,
        "asset_classification": "INTERNAL",
        "asset_project_id": "proj-1",
        "approved_work_session": False,
        "location_hash": "office-hq",
        "known_locations": ["office-hq"],
        "downloads_last_5min": 0,
        "failed_mfa_attempts": 0,
        "is_new_ip": False,
        "concurrent_sessions": 1,
        "rapid_session_switches": False,
        "temporary_permission_active": False,
        "violations_last_24h": 0,
    }
    ctx.update(overrides)
    return ctx


def _risk(score: int) -> dict:
    """Minimal risk_result dict with a given score and empty factors."""
    return {"risk_score": score, "risk_category": "LOW", "factors": []}


# ====================================================================
#  P01 — Revoked / Suspended user (highest priority)
# ====================================================================
class TestP01:
    def test_p01_revoked_overrides_low_score(self):
        """P01 must fire even when risk_score is 0."""
        ctx = _benign_context(user_status="REVOKED")
        result = decide(_risk(0), ctx)
        assert result["outcome"] == "BLOCK_AND_ALERT"
        assert result["policy_applied"] == "P01"
        assert result["enforcement_action"] == "FILE_OPERATION_DENIED"
        assert result["is_blocked"] is True

    def test_p01_suspended(self):
        ctx = _benign_context(user_status="SUSPENDED")
        result = decide(_risk(0), ctx)
        assert result["outcome"] == "BLOCK_AND_ALERT"
        assert result["policy_applied"] == "P01"
        assert result["is_blocked"] is True


# ====================================================================
#  P02 — Restricted asset + untrusted device
# ====================================================================
class TestP02:
    def test_p02_restricted_low_trust(self):
        ctx = _benign_context(
            asset_classification="RESTRICTED",
            device_trust_score=55,
        )
        result = decide(_risk(10), ctx)
        assert result["outcome"] == "STEP_UP_AUTH"
        assert result["policy_applied"] == "P02"
        assert result["enforcement_action"] == "BLOCKED_PENDING_MFA"
        assert result["requires_step_up"] is True


# ====================================================================
#  P03 — Unassigned sensitive asset
# ====================================================================
class TestP03:
    def test_p03_unassigned_confidential(self):
        ctx = _benign_context(
            asset_classification="CONFIDENTIAL",
            asset_project_id="proj-other",
            active_project_ids=["proj-1"],
        )
        result = decide(_risk(10), ctx)
        assert result["outcome"] == "MANAGER_APPROVAL"
        assert result["policy_applied"] == "P03"
        assert result["enforcement_action"] == "BLOCKED_PENDING_APPROVAL"
        assert result["requires_approval"] is True


# ====================================================================
#  P04 — Bulk download anomaly
# ====================================================================
class TestP04:
    def test_p04_bulk_download(self):
        ctx = _benign_context(
            downloads_last_5min=50,
            user_baseline_download_rate=5.0,
            asset_classification="CONFIDENTIAL",
        )
        result = decide(_risk(10), ctx)
        assert result["outcome"] == "RATE_LIMIT_AND_ALERT"
        assert result["policy_applied"] == "P04"
        assert result["enforcement_action"] == "DOWNLOAD_THROTTLED"
        assert result["is_rate_limited"] is True
        assert result["rate_limit_to"] == 5.0


# ====================================================================
#  P05 — Pre-approved work session
# ====================================================================
class TestP05:
    def test_p05_approved_session(self):
        ctx = _benign_context(
            approved_work_session=True,
            device_trust_score=85,
            asset_project_id="proj-1",
            active_project_ids=["proj-1"],
        )
        result = decide(_risk(10), ctx)
        assert result["outcome"] == "ALLOW_WITH_MONITOR"
        assert result["policy_applied"] == "P05"
        assert result["enforcement_action"] == "FILE_SERVED_MONITORED"


# ====================================================================
#  Score-based policies P06 – P10
# ====================================================================
class TestScorePolicies:
    def test_p06_score_15_allow(self):
        ctx = _benign_context()
        result = decide(_risk(15), ctx)
        assert result["outcome"] == "ALLOW"
        assert result["policy_applied"] == "P06"
        assert result["enforcement_action"] == "FILE_SERVED"

    def test_p07_score_35_monitor(self):
        ctx = _benign_context()
        result = decide(_risk(35), ctx)
        assert result["outcome"] == "ALLOW_WITH_MONITOR"
        assert result["policy_applied"] == "P07"
        assert result["enforcement_action"] == "FILE_SERVED_MONITORED"

    def test_p08_score_55_step_up(self):
        ctx = _benign_context()
        result = decide(_risk(55), ctx)
        assert result["outcome"] == "STEP_UP_AUTH"
        assert result["policy_applied"] == "P08"
        assert result["enforcement_action"] == "BLOCKED_PENDING_MFA"
        assert result["requires_step_up"] is True

    def test_p09_score_75_approval(self):
        ctx = _benign_context()
        result = decide(_risk(75), ctx)
        assert result["outcome"] == "MANAGER_APPROVAL"
        assert result["policy_applied"] == "P09"
        assert result["enforcement_action"] == "BLOCKED_PENDING_APPROVAL"
        assert result["requires_approval"] is True

    def test_p10_score_90_block(self):
        ctx = _benign_context()
        result = decide(_risk(90), ctx)
        assert result["outcome"] == "BLOCK_AND_ALERT"
        assert result["policy_applied"] == "P10"
        assert result["enforcement_action"] == "FILE_OPERATION_DENIED"
        assert result["is_blocked"] is True


# ====================================================================
#  Boolean flag exclusivity
# ====================================================================
class TestFlagExclusivity:
    def test_requires_approval_only_for_manager_approval(self):
        """requires_approval must be True ONLY for MANAGER_APPROVAL outcomes."""
        ctx = _benign_context()
        for score, expect_approval in [
            (10, False),   # ALLOW
            (35, False),   # ALLOW_WITH_MONITOR
            (55, False),   # STEP_UP_AUTH
            (75, True),    # MANAGER_APPROVAL
            (90, False),   # BLOCK_AND_ALERT
        ]:
            result = decide(_risk(score), ctx)
            assert result["requires_approval"] is expect_approval, (
                f"score={score}: expected requires_approval={expect_approval}, "
                f"got {result['requires_approval']}"
            )

    def test_is_blocked_only_for_block_and_alert(self):
        """is_blocked must be True ONLY for BLOCK_AND_ALERT outcomes."""
        ctx = _benign_context()
        for score, expect_blocked in [
            (10, False),   # ALLOW
            (35, False),   # ALLOW_WITH_MONITOR
            (55, False),   # STEP_UP_AUTH
            (75, False),   # MANAGER_APPROVAL
            (90, True),    # BLOCK_AND_ALERT
        ]:
            result = decide(_risk(score), ctx)
            assert result["is_blocked"] is expect_blocked, (
                f"score={score}: expected is_blocked={expect_blocked}, "
                f"got {result['is_blocked']}"
            )


# ====================================================================
#  Explanation field sanity
# ====================================================================
class TestExplanation:
    def test_explanation_is_non_empty_string(self):
        ctx = _benign_context()
        for score in (10, 35, 55, 75, 90):
            result = decide(_risk(score), ctx)
            assert isinstance(result["explanation"], str)
            assert len(result["explanation"]) > 10

    def test_block_explanation_mentions_blocked(self):
        ctx = _benign_context(user_status="REVOKED")
        result = decide(_risk(0), ctx)
        assert "blocked" in result["explanation"].lower() or "denied" in result["explanation"].lower()
