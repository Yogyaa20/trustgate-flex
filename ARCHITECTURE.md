# Architecture

## Overview

TrustGate Flex is a five-layer deterministic system. Every access request flows through all five layers in sequence. No layer skips, no shortcuts.

```
┌─────────────────────────────────────────┐
│           Streamlit Frontend            │
│   Login │ Dashboard │ Access Request    │
│   Decision Result │ Replay │ Simulator  │
└────────────────┬────────────────────────┘
                 │ HTTP / REST
┌────────────────▼────────────────────────┐
│           FastAPI Backend               │
│   /auth  /access  /approvals  /audit    │
│   /alerts  /appeals  /users  /debug     │
└────────────────┬────────────────────────┘
                 │
        ┌────────▼────────┐
        │ Context Engine  │  ← 11 signals collected here
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │  Risk Engine    │  ← Weighted formula → 0-100 score
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │ Policy Engine   │  ← P01-P10 rules → named decision
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │  Enforcement    │  ← Allow / block / throttle
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │  Audit Service  │  ← SHA-256 hash chain
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │  SQLite (dev)   │  ← All state persisted here
        │  PostgreSQL     │  ← Production target
        └─────────────────┘
```

## Request Lifecycle

Every file access request follows this exact sequence:

```
1. Identity Check
   ├── Is user active? (ACTIVE / SUSPENDED / REVOKED)
   └── Is JWT valid and not expired?

2. Context Collection (11 signals)
   ├── device.trust_score
   ├── asset.classification + asset.project_id
   ├── user.active_project_ids (project assignment check)
   ├── COUNT(access_requests last 5 min) → download velocity
   ├── request.location_hash vs known_locations
   ├── failed_mfa_attempts + is_new_ip → auth anomaly
   ├── concurrent_sessions + rapid_switches → session anomaly
   ├── user.status
   ├── temporary_permission_active
   ├── session.approved_work_session
   └── COUNT(violations last 24h) → repeat violations

3. Risk Engine
   ├── Each signal → normalized contribution
   ├── Sum all contributions
   ├── Clamp to 0-100
   └── Assign category: LOW / MEDIUM / HIGH / CRITICAL / BLOCK

4. Policy Engine (first match wins, evaluated in order)
   ├── P01: REVOKED/SUSPENDED → BLOCK_AND_ALERT
   ├── P02: RESTRICTED + trust<70 → STEP_UP_AUTH
   ├── P03: Unassigned CONFIDENTIAL/RESTRICTED → MANAGER_APPROVAL
   ├── P04: Velocity >2x baseline → RATE_LIMIT_AND_ALERT
   ├── P05: Approved session + trusted + assigned → ALLOW_WITH_MONITOR
   ├── P06: score 0-29 → ALLOW
   ├── P07: score 30-49 → ALLOW_WITH_MONITOR
   ├── P08: score 50-69 → STEP_UP_AUTH
   ├── P09: score 70-84 → MANAGER_APPROVAL
   └── P10: score 85-100 → BLOCK_AND_ALERT

5. Enforcement
   ├── ALLOW → file served
   ├── ALLOW_WITH_MONITOR → file served, session flagged
   ├── STEP_UP_AUTH → blocked pending MFA
   ├── MANAGER_APPROVAL → blocked, approval record created
   ├── RATE_LIMIT_AND_ALERT → throttled to baseline rate, alert created
   └── BLOCK_AND_ALERT → denied, high-severity alert created

6. Audit Write
   ├── AuditEvent created with full decision data
   ├── prev_hash = last event's event_hash
   ├── event_hash = SHA-256(entity + action + timestamp + data + prev_hash)
   └── Append-only — never updated or deleted

7. Response
   └── request_id, risk_score, risk_category, decision,
       enforcement_action, policy_applied, explanation,
       factors[], requires_approval, approval_id, audit_event_id, latency_ms
```

## Component Responsibilities

| Component | Does | Does NOT |
|-----------|------|----------|
| Context Engine | Gathers 11 signals from DB and request | Make any decision |
| Risk Engine | Computes 0-100 score with factor breakdown | Enforce or block |
| Policy Engine (PDP) | Maps score + context to named decision | Execute file operations |
| Enforcement Point (PEP) | Allows, blocks, or throttles | Change policy rules |
| Audit Service | Writes append-only events with SHA-256 | Delete or modify records |
| Decision Replay API | Returns full record for any past event | Modify past decisions |

## Key Design Decisions

**Rules-based, not ML-based**
The risk engine is a transparent weighted formula. Every signal is named, every weight is published, every decision is explainable. A black-box ML model is inappropriate for access control without a large labelled dataset and formal evaluation.

**Time-of-day = zero weight**
Night work is not a risk signal. This is a formal constraint in the engine, not a configuration option. It cannot be accidentally enabled.

**Fairness before enforcement**
Policy P05 explicitly reduces risk for users with approved work sessions, ensuring that legitimate flexible workers are protected from false positives before the score-based rules fire.

**Append-only audit**
The application never issues UPDATE or DELETE on the AuditEvent table. The SHA-256 chain means any modification after the fact is detectable by recomputing the chain.

**Human override always available**
No automated decision is final. Every BLOCK can be appealed. Every MANAGER_APPROVAL can be granted or denied by a human. The system supports human judgment — it does not replace it.

## Data Model Summary

```
User ──────────────── Device (many)
  │                      │
  │                   AccessRequest ─── RiskFactor (11 per request)
  │                      │
  │                   Decision ─────── Approval (if MANAGER_APPROVAL)
  │                      │
  │                   AuditEvent ───── BlockchainAnchor (optional)
  │
Asset ─── Project
  │
Alert (created for BLOCK/RATE_LIMIT decisions)
Appeal (created when user contests a decision)
```
