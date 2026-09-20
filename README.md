# TrustGate Flex

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35-red)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Track](https://img.shields.io/badge/Track-Cybersecurity-purple)](.)

**Team:** AVOCODER | **Developer:** Yogya Midha | **Track:** Cybersecurity | **Hackathon:** BuildForge

> Explainable just-in-time access gateway for confidential file protection.

---

## The Problem

A valid employee with valid credentials during an active session can silently download every confidential file the organisation owns — and static access control cannot stop it.

Static RBAC grants access at login and never re-evaluates. By the time a SIEM fires an alert, the files are already gone. Enterprise solutions (Varonis, DTEX, Microsoft Purview) solve this — but cost $50K+/year, require dedicated analysts, and take months to deploy. Nothing in the mid-market does context-aware, just-in-time access with an explainable audit trail.

---

## The Solution

TrustGate Flex intercepts every confidential file request and evaluates it against **11 real-time context signals** — device trust, download velocity, project assignment, location anomaly, session behaviour — producing an explainable 0–100 risk score and one of **8 graduated enforcement decisions** in **under 200ms**.

Every decision is **replayable**: click any past event and see the exact user, device, asset, risk factors, policy applied, and enforcement action. Not a number. A story.

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Access Decision Replay** | Click any past decision — full human-readable record. No competitor offers this. |
| **Fairness by Design** | Time-of-day carries zero weight. Night workers are never penalised. |
| **Transparent Scoring** | 11 named signals, published weights, visible breakdown per decision. |
| **Human-in-the-Loop** | High-risk decisions route to manager approval before access is granted. |
| **Tamper-Evident Audit** | SHA-256 hash chain on every event. |
| **Policy Simulator** | Drag sliders to explore how any combination of signals affects the decision — live. |
| **Bulk Download Detection** | Velocity anomaly triggers rate-limiting before exfiltration completes. |
| **Offboarding Simulation** | Revoke a user — their next request is hard-blocked by P01 instantly. |

---

## The 8 Decisions

```
ALLOW → ALLOW_WITH_MONITOR → READ_ONLY → STEP_UP_AUTH
→ MANAGER_APPROVAL → TEMPORARY_ACCESS → RATE_LIMIT_AND_ALERT → BLOCK_AND_ALERT
```

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/Yogyaa20/trustgate-flex
cd trustgate-flex

# 2. Environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env and set SECRET_KEY=any-random-string

# 4. Seed database
python scripts/seed_db.py

# 5. Start backend (terminal 1)
./run.sh

# 6. Start frontend (terminal 2)
streamlit run frontend/app.py
```

Open:
- **App:** http://localhost:8501
- **API Docs:** http://localhost:8000/docs
- **Health check:** http://localhost:8000/health

---

## Demo Accounts

| Name | Email | Role | Use for |
|------|-------|------|---------|
| Alice Chen | alice.chen@trustgate.io | ENGINEER | Normal access demos |
| Bob Martinez | bob.martinez@trustgate.io | ADMIN | Manager approval, offboarding |
| David Park | david.park@trustgate.io | ENGINEER | Bulk download demo |
| Admin One | admin1@trustgate.io | ADMIN | Full admin access |

All accounts use password: `demo123`

---

## Demo Scenarios

Navigate to **Request Access** and scroll to **Demo Scenarios**:

| Demo | Scenario | Expected Result |
|------|----------|----------------|
| **A** | Normal access, trusted device | ALLOW or ALLOW_WITH_MONITOR |
| **B** | Same as A — proves night work = zero weight | Identical score to A |
| **C** | New unmanaged device + RESTRICTED asset | MANAGER_APPROVAL |
| **D** | 20 rapid downloads on CONFIDENTIAL asset | RATE_LIMIT_AND_ALERT — throttled |

---

## The 11 Risk Signals

| # | Signal | Max Points | Note |
|---|--------|-----------|------|
| 1 | Device trust score | 20 | From MDM trust rating |
| 2 | Asset sensitivity | 20 | RESTRICTED=20, CONFIDENTIAL=15 |
| 3 | Project assignment | 15 | Is asset in user's active projects? |
| 4 | Download velocity | 15 | vs. personal 30-day baseline |
| 5 | Location anomaly | 10 | Unknown location only |
| 6 | Auth anomaly | 8 | Failed MFA, new IP |
| 7 | Session anomaly | 7 | Concurrent sessions |
| 8 | User status | 5 | REVOKED/SUSPENDED |
| 9 | Temporary permission | -10 | Reduces score |
| 10 | Approved work session | -8 | Reduces score |
| 11 | Repeat violations | 8 | 3+ violations in 24h |

**Time-of-day: 0 points. Night work is never suspicious.**

---

## Architecture

```
Streamlit UI (port 8501)
        ↓
FastAPI Backend (port 8000)
        ↓
Context Collector (11 signals)
        ↓
Risk Engine (0-100 score, rules-based)
        ↓
Policy Engine (8 decisions, P01-P10)
        ↓
Enforcement Point (allow/block/throttle)
        ↓
Audit Service (SHA-256 hash chain)
        ↓
SQLite Database ← Decision Replay API
```

---

## Competitive Comparison

| Feature | Static RBAC | Enterprise UEBA | TrustGate Flex |
|---------|------------|-----------------|----------------|
| Re-evaluates during session | No | Yes | Yes |
| Explains every decision | No | No | Yes |
| Decision replay | No | No | Yes |
| Night worker fairness | No | No | Yes |
| Policy simulator | No | No | Yes |
| Affordable for small teams | Yes | No | Yes |
| Real-time enforcement | No | Partial | Yes |
| Human-in-the-loop | No | Partial | Yes |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI |
| Database | SQLite + SQLAlchemy |
| Frontend | Streamlit, Plotly |
| Auth | JWT (HS256) |
| Hashing | SHA-256 (hashlib) |
| Testing | pytest |

---

## Project Structure

```
trustgate-flex/
├── backend/
│   ├── api/routes/        # FastAPI endpoints
│   ├── services/          # Risk engine, policy engine, audit
│   ├── models/            # SQLAlchemy ORM models
│   └── main.py
├── frontend/
│   ├── app.py             # Login page
│   ├── pages/             # Dashboard, Access Request, Decision Replay...
│   └── utils.py
├── scripts/
│   └── seed_db.py
├── tests/
└── run.sh
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Limitations

This is a hackathon prototype. See [LIMITATIONS.md](LIMITATIONS.md) for full details.

- Uses synthetic data only
- SQLite not suitable for production load
- Device trust score is simulated
- No real MDM, LDAP, or SSO integration

---

## Ethics and Privacy

- No keystroke logging
- No screen recording
- No content scanning
- No psychological profiling
- Night work = zero risk weight
- False-positive appeals supported
- All blocks overridable by human manager

See [ETHICS.md](ETHICS.md) and [PRIVACY.md](PRIVACY.md).

---

## Documentation

| File | Contents |
|------|---------|
| [SECURITY.md](SECURITY.md) | Auth, authorization, known vulnerabilities |
| [PRIVACY.md](PRIVACY.md) | What data is collected and why |
| [THREAT_MODEL.md](THREAT_MODEL.md) | In-scope and out-of-scope threats |
| [LIMITATIONS.md](LIMITATIONS.md) | Honest prototype limitations |
| [ETHICS.md](ETHICS.md) | Fairness principles and privacy stance |

---

## License

MIT License

> PROTOTYPE ONLY. Synthetic data. Not production software.
