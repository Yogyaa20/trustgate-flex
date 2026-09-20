# TrustGate Flex — 5-Minute Demo Script

> BuildForge Hackathon | Cybersecurity Track | AVOCODER

---

## Prerequisites

```bash
# Terminal 1 — Backend
./run.sh

# Terminal 2 — Frontend
streamlit run frontend/app.py
```

Verify:
- Backend: http://localhost:8000/health → `{"status":"ok"}`
- Frontend: http://localhost:8501

---

## Demo A — Normal Access (0:00–0:45)

**Login as:** Alice Chen (alice@trustgate.com / demo123)

**Navigate to:** Request Access → scroll to Demo Scenarios

**Click:** "Demo A — Normal Access"

**Expected result:**
- Decision: ALLOW or ALLOW_WITH_MONITOR
- Risk Score: under 40
- Latency: under 200ms

**Say:**
> "This is a normal request by a trusted user on a managed device with an assigned project. TrustGate evaluates 11 signals and returns a decision in under 200 milliseconds. The score and every contributing factor are visible immediately."

**Navigate to:** Decision Result to show the gauge chart and factor breakdown.

---

## Demo B — Night Worker Fairness Proof (0:45–1:15)

**Click:** "Demo B — Night Worker (Fairness Proof)"

**Expected result:**
- Decision: identical to Demo A
- Risk Score: identical to Demo A
- Caption: "Night work = zero weight"

**Say:**
> "It is 2 AM. Same user, same device, same project, same velocity. Result: identical. Time-of-day carries zero weight in TrustGate Flex. We do not penalise flexible workers. This is not a policy choice — it is a formal design constraint coded into the risk engine from day one."

**Key point for judges:** This directly addresses the fairness gap in existing tools.

---

## Demo C — New Device + Restricted Asset (1:15–2:30)

**Click:** "Demo C — New Device + Restricted Asset"

**Expected result:**
- Decision: MANAGER_APPROVAL
- Risk Score: 50–70
- Policy fired: P02 or P03

**Say:**
> "Alice is now on a personal laptop — unmanaged, trust score 35. She is requesting a RESTRICTED asset. Risk score climbs. TrustGate does not block her — it escalates. The request is held pending manager approval."

**Navigate to:** Manager Approval (log in as Bob Martinez)

**Click:** Approve → select 30 minutes → confirm

**Say:**
> "Bob approves the request for 30 minutes. Alice gets time-limited access. Both events are written to the audit log with SHA-256 hashes. The full record is replayable."

---

## Demo D — Bulk Exfiltration Attempt (2:30–3:15)

**Still on Access Request page**

**Click:** "Demo D — Bulk Exfiltration (David Park)"

**Expected result:**
- "Throttled at file X of 20"
- Decision: RATE_LIMIT_AND_ALERT
- Risk Score: 30+
- Policy fired: P04

**Say:**
> "David has valid credentials and a trusted managed device. But he downloads 20 CONFIDENTIAL files in rapid succession — far above his normal rate. TrustGate detects the velocity anomaly. P04 fires. Downloads are throttled before the exfiltration completes. An alert is created. No malware needed to trigger this — it is pure behavioural detection."

---

## Demo E — Decision Replay (3:15–4:00)

**Navigate to:** Decision Replay

**Select:** the Demo D event from the dropdown

**Walk through the 7 sections:**
1. User — name, role, ACTIVE status
2. Device — trust score progress bar, Managed badge
3. Asset — classification, project
4. Risk Evaluation — score, all 11 factors table
5. Policy Decision — P04, RATE_LIMIT_AND_ALERT, reason text
6. Audit Record — SHA-256 hash in monospace

**Click:** "Verify Hash Chain"

**Expected result:** "Chain verified — N events checked" in green

**Say:**
> "This is the feature no competitor offers. Click any past access event — allowed, blocked, or challenged — and see the complete record. Every factor, every weight, every enforcement action. Not a number. A story. And every event is SHA-256 hashed and chained. Tamper with any field and the chain breaks."

---

## Demo F — Policy Simulator (4:00–4:45)

**Navigate to:** Policy Simulator

**Starting position:** Device trust=85, INTERNAL asset, project assigned → ALLOW

**Move:** Device trust slider to 10

**Expected result:** Score jumps, decision escalates to BLOCK or MANAGER_APPROVAL

**Move:** Asset classification to RESTRICTED

**Expected result:** Score increases further

**Move:** User status to REVOKED

**Expected result:** Decision immediately becomes BLOCK_AND_ALERT, policy P01

**Say:**
> "Any administrator can open the Policy Simulator and explore how the risk engine responds to different combinations of signals — live, with no real access granted. Drag device trust to 10, switch the asset to RESTRICTED, mark the user as REVOKED — watch P01 fire immediately. This is what transparent, explainable security looks like."

---

## Demo G — Offboarding (4:45–5:00)

**Navigate to:** Dashboard → scroll to Insider Threat Simulation

**Select:** a user from the dropdown

**Click:** Revoke Access

**Say:**
> "The moment an employee is offboarded, their next access attempt is hard-blocked by P01 — regardless of risk score, regardless of device, regardless of credentials. Static RBAC cannot do this mid-session. TrustGate can."

---

## Recovery Steps

If any API call fails during recording:

```bash
# Reset demo data
curl -X POST http://localhost:8000/demo/reset

# Or from the login page — click "Reset Demo Data"
```

If backend crashes:
```bash
./run.sh
```

If frontend crashes:
```bash
streamlit run frontend/app.py
```

All demo results are also reproducible by clicking the demo buttons again — no fixture files needed.

---

## Key Messages for Judges

1. **"We built a gateway that stops threats — not a dashboard that logs them after."**
2. **"Night work carries zero weight. The first system in this space with a formal fairness constraint."**
3. **"Click any decision and see exactly why. Not a number. A story."**
4. **"Built for the 5–50 person team that DTEX and Varonis have never served."**
5. **"Rules-based, not black-box. Any administrator can read the formula and explain any decision to HR or legal."**
