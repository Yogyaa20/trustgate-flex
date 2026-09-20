"""
TrustGate Flex — Audit Service
Append-only SHA-256 hash-chained audit log for tamper-evident event recording.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.models.models import AuditEvent


class AuditService:
    """Stateless audit service — all methods operate on the provided session."""

    @staticmethod
    def write_event(
        db: Session,
        entity_type: str,
        entity_id: str,
        action: str,
        actor_id: str | None,
        data: dict,
    ) -> AuditEvent:
        """
        Append a new event to the tamper-evident audit log.

        Hash formula:
          SHA-256( entity_type + entity_id + action + timestamp_iso
                   + json(data, sorted) + prev_hash )
        """
        # Previous hash (or genesis sentinel)
        last = (
            db.query(AuditEvent)
            .order_by(AuditEvent.timestamp.desc())
            .first()
        )
        prev_hash = last.event_hash if last else "GENESIS"

        timestamp = datetime.utcnow()
        data_json = json.dumps(data, sort_keys=True, default=str)

        hash_input = (
            f"{entity_type}{entity_id}{action}"
            f"{timestamp.isoformat()}{data_json}{prev_hash}"
        )
        event_hash = hashlib.sha256(hash_input.encode()).hexdigest()

        event = AuditEvent(
            id=str(uuid4()),
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_id=actor_id,
            data_json=data_json,
            timestamp=timestamp,
            event_hash=event_hash,
            prev_hash=prev_hash,
        )
        db.add(event)
        db.flush()
        return event

    # ── Chain verification ─────────────────────────────
    @staticmethod
    def verify_chain(db: Session) -> dict:
        """
        Walk the entire audit log in chronological order and verify
        that every prev_hash links to the preceding event_hash.

        Returns
        -------
        dict  {"valid": bool, "events_checked": int, "broken_at": str | None}
        """
        events = (
            db.query(AuditEvent)
            .order_by(AuditEvent.timestamp.asc(), AuditEvent.id.asc())
            .all()
        )
        if not events:
            return {"valid": True, "events_checked": 0, "broken_at": None}

        expected_prev = "GENESIS"
        for i, ev in enumerate(events):
            # Check prev_hash linkage
            if ev.prev_hash != expected_prev:
                return {
                    "valid": False,
                    "events_checked": i + 1,
                    "broken_at": ev.id,
                }
            # Recompute event hash
            hash_input = (
                f"{ev.entity_type}{ev.entity_id}{ev.action}"
                f"{ev.timestamp.isoformat()}{ev.data_json}{ev.prev_hash}"
            )
            recomputed = hashlib.sha256(hash_input.encode()).hexdigest()
            if ev.event_hash != recomputed:
                return {
                    "valid": False,
                    "events_checked": i + 1,
                    "broken_at": ev.id,
                }
            expected_prev = ev.event_hash

        return {"valid": True, "events_checked": len(events), "broken_at": None}

    # ── Single-event verification ──────────────────────
    @staticmethod
    def get_event_verified(db: Session, event_id: str) -> dict | None:
        """Return a single event dict with an extra ``hash_valid`` flag."""
        ev = db.query(AuditEvent).filter(AuditEvent.id == event_id).first()
        if not ev:
            return None

        hash_input = (
            f"{ev.entity_type}{ev.entity_id}{ev.action}"
            f"{ev.timestamp.isoformat()}{ev.data_json}{ev.prev_hash}"
        )
        recomputed = hashlib.sha256(hash_input.encode()).hexdigest()

        return {
            "id": ev.id,
            "entity_type": ev.entity_type,
            "entity_id": ev.entity_id,
            "action": ev.action,
            "actor_id": ev.actor_id,
            "data_json": ev.data_json,
            "timestamp": ev.timestamp.isoformat(),
            "event_hash": ev.event_hash,
            "prev_hash": ev.prev_hash,
            "hash_valid": ev.event_hash == recomputed,
        }
