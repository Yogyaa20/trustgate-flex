"""
TrustGate Flex — Appeals routes
Allows users to appeal access denials (e.g., false positives).
"""

from __future__ import annotations

import logging
import traceback
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core.security import get_current_user, require_roles
from backend.db.database import get_db
from backend.models.models import Appeal, Decision, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/appeals", tags=["appeals"])


class CreateAppealBody(BaseModel):
    decision_id: str
    reason: str


# ====================================================================
#  POST /appeals
# ====================================================================
@router.post("")
def submit_appeal(
    body: CreateAppealBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit an appeal for a blocked or rate-limited decision."""
    logger.info("→ [POST /appeals] called")
    try:
        decision = db.query(Decision).filter(Decision.id == body.decision_id).first()
        if not decision:
            raise HTTPException(status_code=404, detail="Decision not found")

        # Ensure appeal doesn't already exist
        existing = db.query(Appeal).filter(Appeal.decision_id == body.decision_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Appeal already submitted")

        appeal = Appeal(
            id=str(uuid4()),
            decision_id=body.decision_id,
            user_id=user.id,
            reason=body.reason,
            status="PENDING",
        )
        logger.info(f"→ Saving to DB: Appeal for decision {body.decision_id}")
        db.add(appeal)
        db.commit()

        return {
            "appeal_id": appeal.id,
            "status": appeal.status,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Exception in /appeals")
        return {"error": str(e), "step": "submit_appeal execution", "traceback": traceback.format_exc()}


# ====================================================================
#  GET /appeals
# ====================================================================
@router.get("")
def list_appeals(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
):
    """List appeals submitted by users."""
    logger.info("→ [GET /appeals] called")
    try:
        rows = (
            db.query(Appeal)
            .order_by(Appeal.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        results = []
        for a in rows:
            u = db.query(User).filter(User.id == a.user_id).first()
            results.append(
                {
                    "appeal_id": a.id,
                    "decision_id": a.decision_id,
                    "user_name": u.name if u else "Unknown",
                    "reason": a.reason,
                    "status": a.status,
                    "resolution": a.resolution,
                    "created_at": a.created_at.isoformat(),
                }
            )

        return {"total": len(results), "appeals": results}
    except Exception as e:
        logger.exception("Exception in /appeals list")
        return {"error": str(e), "step": "list_appeals execution", "traceback": traceback.format_exc()}
