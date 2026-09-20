"""
TrustGate Flex — Policy Engine
Evaluates risk results against an ordered policy chain and returns
a structured enforcement decision.

Policy evaluation order (first match wins):
  P01  Revoked/suspended user          → BLOCK_AND_ALERT
  P02  Restricted + untrusted device   → STEP_UP_AUTH
  P03  Unassigned sensitive asset      → MANAGER_APPROVAL
  P04  Bulk download anomaly           → RATE_LIMIT_AND_ALERT
  P05  Pre-approved work session       → ALLOW_WITH_MONITOR
  P06  Risk 0–29                       → ALLOW
  P07  Risk 30–49                      → ALLOW_WITH_MONITOR
  P08  Risk 50–69                      → STEP_UP_AUTH
  P09  Risk 70–84                      → MANAGER_APPROVAL
  P10  Risk 85–100                     → BLOCK_AND_ALERT
"""

from __future__ import annotations


# ── Outcome → enforcement action lookup ────────────────
_ENFORCEMENT = {
    "ALLOW": "FILE_SERVED",
    "ALLOW_WITH_MONITOR": "FILE_SERVED_MONITORED",
    "READ_ONLY": "VIEW_ONLY_NO_DOWNLOAD",
    "STEP_UP_AUTH": "BLOCKED_PENDING_MFA",
    "MANAGER_APPROVAL": "BLOCKED_PENDING_APPROVAL",
    "TEMPORARY_ACCESS": "FILE_SERVED_WITH_EXPIRY",
    "RATE_LIMIT_AND_ALERT": "DOWNLOAD_THROTTLED",
    "BLOCK_AND_ALERT": "FILE_OPERATION_DENIED",
}


# ====================================================================
#  Explanation builder
# ====================================================================
def _build_explanation(
    outcome: str,
    reason: str,
    risk_result: dict,
    context: dict,
) -> str:
    """
    Build a plain-English explanation combining risk signals and
    the policy decision for end-user / auditor consumption.
    """
    score = risk_result.get("risk_score", 0)
    factors = risk_result.get("factors", [])
    trust = context.get("device_trust_score", 70)
    classification = context.get("asset_classification", "PUBLIC")
    assigned = context.get("asset_project_id", "") in context.get(
        "active_project_ids", []
    )
    baseline = context.get("user_baseline_download_rate", 5.0)
    downloads = context.get("downloads_last_5min", 0)
    velocity_ratio = (downloads / baseline) if baseline > 0 else 0.0

    # ── Opening statement ──────────────────────────────
    if outcome in ("ALLOW", "ALLOW_WITH_MONITOR"):
        opener = "Access granted."
    elif outcome == "STEP_UP_AUTH":
        opener = "Additional authentication required."
    elif outcome == "MANAGER_APPROVAL":
        opener = "Manager approval required."
    elif outcome == "RATE_LIMIT_AND_ALERT":
        opener = "Download rate limited."
    elif outcome == "BLOCK_AND_ALERT":
        opener = "Access blocked."
    else:
        opener = "Decision rendered."

    # ── Detail fragments ───────────────────────────────
    details: list[str] = []

    # Trust signal
    if trust >= 80:
        details.append(f"Device trust is high ({trust})")
    elif trust < 50:
        details.append(f"Device trust is low ({trust}/100)")

    # Assignment
    if assigned:
        details.append("asset is assigned to user's project")
    else:
        details.append("asset is not in user's assigned projects")

    # Velocity
    if velocity_ratio > 2:
        details.append(
            f"user downloading at {velocity_ratio:.0f}\u00d7 their normal rate "
            "\u2014 possible bulk exfiltration attempt"
        )
    elif velocity_ratio <= 1:
        details.append("download velocity is normal")

    # Classification
    if classification in ("RESTRICTED", "CONFIDENTIAL"):
        details.append(f"asset classification is {classification}")

    # User status
    user_status = context.get("user_status", "ACTIVE")
    if user_status in ("REVOKED", "SUSPENDED"):
        details.append(f"user account is {user_status.lower()}")

    # Risk score (for non-trivial decisions)
    if score >= 30:
        details.append(f"risk score {score}/100")

    # ── Assemble ───────────────────────────────────────
    if details:
        body = ", ".join(details) + "."
        # Capitalize first char of body
        body = body[0].upper() + body[1:]
        return f"{opener} {body}"
    return f"{opener} {reason}."


# ====================================================================
#  Context-based policies (P01 – P05)
# ====================================================================
def _p01_revoked_suspended(context: dict) -> dict | None:
    """P01: Block revoked or suspended users immediately."""
    if context.get("user_status") in ("REVOKED", "SUSPENDED"):
        return {
            "outcome": "BLOCK_AND_ALERT",
            "policy_applied": "P01",
            "reason": "User account is revoked or suspended",
        }
    return None


def _p02_restricted_untrusted(context: dict) -> dict | None:
    """P02: Restricted asset on untrusted device → step-up auth."""
    if (
        context.get("asset_classification") == "RESTRICTED"
        and context.get("device_trust_score", 100) < 70
    ):
        return {
            "outcome": "STEP_UP_AUTH",
            "policy_applied": "P02",
            "reason": "Restricted asset requires a trusted managed device",
        }
    return None


def _p03_unassigned_sensitive(context: dict) -> dict | None:
    """P03: Sensitive asset not in user's projects → manager approval."""
    classification = context.get("asset_classification", "PUBLIC")
    asset_project = context.get("asset_project_id", "")
    active = context.get("active_project_ids", [])
    if (
        asset_project not in active
        and classification in ("RESTRICTED", "CONFIDENTIAL")
    ):
        return {
            "outcome": "MANAGER_APPROVAL",
            "policy_applied": "P03",
            "reason": "Asset not in user's assigned projects",
        }
    return None


def _p04_bulk_download(context: dict) -> dict | None:
    """P04: Abnormal download velocity on sensitive assets → throttle."""
    baseline = context.get("user_baseline_download_rate", 5.0)
    downloads = context.get("downloads_last_5min", 0)
    classification = context.get("asset_classification", "PUBLIC")
    if (
        baseline > 0
        and downloads > 2 * baseline
        and classification in ("CONFIDENTIAL", "RESTRICTED")
    ):
        return {
            "outcome": "RATE_LIMIT_AND_ALERT",
            "policy_applied": "P04",
            "reason": "Abnormal download velocity detected — possible bulk exfiltration",
        }
    return None


def _p05_approved_session(context: dict) -> dict | None:
    """P05: Pre-approved work session on trusted device → allow with monitoring."""
    if (
        context.get("approved_work_session") is True
        and context.get("device_trust_score", 0) >= 80
        and context.get("asset_project_id", "") in context.get("active_project_ids", [])
    ):
        return {
            "outcome": "ALLOW_WITH_MONITOR",
            "policy_applied": "P05",
            "reason": "Pre-approved work session active",
        }
    return None


# Ordered policy chain — evaluation stops at first match
_CONTEXT_POLICIES = [
    _p01_revoked_suspended,
    _p02_restricted_untrusted,
    _p03_unassigned_sensitive,
    _p04_bulk_download,
    _p05_approved_session,
]


# ====================================================================
#  Score-based policies (P06 – P10)
# ====================================================================
def _score_policy(score: int) -> dict:
    """Fall-through policy based on composite risk score."""
    if score <= 29:
        return {
            "outcome": "ALLOW",
            "policy_applied": "P06",
            "reason": "Risk score within acceptable threshold",
        }
    elif score <= 49:
        return {
            "outcome": "ALLOW_WITH_MONITOR",
            "policy_applied": "P07",
            "reason": "Elevated risk — access granted with enhanced monitoring",
        }
    elif score <= 69:
        return {
            "outcome": "STEP_UP_AUTH",
            "policy_applied": "P08",
            "reason": "High risk — additional authentication required",
        }
    elif score <= 84:
        return {
            "outcome": "MANAGER_APPROVAL",
            "policy_applied": "P09",
            "reason": "Critical risk — manager approval required",
        }
    else:
        return {
            "outcome": "BLOCK_AND_ALERT",
            "policy_applied": "P10",
            "reason": "Extreme risk — access denied and security alert raised",
        }


# ====================================================================
#  Main entry point
# ====================================================================
def decide(risk_result: dict, context: dict) -> dict:
    """
    Evaluate the ordered policy chain against the risk assessment
    and context, returning a structured enforcement decision.

    Parameters
    ----------
    risk_result : dict
        Output of ``risk_engine.evaluate()``.
    context : dict
        Same context dict passed to the risk engine.

    Returns
    -------
    dict
        Complete decision record with outcome, enforcement action,
        explanation, and boolean convenience flags.
    """
    # ── Phase 1: context-based policies (first match wins) ──
    match = None
    for policy_fn in _CONTEXT_POLICIES:
        match = policy_fn(context)
        if match is not None:
            break

    # ── Phase 2: fall through to score-based policies ───────
    if match is None:
        match = _score_policy(risk_result.get("risk_score", 0))

    outcome = match["outcome"]
    policy = match["policy_applied"]
    reason = match["reason"]

    # ── Derived fields ──────────────────────────────────────
    enforcement = _ENFORCEMENT.get(outcome, "FILE_OPERATION_DENIED")
    explanation = _build_explanation(outcome, reason, risk_result, context)

    baseline = context.get("user_baseline_download_rate", 5.0)
    is_rate_limited = outcome == "RATE_LIMIT_AND_ALERT"

    return {
        "outcome": outcome,
        "policy_applied": policy,
        "enforcement_action": enforcement,
        "reason": reason,
        "explanation": explanation,
        "requires_approval": outcome == "MANAGER_APPROVAL",
        "is_blocked": outcome == "BLOCK_AND_ALERT",
        "requires_step_up": outcome == "STEP_UP_AUTH",
        "is_rate_limited": is_rate_limited,
        "rate_limit_to": baseline if is_rate_limited else None,
    }
