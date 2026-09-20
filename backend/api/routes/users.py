from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.core.security import require_roles
from backend.db.database import get_db
from backend.models.models import User
from backend.services.audit_service import AuditService
from datetime import datetime
import logging, traceback
from uuid import uuid4

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["users"])

@router.post("/{user_id}/revoke")
def revoke_user(
    user_id: str,
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.status = "REVOKED"
    AuditService.write_event(db, "User", user.id, "USER_REVOKED", current_user.id, {"name": user.name})
    db.commit()
    return {"user_name": user.name, "user_id": user.id, "status": "REVOKED", "revoked_at": datetime.utcnow().isoformat()}

@router.get("")
def list_users(
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db)
):
    users = db.query(User).all()
    return [{"id": u.id, "name": u.name, "role": u.role, "status": u.status, "email": u.email} for u in users]
