"""
TrustGate Flex — Audit routes
Read-only access and cryptographic verification of the audit log.
"""

from __future__ import annotations

import logging
import traceback
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.core.security import require_roles, get_current_user
from backend.db.database import get_db
from backend.models.models import AuditEvent, User
from backend.services.audit_service import AuditService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/audit", tags=["audit"])


# ====================================================================
#  GET /audit/events
# ====================================================================
@router.get("/events")
def list_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List audit events in descending chronological order."""
    logger.info("→ [GET /audit/events] called")
    try:
        events = (
            db.query(AuditEvent)
            .order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        results = []
        for ev in events:
            actor = db.query(User).filter(User.id == ev.actor_id).first() if ev.actor_id else None
            results.append(
                {
                    "event_id": ev.id,
                    "timestamp": ev.timestamp.isoformat(),
                    "entity_type": ev.entity_type,
                    "entity_id": ev.entity_id,
                    "action": ev.action,
                    "actor_name": actor.name if actor else "System",
                    "event_hash": ev.event_hash,
                }
            )
        return {"total": len(results), "skip": skip, "limit": limit, "events": results}
    except Exception as e:
        logger.exception("Exception in /audit/events")
        return {"error": str(e), "step": "list_events execution", "traceback": traceback.format_exc()}


# ====================================================================
#  GET /audit/events/{event_id}
# ====================================================================
@router.get("/events/{event_id}")
def get_event(
    event_id: str,
    user: User = Depends(require_roles("ADMIN", "AUDITOR")),
    db: Session = Depends(get_db),
):
    """Retrieve a single audit event and perform localized hash verification."""
    logger.info(f"→ [GET /audit/events/{event_id}] called")
    try:
        event_dict = AuditService.get_event_verified(db, event_id)
        if not event_dict:
            raise HTTPException(status_code=404, detail="Audit event not found")
        return event_dict
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Exception in /audit/events/{event_id}")
        return {"error": str(e), "step": "get_event execution", "traceback": traceback.format_exc()}


# ====================================================================
#  GET /audit/verify
# ====================================================================
@router.get("/verify")
def verify_chain(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Verify the cryptographic integrity of the entire audit chain.
    Walks from GENESIS to the latest event checking all linkages.
    """
    logger.info("→ [GET /audit/verify] called")
    try:
        return AuditService.verify_chain(db)
    except Exception as e:
        logger.exception("Exception in /audit/verify")
        return {"error": str(e), "step": "verify_chain execution", "traceback": traceback.format_exc()}
