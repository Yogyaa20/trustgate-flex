"""
TrustGate Flex — Approval routes
Manager / Admin approval workflow for escalated access requests.
"""

from __future__ import annotations

import logging
import traceback
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core.security import get_current_user, require_roles
from backend.db.database import get_db
from backend.models.models import (
    AccessRequest,
    Alert,
    Approval,
    Asset,
    Decision,
    User,
)
from backend.services.audit_service import AuditService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/approvals", tags=["approvals"])


class ApprovalDecideBody(BaseModel):
    approved: bool
    reason: str = ""
    duration_minutes: int = 60


# ====================================================================
#  GET /approvals/pending
# ====================================================================
@router.get("/pending")
def list_pending(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
):
    """List all pending approval requests (ADMIN only)."""
    logger.info("→ [GET /approvals/pending] called")
    try:
        rows = (
            db.query(Approval)
            .filter(Approval.status == "PENDING")
            .order_by(Approval.expires_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        results = []
        for appr in rows:
            req = db.query(AccessRequest).filter(AccessRequest.id == appr.request_id).first()
            requester = db.query(User).filter(User.id == req.user_id).first() if req else None
            asset = db.query(Asset).filter(Asset.id == req.asset_id).first() if req else None
            decision = db.query(Decision).filter(Decision.request_id == appr.request_id).first()
            results.append(
                {
                    "approval_id": appr.id,
                    "request_id": appr.request_id,
                    "requester_name": requester.name if requester else "Unknown",
                    "requester_role": requester.role if requester else "Unknown",
                    "asset_name": asset.name if asset else "Unknown",
                    "asset_classification": asset.classification if asset else "Unknown",
                    "risk_score": decision.risk_score if decision else None,
                    "risk_category": decision.risk_category if decision else None,
                    "explanation": decision.explanation if decision else None,
                    "expires_at": appr.expires_at.isoformat() if appr.expires_at else None,
                }
            )
        return {"total": len(results), "approvals": results}
    except Exception as e:
        logger.exception("Exception in /approvals/pending")
        return {"error": str(e), "step": "list_pending execution", "traceback": traceback.format_exc()}


# ====================================================================
#  POST /approvals/{approval_id}/decide
# ====================================================================
@router.post("/{approval_id}/decide")
def decide_approval(
    approval_id: str,
    body: ApprovalDecideBody,
    user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
):
    """Approve or deny a pending approval request."""
    logger.info(f"→ [POST /approvals/{approval_id}/decide] called")
    try:
        appr = db.query(Approval).filter(Approval.id == approval_id).first()
        if not appr:
            raise HTTPException(status_code=404, detail="Approval not found")
        if appr.status != "PENDING":
            raise HTTPException(status_code=400, detail="Approval already resolved")

        decision = db.query(Decision).filter(Decision.request_id == appr.request_id).first()
        req = db.query(AccessRequest).filter(AccessRequest.id == appr.request_id).first()

        if body.approved:
            appr.status = "APPROVED"
            appr.reason = body.reason or "Approved by manager"
            appr.approved_at = datetime.utcnow()
            appr.expires_at = datetime.utcnow() + timedelta(minutes=body.duration_minutes)

            # Update decision to TEMPORARY_ACCESS
            if decision:
                decision.outcome = "TEMPORARY_ACCESS"
                decision.enforcement_action = "FILE_SERVED_WITH_EXPIRY"
                decision.explanation = (
                    f"Manager-approved temporary access ({body.duration_minutes} min). "
                    f"Original: {decision.explanation}"
                )

            action = "approval.approved"
            logger.info(f"✓ Decision: APPROVED for request {appr.request_id}")
        else:
            appr.status = "DENIED"
            appr.reason = body.reason or "Denied by manager"

            # Create alert for denial
            db.add(
                Alert(
                    id=str(uuid4()),
                    request_id=appr.request_id,
                    severity="MEDIUM",
                    message=f"Access request denied by {user.name}: {body.reason}",
                    acknowledged=False,
                    sent_at=datetime.utcnow(),
                )
            )
            action = "approval.denied"
            logger.info(f"✓ Decision: DENIED for request {appr.request_id}")

        # Audit the approval decision
        logger.info("→ Writing audit event...")
        AuditService.write_event(
            db,
            entity_type="Approval",
            entity_id=appr.id,
            action=action,
            actor_id=user.id,
            data={
                "approved": body.approved,
                "reason": body.reason,
                "request_id": appr.request_id,
                "duration_minutes": body.duration_minutes if body.approved else None,
            },
        )

        db.commit()

        return {
            "approval_id": appr.id,
            "status": appr.status,
            "reason": appr.reason,
            "approved_at": appr.approved_at.isoformat() if appr.approved_at else None,
            "expires_at": appr.expires_at.isoformat() if appr.expires_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Exception in /approvals/decide")
        return {"error": str(e), "step": "decide_approval execution", "traceback": traceback.format_exc()}
