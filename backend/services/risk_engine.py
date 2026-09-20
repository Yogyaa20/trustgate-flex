"""
TrustGate Flex — Risk Engine
Evaluates access requests through 11 weighted risk factors.

FAIRNESS GUARANTEE:
  Time-of-day has ZERO weight.  A request at 2 AM produces the
  identical risk score as the same request at 2 PM.  There is
  deliberately no time-based factor in this engine.
"""

from __future__ import annotations


# ── Score → Category mapping ───────────────────────────
def _classify(score: int) -> str:
    """Map a composite 0-100 risk score to a human-readable category."""
    if score <= 29:
        return "LOW"
    elif score <= 49:
        return "MEDIUM"
    elif score <= 69:
        return "HIGH"
    elif score <= 84:
        return "CRITICAL"
    else:
        return "BLOCK"


# ====================================================================
#  Individual factor evaluators
#  Each returns { factor_name, raw_value, normalized_score, weight,
#                 contribution }
# ====================================================================

# ── 1. Device Trust ────────────────────────────────────
def _device_trust(ctx: dict) -> dict:
    """Lower device trust → higher risk.  Max contribution: 20 pts."""
    trust = ctx.get("device_trust_score", 70)
    contribution = round((1 - trust / 100) * 20, 2)
    return {
        "factor_name": "device_trust",
        "raw_value": str(trust),
        "normalized_score": round(contribution / 20, 4),
        "weight": 20.0,
        "contribution": contribution,
    }


# ── 2. Asset Sensitivity ──────────────────────────────
_SENSITIVITY_MAP = {"RESTRICTED": 20, "CONFIDENTIAL": 15, "INTERNAL": 5, "PUBLIC": 0}


def _asset_sensitivity(ctx: dict) -> dict:
    """Classification drives fixed-point contribution.  Max: 20 pts."""
    classification = ctx.get("asset_classification", "PUBLIC")
    contribution = float(_SENSITIVITY_MAP.get(classification, 0))
    return {
        "factor_name": "asset_sensitivity",
        "raw_value": classification,
        "normalized_score": round(contribution / 20, 4) if contribution else 0.0,
        "weight": 20.0,
        "contribution": contribution,
    }


# ── 3. Project Assignment ─────────────────────────────
def _project_assignment(ctx: dict) -> dict:
    """Unassigned to the asset's project → +15 pts.  Assigned → 0."""
    asset_project = ctx.get("asset_project_id", "")
    active_projects = ctx.get("active_project_ids", [])
    assigned = asset_project in active_projects
    contribution = 0.0 if assigned else 15.0
    return {
        "factor_name": "project_assignment",
        "raw_value": "assigned" if assigned else "unassigned",
        "normalized_score": 0.0 if assigned else 1.0,
        "weight": 15.0,
        "contribution": contribution,
    }


# ── 4. Download Velocity ──────────────────────────────
def _download_velocity(ctx: dict) -> dict:
    """Ratio of recent downloads to user baseline.  Max: 15 pts."""
    downloads = ctx.get("downloads_last_5min", 0)
    baseline = ctx.get("user_baseline_download_rate", 5.0)

    if baseline <= 0:
        ratio = float(downloads) if downloads > 0 else 0.0
    else:
        ratio = downloads / baseline

    if ratio > 2:
        contribution = 15.0
    elif ratio > 1:
        contribution = 7.0
    else:
        contribution = 0.0

    return {
        "factor_name": "download_velocity",
        "raw_value": f"{ratio:.2f}x baseline",
        "normalized_score": round(contribution / 15, 4) if contribution else 0.0,
        "weight": 15.0,
        "contribution": contribution,
    }


# ── 5. Location Anomaly ───────────────────────────────
def _location_anomaly(ctx: dict) -> dict:
    """Unknown location hash → +10 pts."""
    loc = ctx.get("location_hash", "")
    known = ctx.get("known_locations", [])
    anomalous = loc not in known
    contribution = 10.0 if anomalous else 0.0
    return {
        "factor_name": "location_anomaly",
        "raw_value": "unknown" if anomalous else "known",
        "normalized_score": 1.0 if anomalous else 0.0,
        "weight": 10.0,
        "contribution": contribution,
    }


# ── 6. Auth Anomaly ───────────────────────────────────
def _auth_anomaly(ctx: dict) -> dict:
    """Failed MFA ≥ 3 → +8.  New IP alone → +3.  Max: 8 pts."""
    failed_mfa = ctx.get("failed_mfa_attempts", 0)
    new_ip = ctx.get("is_new_ip", False)

    if failed_mfa >= 3:
        contribution = 8.0          # caps at 8, even if also new_ip
    elif new_ip:
        contribution = 3.0
    else:
        contribution = 0.0

    raw_parts = []
    if failed_mfa >= 3:
        raw_parts.append(f"failed_mfa={failed_mfa}")
    if new_ip:
        raw_parts.append("new_ip")

    return {
        "factor_name": "auth_anomaly",
        "raw_value": ", ".join(raw_parts) if raw_parts else "clean",
        "normalized_score": round(contribution / 8, 4) if contribution else 0.0,
        "weight": 8.0,
        "contribution": contribution,
    }


# ── 7. Session Anomaly ────────────────────────────────
def _session_anomaly(ctx: dict) -> dict:
    """concurrent > 1 → +5, rapid switches → +4, both → +7.  Max: 7."""
    concurrent = ctx.get("concurrent_sessions", 1)
    rapid = ctx.get("rapid_session_switches", False)

    multi = concurrent > 1
    if multi and rapid:
        contribution = 7.0
    elif multi:
        contribution = 5.0
    elif rapid:
        contribution = 4.0
    else:
        contribution = 0.0

    return {
        "factor_name": "session_anomaly",
        "raw_value": f"concurrent={concurrent}, rapid={rapid}",
        "normalized_score": round(contribution / 7, 4) if contribution else 0.0,
        "weight": 7.0,
        "contribution": contribution,
    }


# ── 8. User Status ────────────────────────────────────
_STATUS_MAP = {"ACTIVE": 0, "SUSPENDED": 5, "REVOKED": 5}


def _user_status(ctx: dict) -> dict:
    """Non-ACTIVE users incur +5 pts."""
    status = ctx.get("user_status", "ACTIVE")
    contribution = float(_STATUS_MAP.get(status, 0))
    return {
        "factor_name": "user_status",
        "raw_value": status,
        "normalized_score": round(contribution / 5, 4) if contribution else 0.0,
        "weight": 5.0,
        "contribution": contribution,
    }


# ── 9. Temporary Permission ───────────────────────────
def _temp_permission(ctx: dict) -> dict:
    """Active temporary permission → −10 pts (reduces risk)."""
    active = ctx.get("temporary_permission_active", False)
    contribution = -10.0 if active else 0.0
    return {
        "factor_name": "temp_permission",
        "raw_value": str(active),
        "normalized_score": 1.0 if active else 0.0,
        "weight": 10.0,
        "contribution": contribution,
    }


# ── 10. Approved Work Session ─────────────────────────
def _approved_session(ctx: dict) -> dict:
    """Manager-approved session → −8 pts (reduces risk)."""
    approved = ctx.get("approved_work_session", False)
    contribution = -8.0 if approved else 0.0
    return {
        "factor_name": "approved_session",
        "raw_value": str(approved),
        "normalized_score": 1.0 if approved else 0.0,
        "weight": 8.0,
        "contribution": contribution,
    }


# ── 11. Repeat Violations ─────────────────────────────
def _repeat_violations(ctx: dict) -> dict:
    """≥ 3 violations in last 24 h → +8 pts."""
    violations = ctx.get("violations_last_24h", 0)
    triggered = violations >= 3
    contribution = 8.0 if triggered else 0.0
    return {
        "factor_name": "repeat_violations",
        "raw_value": str(violations),
        "normalized_score": 1.0 if triggered else 0.0,
        "weight": 8.0,
        "contribution": contribution,
    }


# ====================================================================
#  Factor registry — ordered list of all evaluators
# ====================================================================
_FACTORS = [
    _device_trust,
    _asset_sensitivity,
    _project_assignment,
    _download_velocity,
    _location_anomaly,
    _auth_anomaly,
    _session_anomaly,
    _user_status,
    _temp_permission,
    _approved_session,
    _repeat_violations,
]


# ====================================================================
#  Main evaluation entry point
# ====================================================================
def evaluate(context: dict) -> dict:
    """
    Run all 11 risk factors against the supplied *context* dict and
    return a structured risk assessment.

    Parameters
    ----------
    context : dict
        Keys expected:
          user_id, user_status, user_baseline_download_rate,
          active_project_ids, device_trust_score, asset_classification,
          asset_project_id, approved_work_session, location_hash,
          known_locations, downloads_last_5min, failed_mfa_attempts,
          is_new_ip, concurrent_sessions, rapid_session_switches,
          temporary_permission_active, violations_last_24h

    Returns
    -------
    dict
        {
          "risk_score":    int   (0–100, clamped),
          "risk_category": str   (LOW/MEDIUM/HIGH/CRITICAL/BLOCK),
          "factors":       list  (one dict per factor)
        }

    Fairness
    --------
    No time-of-day factor exists.  Identical contexts always produce
    identical scores regardless of when the request is made.
    """
    factors = [fn(context) for fn in _FACTORS]

    raw_total = sum(f["contribution"] for f in factors)
    risk_score = max(0, min(100, int(round(raw_total))))
    risk_category = _classify(risk_score)

    return {
        "risk_score": risk_score,
        "risk_category": risk_category,
        "factors": factors,
    }
