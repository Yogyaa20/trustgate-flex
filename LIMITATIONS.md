# Known Limitations

This is a hackathon prototype. The following limitations are acknowledged honestly.

## Data

- All users, devices, assets, and access events are **synthetic**
- Download velocity baselines are manually assigned, not learned from real history
- Location anomaly uses synthetic hashes, not real geolocation
- Device trust scores are simulated — no real MDM integration

## Risk Engine

- Rules-based, not machine-learned — weights are manually tuned
- No adaptive baseline — production would require 30+ days of real access history per user
- VPN or proxy can mask location anomaly (location carries only 10/100 points)
- Device trust score changes between requests but is not pushed from a real MDM

## Infrastructure

- SQLite is not suitable for production load or concurrent writes
- No TLS in local development — production requires HTTPS everywhere
- No rate limiting on the login endpoint
- Blockchain anchor is not implemented in this version (SHA-256 hash chain is used instead)

## Coverage

- Does not protect against network-layer attacks or malware
- Does not integrate with real MDM, LDAP, SSO, or SIEM
- File sandbox is a logical simulation — no real file I/O enforcement
- Does not detect zero-day exploits or credential theft at the network level

## Claims We Do NOT Make

- This is not a production-ready product
- This does not catch all insider threats
- This does not replace enterprise IAM, DLP, or SIEM
- This has not been evaluated on real-world datasets
- The risk weights have not been validated against historical breach data

## What Would Be Needed for Production

1. MDM integration for real device trust scores (Jamf, Intune)
2. 30-day baseline learning period per user
3. PostgreSQL with read replicas for concurrent load
4. Real file storage integration (S3, SharePoint, Google Drive)
5. LDAP/SSO integration for identity
6. Formal security audit and penetration testing
7. Privacy Impact Assessment and legal review
8. Employee disclosure and consent process
