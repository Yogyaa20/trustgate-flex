"""
TrustGate Flex — Debug routes
"""

from __future__ import annotations

import logging
import traceback
import time
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi.routing import APIRoute

from backend.db.database import get_db
from backend.models.models import (
    User, Device, Asset, Project, AccessRequest, RiskFactor, Decision,
    AuditEvent, Alert, Approval
)

logger = logging.getLogger(__name__)
router = APIRouter()

START_TIME = time.time()


# ====================================================================
#  GET /debug/status
# ====================================================================
@router.get("/status")
def debug_status(request: Request, db: Session = Depends(get_db)):
    """Return system status, DB row counts, last audit hashes, uptime, routes."""
    logger.info("→ [GET /debug/status] called")
    try:
        # Check DB connection
        db.execute(text("SELECT 1"))
        db_status = "connected"
        
        # Row counts
        tables = {
            "users": db.query(User).count(),
            "devices": db.query(Device).count(),
            "assets": db.query(Asset).count(),
            "projects": db.query(Project).count(),
            "access_requests": db.query(AccessRequest).count(),
            "risk_factors": db.query(RiskFactor).count(),
            "decisions": db.query(Decision).count(),
            "audit_events": db.query(AuditEvent).count(),
            "alerts": db.query(Alert).count(),
            "approvals": db.query(Approval).count(),
        }

        # Last 3 audit events
        last_events = (
            db.query(AuditEvent)
            .order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc())
            .limit(3)
            .all()
        )
        audit_hashes = [{"id": e.id, "hash": e.event_hash} for e in last_events]

        # Uptime
        uptime_seconds = int(time.time() - START_TIME)

        # Routes list
        routes = []
        for route in request.app.routes:
            if hasattr(route, "methods"):
                routes.append(f"{','.join(route.methods)} {route.path}")

        return {
            "database_connection": db_status,
            "table_counts": tables,
            "last_3_audit_hashes": audit_hashes,
            "uptime_seconds": uptime_seconds,
            "routes": routes,
        }
    except Exception as e:
        logger.exception("Exception in /debug/status")
        return {"error": str(e), "step": "debug_status execution", "traceback": traceback.format_exc()}


# ====================================================================
#  GET /debug/test-pipeline
# ====================================================================
@router.get("/test-pipeline")
def test_pipeline(db: Session = Depends(get_db)):
    """Runs a complete test access request using Alice's seeded data and returns intermediates."""
    logger.info("→ [GET /debug/test-pipeline] called")
    try:
        from backend.api.routes.access import _run_pipeline, AccessRequestBody
        
        logger.info("→ Loading user Alice...")
        user = db.query(User).filter(User.name.like("Alice%")).first()
        if not user:
            return {"error": "Alice not found in DB. Did you seed?"}

        logger.info("→ Loading Alice's device...")
        device = db.query(Device).filter(Device.user_id == user.id).first()
        if not device:
            return {"error": "Alice's device not found."}

        logger.info("→ Loading an asset...")
        asset = db.query(Asset).first()
        if not asset:
            return {"error": "No assets found."}

        req_body = AccessRequestBody(
            asset_id=asset.id,
            device_id=device.id,
            request_type="READ",
            location_hash="office-hq"
        )
        
        logger.info("→ Running pipeline...")
        result = _run_pipeline(user, device, asset, req_body, db)
        
        # Rollback so we don't pollute the DB with test requests, or commit?
        # The prompt says "DB writes" so we should commit.
        db.commit()

        logger.info("✓ Pipeline execution complete")
        return {
            "status": "success",
            "context_built": "Loaded Alice, device, asset",
            "risk_score": result["risk_score"],
            "policy_decision": result["decision"],
            "db_writes": "AccessRequest, Decision, RiskFactors, AuditEvent saved",
            "result": result
        }

    except Exception as e:
        logger.exception("Exception in /debug/test-pipeline")
        return {"error": str(e), "step": "test_pipeline execution", "traceback": traceback.format_exc()}
