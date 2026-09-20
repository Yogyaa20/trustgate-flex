#!/usr/bin/env python3
"""
TrustGate Flex — Database Seeder
Seeds the SQLite database with realistic demo data for dashboard testing.

Usage (from project root):
    python -m scripts.seed_db
"""

import hashlib
import json
import random
import sys
import os
from datetime import datetime, timedelta
from uuid import uuid4

# Ensure the project root is on sys.path so we can import backend.*
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.db.database import SessionLocal, create_all_tables
from backend.models.models import (
    AccessRequest,
    Alert,
    Approval,
    Asset,
    AuditEvent,
    Decision,
    Device,
    Project,
    RiskFactor,
    User,
)


# ── Deterministic seed for reproducibility ─────────────
random.seed(42)

NOW = datetime.utcnow()


def _id() -> str:
    return str(uuid4())


def _hash(val: str) -> str:
    return hashlib.sha256(val.encode()).hexdigest()


# ====================================================================
# 1. USERS  (8)
# ====================================================================
def seed_users(db):
    users_data = [
        {"name": "Alice Chen", "email": "alice.chen@trustgate.io", "role": "ENGINEER"},
        {"name": "Bob Martinez", "email": "bob.martinez@trustgate.io", "role": "ADMIN"},
        {"name": "David Park", "email": "david.park@trustgate.io", "role": "ENGINEER"},
        {"name": "Riya Sharma", "email": "riya.sharma@trustgate.io", "role": "ENGINEER"},
        {"name": "Jordan Lee", "email": "jordan.lee@trustgate.io", "role": "ADMIN"},
        {"name": "Contractor One", "email": "contractor1@external.io", "role": "CONTRACTOR"},
        {"name": "Auditor One", "email": "auditor1@compliance.io", "role": "AUDITOR"},
        {"name": "Admin One", "email": "admin1@trustgate.io", "role": "ADMIN"},
    ]
    users = []
    for u in users_data:
        user = User(
            id=_id(),
            name=u["name"],
            email=u["email"],
            role=u["role"],
            status="ACTIVE",
            baseline_download_rate=round(random.uniform(2.0, 8.0), 1),
            active_project_ids="[]",
            created_at=NOW - timedelta(days=random.randint(30, 365)),
        )
        users.append(user)
    db.add_all(users)
    db.flush()
    return users


# ====================================================================
# 2. PROJECTS  (4)
# ====================================================================
def seed_projects(db, users):
    projects_data = [
        {"name": "Project Alpha", "classification": "CONFIDENTIAL"},
        {"name": "Project Beta", "classification": "INTERNAL"},
        {"name": "Research Lab", "classification": "RESTRICTED"},
        {"name": "Infrastructure", "classification": "INTERNAL"},
    ]
    projects = []
    for p in projects_data:
        member_sample = random.sample(users, k=random.randint(2, 5))
        project = Project(
            id=_id(),
            name=p["name"],
            member_ids=json.dumps([u.id for u in member_sample]),
            classification=p["classification"],
            active=True,
        )
        projects.append(project)
    db.add_all(projects)
    db.flush()

    # Back-fill active_project_ids on users
    for user in users:
        user_projects = [p for p in projects if user.id in json.loads(p.member_ids)]
        user.active_project_ids = json.dumps([p.id for p in user_projects])

    return projects


# ====================================================================
# 3. DEVICES  (10)
# ====================================================================
def seed_devices(db, users):
    managed_configs = [
        {"trust": 95, "managed": True},
        {"trust": 90, "managed": True},
        {"trust": 88, "managed": True},
        {"trust": 85, "managed": True},
        {"trust": 82, "managed": True},
        {"trust": 78, "managed": True},
    ]
    unmanaged_configs = [
        {"trust": 42, "managed": False},
        {"trust": 38, "managed": False},
        {"trust": 35, "managed": False},
        {"trust": 28, "managed": False},
    ]
    all_configs = managed_configs + unmanaged_configs
    devices = []
    for i, cfg in enumerate(all_configs):
        owner = users[i % len(users)]
        device = Device(
            id=_id(),
            user_id=owner.id,
            device_hash=_hash(f"device-{i}-{owner.email}"),
            trust_score=cfg["trust"],
            is_managed=cfg["managed"],
            registered_at=NOW - timedelta(days=random.randint(10, 200)),
            last_seen=NOW - timedelta(minutes=random.randint(0, 1440)),
        )
        devices.append(device)
    db.add_all(devices)
    db.flush()
    return devices


# ====================================================================
# 4. ASSETS  (15)
# ====================================================================
def seed_assets(db, projects):
    assets_data = [
        # 3 PUBLIC
        {"name": "company-handbook.pdf", "classification": "PUBLIC", "sensitivity": 2},
        {"name": "onboarding-guide.docx", "classification": "PUBLIC", "sensitivity": 1},
        {"name": "public-api-spec.yaml", "classification": "PUBLIC", "sensitivity": 3},
        # 5 INTERNAL
        {"name": "quarterly-roadmap.pptx", "classification": "INTERNAL", "sensitivity": 6},
        {"name": "team-wiki-export.md", "classification": "INTERNAL", "sensitivity": 5},
        {"name": "ci-pipeline-config.yml", "classification": "INTERNAL", "sensitivity": 7},
        {"name": "staging-env-vars.env", "classification": "INTERNAL", "sensitivity": 8},
        {"name": "architecture-diagram.drawio", "classification": "INTERNAL", "sensitivity": 5},
        # 4 CONFIDENTIAL
        {"name": "customer-pii-export.csv", "classification": "CONFIDENTIAL", "sensitivity": 15},
        {"name": "financial-forecast-Q4.xlsx", "classification": "CONFIDENTIAL", "sensitivity": 14},
        {"name": "patent-draft-v3.docx", "classification": "CONFIDENTIAL", "sensitivity": 16},
        {"name": "security-audit-report.pdf", "classification": "CONFIDENTIAL", "sensitivity": 13},
        # 3 RESTRICTED
        {"name": "master-encryption-keys.pem", "classification": "RESTRICTED", "sensitivity": 20},
        {"name": "board-acquisition-plan.pdf", "classification": "RESTRICTED", "sensitivity": 19},
        {"name": "zero-day-vuln-details.md", "classification": "RESTRICTED", "sensitivity": 18},
    ]
    assets = []
    for a in assets_data:
        asset = Asset(
            id=_id(),
            name=a["name"],
            path_hash=_hash(f"/vault/{a['classification'].lower()}/{a['name']}"),
            classification=a["classification"],
            project_id=random.choice(projects).id,
            sensitivity_score=a["sensitivity"],
        )
        assets.append(asset)
    db.add_all(assets)
    db.flush()
    return assets


# ====================================================================
# 5. ACCESS REQUESTS + DECISIONS  (20)
# ====================================================================
REQUEST_TYPES = ["READ", "DOWNLOAD", "EXPORT"]
LOCATIONS = ["office-hq", "vpn-us-east", "vpn-eu-west", "home-wifi", "coffee-shop", "unknown"]

RISK_FACTOR_TEMPLATES = [
    {"name": "device_trust", "weight": 0.25},
    {"name": "asset_sensitivity", "weight": 0.20},
    {"name": "time_anomaly", "weight": 0.15},
    {"name": "location_risk", "weight": 0.15},
    {"name": "download_velocity", "weight": 0.10},
    {"name": "role_match", "weight": 0.15},
]

POLICIES = [
    "baseline-access-v2",
    "contractor-restricted-v1",
    "confidential-mfa-check",
    "restricted-escalation-v3",
    "time-window-policy",
]


def _make_decision(risk_score: int):
    """Map a composite risk score to a category and outcome."""
    if risk_score <= 25:
        return "LOW", "ALLOW", None
    elif risk_score <= 50:
        return "MEDIUM", "ALLOW", "log-enhanced"
    elif risk_score <= 70:
        return "HIGH", "ESCALATE", "require-mfa"
    elif risk_score <= 85:
        return "CRITICAL", "DENY", "alert-soc"
    else:
        return "BLOCK", "DENY", "lock-account"


def seed_access_requests(db, users, devices, assets):
    requests = []
    decisions = []
    risk_factors_all = []
    alerts_all = []
    approvals_all = []
    audit_events_all = []
    prev_hash = "GENESIS"  # Genesis hash

    # Managers for escalation approvals
    managers = [u for u in users if u.role == "ADMIN"]
    
    # Pre-generate and sort timestamps so the hash chain is chronological
    timestamps = sorted([NOW - timedelta(hours=random.randint(1, 720)) for _ in range(20)])

    for i in range(20):
        user = random.choice(users)
        user_devices = [d for d in devices if d.user_id == user.id]
        device = random.choice(user_devices) if user_devices else random.choice(devices)
        asset = random.choice(assets)
        req_type = random.choice(REQUEST_TYPES)
        ts = timestamps[i]

        req = AccessRequest(
            id=_id(),
            user_id=user.id,
            device_id=device.id,
            asset_id=asset.id,
            session_id=_id(),
            request_type=req_type,
            timestamp=ts,
            location_hash=_hash(random.choice(LOCATIONS)),
            approved_work_session=random.choice([True, True, True, False]),
        )
        requests.append(req)
        db.add(req)
        db.flush()

        # ── Risk Factors ───────────────────────────────
        total_contribution = 0.0
        for tmpl in RISK_FACTOR_TEMPLATES:
            norm = round(random.uniform(0.0, 1.0), 3)
            contrib = round(norm * tmpl["weight"] * 100, 2)
            total_contribution += contrib
            rf = RiskFactor(
                id=_id(),
                request_id=req.id,
                factor_name=tmpl["name"],
                raw_value=str(round(random.uniform(0, 100), 1)),
                normalized_score=norm,
                weight=tmpl["weight"],
                contribution=contrib,
            )
            risk_factors_all.append(rf)

        risk_score = min(100, max(0, int(total_contribution)))
        category, outcome, enforcement = _make_decision(risk_score)

        explanation_parts = [
            f"Risk score {risk_score}/100 → {category}.",
            f"Device trust: {device.trust_score}/100.",
            f"Asset classification: {asset.classification} (sensitivity {asset.sensitivity_score}/20).",
            f"Request type: {req_type}.",
        ]

        dec = Decision(
            id=_id(),
            request_id=req.id,
            risk_score=risk_score,
            risk_category=category,
            policy_applied=random.choice(POLICIES),
            outcome=outcome,
            enforcement_action=enforcement,
            explanation=" ".join(explanation_parts),
            latency_ms=random.randint(8, 145),
            decided_at=ts + timedelta(milliseconds=random.randint(10, 200)),
        )
        decisions.append(dec)

        # ── Alert for HIGH / CRITICAL / BLOCK ──────────
        if category in ("HIGH", "CRITICAL", "BLOCK"):
            alert = Alert(
                id=_id(),
                request_id=req.id,
                severity=category if category != "BLOCK" else "CRITICAL",
                message=f"Elevated risk ({risk_score}) for {req_type} on {asset.name} by {user.name}.",
                acknowledged=random.choice([True, False]),
                sent_at=ts + timedelta(seconds=1),
            )
            alerts_all.append(alert)

        # ── Approval for ESCALATE ──────────────────────
        if outcome == "ESCALATE" and managers:
            mgr = random.choice(managers)
            approval_status = random.choice(["APPROVED", "DENIED", "PENDING"])
            appr = Approval(
                id=_id(),
                request_id=req.id,
                manager_id=mgr.id,
                status=approval_status,
                reason=f"Escalation review for {asset.name} access." if approval_status != "PENDING" else None,
                expires_at=ts + timedelta(hours=4),
                approved_at=(ts + timedelta(minutes=random.randint(5, 60))) if approval_status == "APPROVED" else None,
            )
            approvals_all.append(appr)

        # ── Audit Event ────────────────────────────────
        event_data = {
            "user": user.name,
            "asset": asset.name,
            "outcome": outcome,
            "risk_score": risk_score,
        }
        event_payload = json.dumps(event_data, sort_keys=True)
        action_str = f"access.{outcome.lower()}"
        hash_input = (
            f"AccessRequest{req.id}{action_str}"
            f"{ts.isoformat()}{event_payload}{prev_hash}"
        )
        event_hash = _hash(hash_input)
        audit = AuditEvent(
            id=_id(),
            entity_type="AccessRequest",
            entity_id=req.id,
            action=action_str,
            actor_id=user.id,
            data_json=event_payload,
            timestamp=ts,
            event_hash=event_hash,
            prev_hash=prev_hash,
        )
        audit_events_all.append(audit)
        prev_hash = event_hash

    db.add_all(risk_factors_all)
    db.add_all(decisions)
    db.add_all(alerts_all)
    db.add_all(approvals_all)
    db.add_all(audit_events_all)
    db.flush()

    return requests, decisions, alerts_all, approvals_all, audit_events_all


# ====================================================================
# MAIN
# ====================================================================
def main():
    print("╔══════════════════════════════════════════════════╗")
    print("║       TrustGate Flex — Database Seeder           ║")
    print("╚══════════════════════════════════════════════════╝")
    print()

    # 1. Handle --reset flag
    if "--reset" in sys.argv:
        print("▸ Dropping existing tables (--reset flag detected) …")
        import backend.models.models
        from backend.db.database import Base, engine
        Base.metadata.drop_all(bind=engine)
        
    # 2. Create tables
    print("▸ Creating tables …")
    create_all_tables()

    db = SessionLocal()
    try:
        # 2. Seed users
        print("▸ Seeding users …")
        users = seed_users(db)

        # 3. Seed projects
        print("▸ Seeding projects …")
        projects = seed_projects(db, users)

        # 4. Seed devices
        print("▸ Seeding devices …")
        devices = seed_devices(db, users)

        # 5. Seed assets
        print("▸ Seeding assets …")
        assets = seed_assets(db, projects)

        # 6. Seed access requests + decisions + alerts + approvals + audit events
        print("▸ Seeding access requests & decisions …")
        reqs, decs, alerts, approvals, audits = seed_access_requests(
            db, users, devices, assets
        )

        db.commit()
        print()
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("  ✔  SEED COMPLETE — Summary")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"   Users            : {len(users)}")
        print(f"   Projects         : {len(projects)}")
        print(f"   Devices          : {len(devices)}")
        print(f"   Assets           : {len(assets)}")
        print(f"   Access Requests  : {len(reqs)}")
        print(f"   Decisions        : {len(decs)}")
        print(f"   Risk Factors     : {len(reqs) * 6}")
        print(f"   Alerts           : {len(alerts)}")
        print(f"   Approvals        : {len(approvals)}")
        print(f"   Audit Events     : {len(audits)}")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        # Quick outcome breakdown
        outcomes = {}
        for d in decs:
            outcomes[d.outcome] = outcomes.get(d.outcome, 0) + 1
        print()
        print("  Decision Outcomes:")
        for outcome, count in sorted(outcomes.items()):
            print(f"    {outcome:12s} → {count}")

        categories = {}
        for d in decs:
            categories[d.risk_category] = categories.get(d.risk_category, 0) + 1
        print()
        print("  Risk Categories:")
        for cat, count in sorted(categories.items()):
            print(f"    {cat:12s} → {count}")
        print()

    except Exception as e:
        db.rollback()
        print(f"\n✘ Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
