"""
TrustGate Flex — Devices Route
"""
from __future__ import annotations

import logging
import traceback
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.security import get_current_user
from backend.db.database import get_db
from backend.models.models import Device, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("/my")
def list_my_devices(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List devices belonging to the current authenticated user."""
    logger.info("→ [GET /devices/my] called")
    try:
        devices = db.query(Device).filter(Device.user_id == user.id).all()
        return [
            {
                "id": d.id,
                "device_hash": d.device_hash,
                "trust_score": d.trust_score,
                "is_managed": d.is_managed,
                "last_seen": d.last_seen.isoformat() if d.last_seen else None,
            }
            for d in devices
        ]
    except Exception as e:
        logger.exception("Exception in /devices/my")
        return {"error": str(e), "step": "list_my_devices", "traceback": traceback.format_exc()}
