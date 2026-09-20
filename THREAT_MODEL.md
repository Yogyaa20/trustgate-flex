# Threat Model

## In Scope

TrustGate Flex is designed to address these specific threats:

| Threat | Description | How TrustGate Addresses It |
|--------|-------------|---------------------------|
| Bulk exfiltration | Valid user bulk-downloading before offboarding | Velocity detection (P04) — throttles at 2x baseline |
| Compromised account | Attacker with stolen credentials accessing files | Device trust + location anomaly + session anomaly signals |
| Departing employee | Employee downloading IP before resignation | Combined velocity + project assignment checks |
| Unmanaged device | Corporate files accessed from personal laptop | Device trust score check (P02 for restricted assets) |
| Contractor over-reach | Contractor accessing files outside their scope | Project assignment check (P03) |
| Revoked user | Offboarded employee attempting access | Hard block P01 — fires before any risk scoring |
| Off-project access | Valid user accessing files from another team | Project assignment signal + P03 policy |

## Out of Scope

TrustGate Flex does NOT protect against:

- Network-level attacks (MITM, DDoS, packet injection)
- Malware, ransomware, or zero-day exploits
- Physical access to hardware
- Supply chain attacks
- Social engineering attacks
- Attacks against the TrustGate infrastructure itself
- Credential theft at the phishing or keylogging level
- Insider threats that operate within normal velocity and device patterns

## Assumptions

- The FastAPI backend and database are not publicly exposed
- The file sandbox directory has OS-level access controls
- JWT signing keys are rotated regularly in production
- The audit log is monitored by a human administrator
- Users have been onboarded and their baselines established

## Risk Signal Weaknesses

| Signal | Weakness | Mitigation |
|--------|---------|------------|
| Location hash | VPN can spoof location | Location carries only 10/100 points — not decisive alone |
| Device trust | Self-reported in prototype | Production: integrate with MDM (Jamf, Intune) |
| Download velocity | Baseline is fixed in prototype | Production: 30-day rolling baseline per user |
| Project assignment | Based on DB records | Production: sync with HRMS/identity provider |

## Policy Priority Order

Policies are evaluated in this order — first match wins:

1. **P01** — Revoked/suspended user → immediate hard block (no score needed)
2. **P02** — RESTRICTED asset + untrusted device → step-up auth
3. **P03** — Unassigned CONFIDENTIAL/RESTRICTED asset → manager approval
4. **P04** — Bulk download velocity → rate limit and alert
5. **P05** — Approved work session → allow with monitor
6. **P06-P10** — Score-based decisions (0→ALLOW through 85+→BLOCK)
