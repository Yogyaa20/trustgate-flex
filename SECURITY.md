# Security Policy

> This is a hackathon prototype using synthetic data. It is NOT intended for production deployment.

## Authentication

- All API endpoints require a valid JWT (HS256, 1-hour expiry)
- Login via `POST /auth/login` returns a signed token
- No real passwords are stored — prototype uses a fixed demo password for all synthetic users
- JWT secret is loaded from `.env` — never committed to the repository

## Authorisation

Role-based access control with four roles:

| Role | Permissions |
|------|-------------|
| ENGINEER | Submit access requests, view own decisions |
| MANAGER | All ENGINEER permissions + approve/deny pending requests |
| ADMIN | Full access including user management and audit log |
| AUDITOR | Read-only access to audit log and decision replay |

## Data

- All users, assets, devices, and files are **synthetic**
- No real personal data is stored or processed
- Asset hashes use SHA-256 (hashlib — no external dependency)
- Audit log is append-only at the application level

## Audit Integrity

- Every access decision writes an `AuditEvent` with a SHA-256 hash
- Each event stores the hash of the previous event (`prev_hash`) forming a hash chain
- `GET /audit/verify` recomputes and validates the entire chain
- Tamper with any field and the chain breaks — detectable immediately

## Known Limitations

- JWT secret is stored in `.env` — rotate before any non-demo use
- SQLite has no row-level security
- No TLS in local development — production would require HTTPS everywhere
- No rate limiting on the login endpoint
- Demo password (`demo123`) is the same for all users

## Reporting Issues

This is a hackathon project. Report issues via [GitHub Issues](https://github.com/Yogyaa20/trustgate-flex/issues).
