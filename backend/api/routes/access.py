"""
TrustGate Flex — Access Request routes
Full request → risk → policy → persist → audit pipeline.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4
import traceback

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core.security import get_current_user
from backend.db.database import get_db
from backend.models.models import (
    AccessRequest,
    Alert,
    Approval,
    Asset,
    AuditEvent,
    Decision,
    Device,
    Project,
    RiskFactor,
    User,
)
from backend.services import policy_engine, risk_engine
from backend.services.audit_service import AuditService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/access", tags=["access"])


# ── Request / response schemas ─────────────────────────
class AccessRequestBody(BaseModel):
    asset_id: str
    device_id: str
    session_id: Optional[str] = None
    location_hash: str = ""
    approved_work_session: bool = False
    request_type: str = "READ"
    # Optional signal overrides (for testing / external enrichment)
    failed_mfa_attempts: int = 0
    is_new_ip: bool = False
    concurrent_sessions: int = 1
    rapid_session_switches: bool = False


class BulkDownloadBody(BaseModel):
    asset_id: str
    device_id: str
    file_count: int = 5
    user_id_override: Optional[str] = None


# ── Helpers ────────────────────────────────────────────
def _count_downloads_last_5min(db: Session, user_id: str) -> int:
    cutoff = datetime.utcnow() - timedelta(minutes=5)
    return (
        db.query(AccessRequest)
        .filter(
            AccessRequest.user_id == user_id,
            AccessRequest.request_type.in_(["DOWNLOAD", "EXPORT"]),
            AccessRequest.timestamp >= cutoff,
        )
        .count()
    )


def _count_violations_last_24h(db: Session, user_id: str) -> int:
    cutoff = datetime.utcnow() - timedelta(hours=24)
    return (
        db.query(Decision)
        .join(AccessRequest, Decision.request_id == AccessRequest.id)
        .filter(
            AccessRequest.user_id == user_id,
            Decision.outcome.contains("BLOCK"),
            Decision.decided_at >= cutoff,
        )
        .count()
    )


def _known_locations(db: Session, user_id: str) -> list[str]:
    rows = (
        db.query(AccessRequest.location_hash)
        .filter(
            AccessRequest.user_id == user_id,
            AccessRequest.location_hash.isnot(None),
            AccessRequest.location_hash != "",
        )
        .distinct()
        .all()
    )
    return [r[0] for r in rows]


def _has_temporary_permission(db: Session, user_id: str) -> bool:
    return (
        db.query(Approval)
        .join(AccessRequest, Approval.request_id == AccessRequest.id)
        .filter(
            AccessRequest.user_id == user_id,
            Approval.status == "APPROVED",
            Approval.expires_at > datetime.utcnow(),
        )
        .first()
        is not None
    )


def _build_context(
    user: User,
    device: Device,
    asset: Asset,
    body: AccessRequestBody,
    db: Session,
) -> dict:
    """Assemble the full 11-signal context dict for the risk engine."""
    active_project_ids = json.loads(user.active_project_ids or "[]")
    return {
        "user_id": user.id,
        "user_status": user.status,
        "user_baseline_download_rate": user.baseline_download_rate,
        "active_project_ids": active_project_ids,
        "device_trust_score": device.trust_score,
        "asset_classification": asset.classification,
        "asset_project_id": asset.project_id,
        "approved_work_session": body.approved_work_session,
        "location_hash": body.location_hash,
        "known_locations": _known_locations(db, user.id),
        "downloads_last_5min": _count_downloads_last_5min(db, user.id),
        "failed_mfa_attempts": body.failed_mfa_attempts,
        "is_new_ip": body.is_new_ip,
        "concurrent_sessions": body.concurrent_sessions,
        "rapid_session_switches": body.rapid_session_switches,
        "temporary_permission_active": _has_temporary_permission(db, user.id),
        "violations_last_24h": _count_violations_last_24h(db, user.id),
    }


def _run_pipeline(
    user: User,
    device: Device,
    asset: Asset,
    body: AccessRequestBody,
    db: Session,
) -> dict:
    """Execute the full risk → policy → persist → audit pipeline."""
    start = time.perf_counter()

    # ── 1. Build context ───────────────────────────────
    logger.info("→ Loading context...")
    context = _build_context(user, device, asset, body, db)

    # ── 2. Risk evaluation ─────────────────────────────
    logger.info("→ Running risk engine...")
    risk_result = risk_engine.evaluate(context)

    # ── 3. Policy decision ─────────────────────────────
    logger.info("→ Running policy engine...")
    decision_result = policy_engine.decide(risk_result, context)

    # ── 4. Persist AccessRequest ───────────────────────
    logger.info("→ Saving to DB...")
    req = AccessRequest(
        id=str(uuid4()),
        user_id=user.id,
        device_id=device.id,
        asset_id=asset.id,
        session_id=body.session_id or str(uuid4()),
        request_type=body.request_type,
        timestamp=datetime.utcnow(),
        location_hash=body.location_hash,
        approved_work_session=body.approved_work_session,
    )
    db.add(req)
    db.flush()

    # ── 5. Persist Decision ────────────────────────────
    dec = Decision(
        id=str(uuid4()),
        request_id=req.id,
        risk_score=risk_result["risk_score"],
        risk_category=risk_result["risk_category"],
        policy_applied=decision_result["policy_applied"],
        outcome=decision_result["outcome"],
        enforcement_action=decision_result["enforcement_action"],
        explanation=decision_result["explanation"],
        latency_ms=0,
        decided_at=datetime.utcnow(),
    )
    db.add(dec)
    db.flush()

    # ── 6. Persist RiskFactors ─────────────────────────
    for f in risk_result["factors"]:
        db.add(
            RiskFactor(
                id=str(uuid4()),
                request_id=req.id,
                factor_name=f["factor_name"],
                raw_value=f["raw_value"],
                normalized_score=f["normalized_score"],
                weight=f["weight"],
                contribution=f["contribution"],
            )
        )

    # ── 7. Alert (if blocked / rate-limited) ───────────
    if decision_result["outcome"] in ("BLOCK_AND_ALERT", "RATE_LIMIT_AND_ALERT"):
        severity = (
            "CRITICAL"
            if decision_result["outcome"] == "BLOCK_AND_ALERT"
            else "HIGH"
        )
        db.add(
            Alert(
                id=str(uuid4()),
                request_id=req.id,
                severity=severity,
                message=decision_result["explanation"],
                acknowledged=False,
                sent_at=datetime.utcnow(),
            )
        )

    # ── 8. Approval (if escalated) ─────────────────────
    approval_id: str | None = None
    if decision_result["outcome"] == "MANAGER_APPROVAL":
        # Assign to first available ADMIN
        manager = (
            db.query(User).filter(User.role == "ADMIN", User.status == "ACTIVE").first()
        )
        appr = Approval(
            id=str(uuid4()),
            request_id=req.id,
            manager_id=manager.id if manager else user.id,
            status="PENDING",
            expires_at=datetime.utcnow() + timedelta(hours=4),
        )
        db.add(appr)
        db.flush()
        approval_id = appr.id

    # ── 9. Audit event ─────────────────────────────────
    logger.info("→ Writing audit event...")
    audit_event = AuditService.write_event(
        db,
        entity_type="AccessRequest",
        entity_id=req.id,
        action=f"access.{decision_result['outcome'].lower().replace('_', '-')}",
        actor_id=user.id,
        data={
            "risk_score": risk_result["risk_score"],
            "outcome": decision_result["outcome"],
            "policy": decision_result["policy_applied"],
            "asset": asset.name,
        },
    )

    latency_ms = int((time.perf_counter() - start) * 1000)
    dec.latency_ms = latency_ms

    db.flush()

    logger.info(f"✓ Decision: {decision_result['outcome']}, Score: {risk_result['risk_score']}, Latency: {latency_ms}ms")

    return {
        "request_id": req.id,
        "risk_score": risk_result["risk_score"],
        "risk_category": risk_result["risk_category"],
        "decision": decision_result["outcome"],
        "enforcement_action": decision_result["enforcement_action"],
        "policy_applied": decision_result["policy_applied"],
        "explanation": decision_result["explanation"],
        "factors": [
            {
                "name": f["factor_name"],
                "raw_value": f["raw_value"],
                "contribution": f["contribution"],
                "weight": f["weight"],
            }
            for f in risk_result["factors"]
        ],
        "requires_approval": decision_result["requires_approval"],
        "approval_id": approval_id,
        "audit_event_id": audit_event.id,
        "latency_ms": latency_ms,
    }


# ====================================================================
#  POST /access/request
# ====================================================================
@router.post("/request")
def create_access_request(
    body: AccessRequestBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit an access request — full risk + policy + persist pipeline."""
    logger.info("→ [POST /access/request] called")
    try:
        logger.info("→ Loading user, device, asset...")
        device = db.query(Device).filter(Device.id == body.device_id).first()
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        asset = db.query(Asset).filter(Asset.id == body.asset_id).first()
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        result = _run_pipeline(user, device, asset, body, db)
        db.commit()
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Exception in /access/request")
        return {"error": str(e), "step": "create_access_request execution", "traceback": traceback.format_exc()}


# ====================================================================
#  GET /access/request/{request_id}/replay
# ====================================================================
@router.get("/request/{request_id}/replay")
def replay_request(
    request_id: str,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return a complete decision replay for audit / explainability."""
    logger.info(f"→ [GET /access/request/{request_id}/replay] called")
    try:
        req = db.query(AccessRequest).filter(AccessRequest.id == request_id).first()
        if not req:
            raise HTTPException(status_code=404, detail="Access request not found")

        user = db.query(User).filter(User.id == req.user_id).first()
        device = db.query(Device).filter(Device.id == req.device_id).first()
        asset = db.query(Asset).filter(Asset.id == req.asset_id).first()
        project = db.query(Project).filter(Project.id == asset.project_id).first() if asset else None
        decision = db.query(Decision).filter(Decision.request_id == req.id).first()
        risk_factors = db.query(RiskFactor).filter(RiskFactor.request_id == req.id).all()
        approval = db.query(Approval).filter(Approval.request_id == req.id).first()
        audit_event = (
            db.query(AuditEvent)
            .filter(
                AuditEvent.entity_type == "AccessRequest",
                AuditEvent.entity_id == req.id,
            )
            .first()
        )

        # Build response
        approval_block = None
        if approval:
            manager = db.query(User).filter(User.id == approval.manager_id).first()
            approval_block = {
                "manager_name": manager.name if manager else "Unknown",
                "status": approval.status,
                "reason": approval.reason,
                "approved_at": approval.approved_at.isoformat() if approval.approved_at else None,
                "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
            }

        audit_block = None
        if audit_event:
            audit_block = {
                "event_id": audit_event.id,
                "timestamp": audit_event.timestamp.isoformat(),
                "event_hash": audit_event.event_hash,
                "prev_hash": audit_event.prev_hash,
            }

        return {
            "request": {
                "user_name": user.name if user else "Unknown",
                "user_role": user.role if user else "Unknown",
                "user_status": user.status if user else "Unknown",
                "device_trust": device.trust_score if device else 0,
                "device_managed": device.is_managed if device else False,
                "device_hash": device.device_hash if device else "Unknown",
                "asset_name": asset.name if asset else "Unknown",
                "asset_classification": asset.classification if asset else "Unknown",
                "project_name": project.name if project else "Unknown",
                "request_type": req.request_type,
                "timestamp": req.timestamp.isoformat(),
            },
            "risk": {
                "score": decision.risk_score if decision else 0,
                "category": decision.risk_category if decision else "UNKNOWN",
                "factors": [
                    {
                        "name": rf.factor_name,
                        "weight": rf.weight,
                        "contribution": rf.contribution,
                        "raw_value": rf.raw_value,
                    }
                    for rf in risk_factors
                ],
            },
            "policy": {
                "policy_applied": decision.policy_applied if decision else None,
                "outcome": decision.outcome if decision else None,
                "reason": decision.explanation if decision else None,
                "enforcement_action": decision.enforcement_action if decision else None,
            },
            "approval": approval_block,
            "audit": audit_block,
            "explanation": decision.explanation if decision else "No decision recorded",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Exception in /access/request/replay")
        return {"error": str(e), "step": "replay_request execution", "traceback": traceback.format_exc()}


# ====================================================================
#  GET /access/requests
# ====================================================================
@router.get("/requests")
def list_requests(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the most recent access requests with decision info."""
    logger.info("→ [GET /access/requests] called")
    try:
        query = (
            db.query(AccessRequest, Decision)
            .outerjoin(Decision, Decision.request_id == AccessRequest.id)
            .order_by(AccessRequest.timestamp.desc())
        )
        
        if user.role not in ["ADMIN", "AUDITOR", "MANAGER"]:
            query = query.filter(AccessRequest.user_id == user.id)
            
        rows = query.offset(skip).limit(limit).all()
        results = []
        for req, dec in rows:
            user = db.query(User).filter(User.id == req.user_id).first()
            asset = db.query(Asset).filter(Asset.id == req.asset_id).first()
            results.append(
                {
                    "request_id": req.id,
                    "user_name": user.name if user else "Unknown",
                    "user_role": user.role if user else "Unknown",
                    "asset_name": asset.name if asset else "Unknown",
                    "asset_classification": asset.classification if asset else "Unknown",
                    "request_type": req.request_type,
                    "timestamp": req.timestamp.isoformat(),
                    "risk_score": dec.risk_score if dec else None,
                    "risk_category": dec.risk_category if dec else None,
                    "outcome": dec.outcome if dec else None,
                    "policy_applied": dec.policy_applied if dec else None,
                    "enforcement_action": dec.enforcement_action if dec else None,
                }
            )
        return {"total": len(results), "skip": skip, "limit": limit, "requests": results}
    except Exception as e:
        logger.exception("Exception in /access/requests")
        return {"error": str(e), "step": "list_requests execution", "traceback": traceback.format_exc()}


# ====================================================================
#  POST /access/simulate_bulk_download
# ====================================================================
@router.post("/simulate_bulk_download")
def simulate_bulk_download(
    body: BulkDownloadBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Simulate *file_count* rapid DOWNLOAD requests to demonstrate
    how the risk engine and policy engine escalate enforcement
    as download velocity increases.
    """
    logger.info("→ [POST /access/simulate_bulk_download] called")
    try:
        device = db.query(Device).filter(Device.id == body.device_id).first()
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        asset = db.query(Asset).filter(Asset.id == body.asset_id).first()
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        if body.user_id_override:
            sim_user = db.query(User).filter(User.id == body.user_id_override).first()
            if not sim_user:
                raise HTTPException(status_code=404, detail="Override user not found")
        else:
            sim_user = user

        decisions: list[dict] = []
        throttle_triggered_at: int | None = None

        import json as _json
        original_project_ids = sim_user.active_project_ids
        sim_project_ids = _json.loads(sim_user.active_project_ids or "[]")
        if asset.project_id and asset.project_id not in sim_project_ids:
            sim_project_ids.append(asset.project_id)
            sim_user.active_project_ids = _json.dumps(sim_project_ids)

        for i in range(body.file_count):
            req_body = AccessRequestBody(
                asset_id=body.asset_id,
                device_id=body.device_id,
                request_type="DOWNLOAD",
                location_hash="office-hq",
            )
            result = _run_pipeline(sim_user, device, asset, req_body, db)
            db.flush()

            entry = {
                "iteration": i + 1,
                "risk_score": result["risk_score"],
                "decision": result["decision"],
                "policy_applied": result["policy_applied"],
                "enforcement_action": result["enforcement_action"],
            }
            decisions.append(entry)

            if (
                throttle_triggered_at is None
                and result["decision"] in ("RATE_LIMIT_AND_ALERT", "BLOCK_AND_ALERT")
            ):
                throttle_triggered_at = i + 1

        sim_user.active_project_ids = original_project_ids
        db.commit()

        return {
            "file_count": body.file_count,
            "throttle_triggered_at": throttle_triggered_at,
            "decisions": decisions,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Exception in /access/simulate_bulk_download")
        return {"error": str(e), "step": "simulate_bulk_download execution", "traceback": traceback.format_exc()}

class SimulateEvaluateBody(BaseModel):
    device_trust_score: int = 85
    asset_classification: str = "INTERNAL"
    project_assigned: bool = True
    download_velocity_ratio: float = 1.0
    location_known: bool = True
    failed_mfa_attempts: int = 0
    concurrent_sessions: int = 1
    user_status: str = "ACTIVE"
    approved_work_session: bool = False
    temporary_permission_active: bool = False
    violations_last_24h: int = 0

@router.post("/simulate_evaluate")
def simulate_evaluate(body: SimulateEvaluateBody):
    """Evaluate risk + policy without DB writes. For the Policy Simulator UI."""
    context = {
        "user_id": "simulator",
        "user_status": body.user_status,
        "user_baseline_download_rate": 5.0,
        "active_project_ids": ["sim-project"] if body.project_assigned else [],
        "device_trust_score": body.device_trust_score,
        "asset_classification": body.asset_classification,
        "asset_project_id": "sim-project",
        "approved_work_session": body.approved_work_session,
        "location_hash": "known-location" if body.location_known else "unknown-xyz",
        "known_locations": ["known-location"],
        "downloads_last_5min": int(body.download_velocity_ratio * 5.0 * 2),
        "failed_mfa_attempts": body.failed_mfa_attempts,
        "is_new_ip": False,
        "concurrent_sessions": body.concurrent_sessions,
        "rapid_session_switches": False,
        "temporary_permission_active": body.temporary_permission_active,
        "violations_last_24h": body.violations_last_24h,
    }
    risk_result = risk_engine.evaluate(context)
    decision_result = policy_engine.decide(risk_result, context)
    return {
        "risk_score": risk_result["risk_score"],
        "risk_category": risk_result["risk_category"],
        "factors": risk_result["factors"],
        "decision": decision_result["outcome"],
        "policy_applied": decision_result["policy_applied"],
        "enforcement_action": decision_result["enforcement_action"],
        "explanation": decision_result["explanation"],
    }

@router.post("/demo_reset_velocity")
def demo_reset_velocity(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cutoff = datetime.utcnow() - timedelta(minutes=5)
    db.query(AccessRequest).filter(
        AccessRequest.user_id == user.id,
        AccessRequest.timestamp >= cutoff
    ).delete()
    db.commit()
    return {"status": "cleared", "message": "Recent download history cleared"}
