"""
TrustGate Flex — Auth routes
Prototype login: any seeded user email + password "demo123".
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core.security import create_access_token
from backend.db.database import get_db
from backend.models.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

DEMO_PASSWORD = "demo123"


class LoginBody(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


@router.post("/login")
def login(body: LoginBody, db: Session = Depends(get_db)):
    """
    Prototype login — accepts any seeded user email with password "demo123".
    """
    logger.info("→ [POST /auth/login] called")
    try:
        logger.info(f"→ Attempting login for user: {body.username}")
        if body.password != DEMO_PASSWORD:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user = db.query(User).filter(User.email == body.username).first()
        if not user:
            # Fuzzy match to handle "alice@trustgate.com" matching "alice.chen@trustgate.io"
            prefix = body.username.split('@')[0].split('.')[0]
            user = db.query(User).filter(User.email.ilike(f"%{prefix}%")).first()
            
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        logger.info("→ User loaded successfully. Generating token...")
        token = create_access_token(data={"sub": user.id, "role": user.role})
        
        logger.info(f"✓ Login successful for {user.email}")
        return LoginResponse(
            access_token=token,
            user={
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user.role,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Exception in /auth/login")
        return {"error": str(e), "step": "login execution", "traceback": str(e.__traceback__)}
