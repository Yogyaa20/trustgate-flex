"""
TrustGate Flex — SQLAlchemy ORM Models
All 12 core tables for the explainable JIT access gateway.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from backend.db.database import Base


# ── Helper ─────────────────────────────────────────────
def _uuid() -> str:
    """Generate a new UUID4 string for use as a primary key."""
    return str(uuid.uuid4())


# ── 1. User ────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(128), nullable=False)
    email = Column(String(256), unique=True, nullable=False)
    role = Column(
        String(20),
        nullable=False,
        comment="ENGINEER | RESEARCHER | CONTRACTOR | ADMIN | AUDITOR",
    )
    status = Column(
        String(20),
        nullable=False,
        default="ACTIVE",
        comment="ACTIVE | SUSPENDED | REVOKED",
    )
    baseline_download_rate = Column(Float, nullable=False, default=5.0)
    active_project_ids = Column(Text, nullable=True, comment="JSON array of project IDs")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    devices = relationship("Device", back_populates="user", cascade="all, delete-orphan")
    access_requests = relationship("AccessRequest", back_populates="user", foreign_keys="AccessRequest.user_id")
    approvals_given = relationship("Approval", back_populates="manager", foreign_keys="Approval.manager_id")
    appeals = relationship("Appeal", back_populates="user")

    def __repr__(self):
        return f"<User {self.name} ({self.role})>"


# ── 2. Device ──────────────────────────────────────────
class Device(Base):
    __tablename__ = "devices"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    device_hash = Column(String(64), nullable=False)
    trust_score = Column(Integer, nullable=False, default=70, comment="0-100")
    is_managed = Column(Boolean, nullable=False, default=True)
    registered_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_seen = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="devices")
    access_requests = relationship("AccessRequest", back_populates="device")

    def __repr__(self):
        return f"<Device {self.device_hash[:12]}… trust={self.trust_score}>"


# ── 3. Project ─────────────────────────────────────────
class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(128), nullable=False)
    member_ids = Column(Text, nullable=True, comment="JSON array of user IDs")
    classification = Column(
        String(20),
        nullable=False,
        comment="PUBLIC | INTERNAL | CONFIDENTIAL | RESTRICTED",
    )
    active = Column(Boolean, nullable=False, default=True)

    # Relationships
    assets = relationship("Asset", back_populates="project")

    def __repr__(self):
        return f"<Project {self.name}>"


# ── 4. Asset ───────────────────────────────────────────
class Asset(Base):
    __tablename__ = "assets"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(256), nullable=False)
    path_hash = Column(String(64), nullable=False)
    classification = Column(
        String(20),
        nullable=False,
        comment="PUBLIC | INTERNAL | CONFIDENTIAL | RESTRICTED",
    )
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    sensitivity_score = Column(Integer, nullable=False, default=0, comment="0-20")

    # Relationships
    project = relationship("Project", back_populates="assets")
    access_requests = relationship("AccessRequest", back_populates="asset")

    def __repr__(self):
        return f"<Asset {self.name} [{self.classification}]>"


# ── 5. AccessRequest ───────────────────────────────────
class AccessRequest(Base):
    __tablename__ = "access_requests"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    device_id = Column(String(36), ForeignKey("devices.id"), nullable=False)
    asset_id = Column(String(36), ForeignKey("assets.id"), nullable=False)
    session_id = Column(String(36), nullable=False, default=_uuid)
    request_type = Column(
        String(20),
        nullable=False,
        comment="READ | DOWNLOAD | EXPORT",
    )
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    location_hash = Column(String(64), nullable=True)
    approved_work_session = Column(Boolean, nullable=False, default=False)

    # Relationships
    user = relationship("User", back_populates="access_requests", foreign_keys=[user_id])
    device = relationship("Device", back_populates="access_requests")
    asset = relationship("Asset", back_populates="access_requests")
    risk_factors = relationship("RiskFactor", back_populates="request", cascade="all, delete-orphan")
    decision = relationship("Decision", back_populates="request", uselist=False)
    approval = relationship("Approval", back_populates="request", uselist=False)
    alert = relationship("Alert", back_populates="request", uselist=False)

    def __repr__(self):
        return f"<AccessRequest {self.request_type} by user={self.user_id[:8]}…>"


# ── 6. RiskFactor ──────────────────────────────────────
class RiskFactor(Base):
    __tablename__ = "risk_factors"

    id = Column(String(36), primary_key=True, default=_uuid)
    request_id = Column(String(36), ForeignKey("access_requests.id"), nullable=False)
    factor_name = Column(String(64), nullable=False)
    raw_value = Column(String(256), nullable=False)
    normalized_score = Column(Float, nullable=False)
    weight = Column(Float, nullable=False)
    contribution = Column(Float, nullable=False)

    # Relationships
    request = relationship("AccessRequest", back_populates="risk_factors")

    def __repr__(self):
        return f"<RiskFactor {self.factor_name}={self.normalized_score:.2f}>"


# ── 7. Decision ────────────────────────────────────────
class Decision(Base):
    __tablename__ = "decisions"

    id = Column(String(36), primary_key=True, default=_uuid)
    request_id = Column(
        String(36), ForeignKey("access_requests.id"), unique=True, nullable=False
    )
    risk_score = Column(Integer, nullable=False, comment="0-100 composite risk score")
    risk_category = Column(
        String(20),
        nullable=False,
        comment="LOW | MEDIUM | HIGH | CRITICAL | BLOCK",
    )
    policy_applied = Column(String(128), nullable=False)
    outcome = Column(String(20), nullable=False, comment="ALLOW | DENY | ESCALATE")
    enforcement_action = Column(String(64), nullable=True)
    explanation = Column(Text, nullable=False)
    latency_ms = Column(Integer, nullable=False, default=0)
    decided_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    request = relationship("AccessRequest", back_populates="decision")
    appeals = relationship("Appeal", back_populates="decision")

    def __repr__(self):
        return f"<Decision {self.outcome} risk={self.risk_score}>"


# ── 8. Approval ────────────────────────────────────────
class Approval(Base):
    __tablename__ = "approvals"

    id = Column(String(36), primary_key=True, default=_uuid)
    request_id = Column(String(36), ForeignKey("access_requests.id"), nullable=False)
    manager_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    status = Column(
        String(20),
        nullable=False,
        default="PENDING",
        comment="PENDING | APPROVED | DENIED",
    )
    reason = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)

    # Relationships
    request = relationship("AccessRequest", back_populates="approval")
    manager = relationship("User", back_populates="approvals_given", foreign_keys=[manager_id])

    def __repr__(self):
        return f"<Approval {self.status} by manager={self.manager_id[:8]}…>"


# ── 9. Alert ───────────────────────────────────────────
class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String(36), primary_key=True, default=_uuid)
    request_id = Column(String(36), ForeignKey("access_requests.id"), nullable=False)
    severity = Column(
        String(20),
        nullable=False,
        comment="LOW | MEDIUM | HIGH | CRITICAL",
    )
    message = Column(Text, nullable=False)
    acknowledged = Column(Boolean, nullable=False, default=False)
    sent_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    request = relationship("AccessRequest", back_populates="alert")

    def __repr__(self):
        return f"<Alert [{self.severity}] {self.message[:40]}…>"


# ── 10. AuditEvent ─────────────────────────────────────
class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True, default=_uuid)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(String(36), nullable=False)
    action = Column(String(64), nullable=False)
    actor_id = Column(String(36), nullable=True)
    data_json = Column(Text, nullable=True, comment="JSON payload")
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    event_hash = Column(String(64), nullable=False, comment="SHA-256")
    prev_hash = Column(String(64), nullable=True, comment="SHA-256 of previous event")

    # Relationships
    blockchain_anchor = relationship("BlockchainAnchor", back_populates="audit_event", uselist=False)

    def __repr__(self):
        return f"<AuditEvent {self.action} on {self.entity_type}>"


# ── 11. Appeal ─────────────────────────────────────────
class Appeal(Base):
    __tablename__ = "appeals"

    id = Column(String(36), primary_key=True, default=_uuid)
    decision_id = Column(String(36), ForeignKey("decisions.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(
        String(20),
        nullable=False,
        default="PENDING",
        comment="PENDING | RESOLVED",
    )
    resolution = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    decision = relationship("Decision", back_populates="appeals")
    user = relationship("User", back_populates="appeals")

    def __repr__(self):
        return f"<Appeal {self.status} for decision={self.decision_id[:8]}…>"


# ── 12. BlockchainAnchor ───────────────────────────────
class BlockchainAnchor(Base):
    __tablename__ = "blockchain_anchors"

    id = Column(String(36), primary_key=True, default=_uuid)
    audit_event_id = Column(
        String(36), ForeignKey("audit_events.id"), nullable=False
    )
    tx_hash = Column(String(66), nullable=True)
    block_number = Column(Integer, nullable=True)
    status = Column(
        String(20),
        nullable=False,
        default="PENDING",
        comment="PENDING | ANCHORED",
    )
    anchored_at = Column(DateTime, nullable=True)

    # Relationships
    audit_event = relationship("AuditEvent", back_populates="blockchain_anchor")

    def __repr__(self):
        return f"<BlockchainAnchor {self.status} tx={self.tx_hash}>"
