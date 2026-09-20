"""
TrustGate Flex — Assets Route
"""
from __future__ import annotations

import logging
import traceback
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.models.models import Asset

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("")
def list_assets(db: Session = Depends(get_db)):
    """List all assets (no auth required for demo)."""
    logger.info("→ [GET /assets] called")
    try:
        assets = db.query(Asset).all()
        return [
            {
                "id": a.id,
                "name": a.name,
                "classification": a.classification,
                "project_id": a.project_id,
                "sensitivity_score": a.sensitivity_score,
            }
            for a in assets
        ]
    except Exception as e:
        logger.exception("Exception in /assets")
        return {"error": str(e), "step": "list_assets", "traceback": traceback.format_exc()}


@router.get("/{asset_id}")
def get_asset(asset_id: str, db: Session = Depends(get_db)):
    """Get a single asset."""
    logger.info(f"→ [GET /assets/{asset_id}] called")
    try:
        asset = db.query(Asset).filter(Asset.id == asset_id).first()
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        return {
            "id": asset.id,
            "name": asset.name,
            "classification": asset.classification,
            "project_id": asset.project_id,
            "sensitivity_score": asset.sensitivity_score,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Exception in /assets/{asset_id}")
        return {"error": str(e), "step": "get_asset", "traceback": traceback.format_exc()}
