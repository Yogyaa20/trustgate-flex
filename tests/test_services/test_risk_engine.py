"""
TrustGate Flex — Risk Engine Tests
8 deterministic scenarios verifying factor logic, fairness, and edge cases.
"""

import pytest

from backend.services.risk_engine import evaluate


# ── Helper: build a fully-benign baseline context ──────
def _base_context(**overrides) -> dict:
    """Return a zero-risk context, then apply any overrides."""
    ctx = {
        "user_id": "test-user-001",
        "user_status": "ACTIVE",
        "user_baseline_download_rate": 5.0,
        "active_project_ids": ["proj-1"],
        "device_trust_score": 100,
        "asset_classification": "PUBLIC",
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


def _get_factor(result: dict, name: str) -> dict:
    """Extract a single factor dict by name from evaluate() output."""
    for f in result["factors"]:
        if f["factor_name"] == name:
            return f
    raise KeyError(f"Factor '{name}' not found in result")


# ====================================================================
# TEST 1 — Trusted device, CONFIDENTIAL, assigned, low velocity
# ====================================================================
class TestTrustedConfidential:
    """
    trust=92, CONFIDENTIAL, assigned, downloads=1 (ratio 0.2x), known location.
    Expected contributions:
      device_trust  = (1 − 0.92) × 20 = 1.6
      asset_sens    = 15
      all others    = 0
    Total = 16.6 → 17, category = LOW
    """

    def test_1_score_is_low(self):
        ctx = _base_context(
            device_trust_score=92,
            asset_classification="CONFIDENTIAL",
            downloads_last_5min=1,
        )
        result = evaluate(ctx)
        assert result["risk_score"] == 17
        assert result["risk_category"] == "LOW"

    # ── TEST 2 — Fairness proof: 2 AM == 2 PM ─────────
    def test_2_time_invariance(self):
        """
        Identical context — no time field exists in the engine,
        so the score must be bit-for-bit identical regardless of
        when the caller invokes it.
        """
        ctx_day = _base_context(
            device_trust_score=92,
            asset_classification="CONFIDENTIAL",
            downloads_last_5min=1,
        )
        ctx_night = ctx_day.copy()  # exact same dict

        result_day = evaluate(ctx_day)
        result_night = evaluate(ctx_night)

        assert result_day["risk_score"] == result_night["risk_score"]
        assert result_day["risk_category"] == result_night["risk_category"]
        assert result_day["factors"] == result_night["factors"]


# ====================================================================
# TEST 3 — Untrusted device, RESTRICTED, multi-signal threat
# ====================================================================
class TestUntrustedRestricted:
    """
    trust=35, RESTRICTED, assigned, unknown location,
    failed_mfa=3, concurrent=2 + rapid switches.

    Contributions:
      device_trust      = (1 − 0.35) × 20 = 13
      asset_sensitivity  = 20
      location_anomaly   = 10
      auth_anomaly       = 8   (failed_mfa ≥ 3)
      session_anomaly    = 7   (concurrent + rapid)
    Total = 58, category = HIGH
    """

    def test_3_high_risk(self):
        ctx = _base_context(
            device_trust_score=35,
            asset_classification="RESTRICTED",
            location_hash="unknown-cafe-wifi",
            known_locations=["office-hq"],
            failed_mfa_attempts=3,
            is_new_ip=True,
            concurrent_sessions=2,
            rapid_session_switches=True,
        )
        result = evaluate(ctx)
        assert 55 <= result["risk_score"] <= 70
        assert result["risk_category"] == "HIGH"


# ====================================================================
# TEST 4 — Bulk download (10× baseline) → CRITICAL or BLOCK
# ====================================================================
class TestBulkDownload:
    """
    trust=30, RESTRICTED, unassigned project, 50 downloads /
    baseline 5.0 = 10× velocity, unknown location, failed MFA,
    concurrent sessions.

    Contributions:
      device_trust      = 14
      asset_sensitivity  = 20
      project_assignment = 15
      download_velocity  = 15  (ratio > 2)
      location_anomaly   = 10
      auth_anomaly       = 8
      session_anomaly    = 7
    Total = 89, category = BLOCK
    """

    def test_4_critical_or_block(self):
        ctx = _base_context(
            device_trust_score=30,
            asset_classification="RESTRICTED",
            asset_project_id="proj-99",
            active_project_ids=["proj-1"],
            downloads_last_5min=50,
            location_hash="unknown-network",
            known_locations=["office-hq"],
            failed_mfa_attempts=3,
            is_new_ip=True,
            concurrent_sessions=2,
            rapid_session_switches=True,
        )
        result = evaluate(ctx)
        assert result["risk_score"] >= 70
        assert result["risk_category"] in ("CRITICAL", "BLOCK")


# ====================================================================
# TEST 5 — Revoked user adds 5 points
# ====================================================================
class TestRevokedUser:
    def test_5_revoked_contributes_5(self):
        ctx = _base_context(user_status="REVOKED")
        result = evaluate(ctx)
        factor = _get_factor(result, "user_status")
        assert factor["contribution"] == 5.0
        assert result["risk_score"] == 5


# ====================================================================
# TEST 6 — Approved work session reduces score by 8
# ====================================================================
class TestApprovedSession:
    def test_6_approved_reduces_by_8(self):
        # Build a context with some positive risk first
        base = _base_context(
            device_trust_score=60,
            asset_classification="CONFIDENTIAL",
        )
        score_without = evaluate(base)["risk_score"]

        base_approved = {**base, "approved_work_session": True}
        score_with = evaluate(base_approved)["risk_score"]

        assert score_without - score_with == 8
        # Verify the factor itself
        factor = _get_factor(evaluate(base_approved), "approved_session")
        assert factor["contribution"] == -8.0


# ====================================================================
# TEST 7 — All factors at maximum → clamped to 100
# ====================================================================
class TestMaximumRisk:
    """
    Every positive factor at max, negative factors disabled.
    Positive sum = 20+20+15+15+10+8+7+5+8 = 108 → clamped to 100.
    """

    def test_7_clamped_at_100(self):
        ctx = _base_context(
            device_trust_score=0,              # +20
            asset_classification="RESTRICTED", # +20
            asset_project_id="proj-unassigned", # +15
            active_project_ids=["proj-1"],
            downloads_last_5min=100,           # ratio 20× → +15
            location_hash="unknown",           # +10
            known_locations=["office-hq"],
            failed_mfa_attempts=5,             # +8
            is_new_ip=True,
            concurrent_sessions=3,             # +7 (with rapid)
            rapid_session_switches=True,
            user_status="REVOKED",             # +5
            temporary_permission_active=False,  # 0
            approved_work_session=False,        # 0
            violations_last_24h=5,             # +8
        )
        result = evaluate(ctx)
        assert result["risk_score"] == 100
        assert result["risk_category"] == "BLOCK"

        # Raw sum should exceed 100 (verifies clamping)
        raw = sum(f["contribution"] for f in result["factors"])
        assert raw == 108.0


# ====================================================================
# TEST 8 — Fully benign context → score 0
# ====================================================================
class TestFullyBenign:
    def test_8_zero_risk(self):
        ctx = _base_context()  # all defaults are benign
        result = evaluate(ctx)
        assert result["risk_score"] == 0
        assert result["risk_category"] == "LOW"
        # Every contribution must be zero
        for f in result["factors"]:
            assert f["contribution"] == 0.0, f"Non-zero: {f['factor_name']}"
