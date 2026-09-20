# Privacy Policy

## Summary

TrustGate Flex is designed as a consent-based, disclosed access monitoring system. This prototype uses **only synthetic data**. No real employee data is collected, stored, or processed.

## What This Prototype Collects

All data in this prototype is synthetic:

| Data Type | Purpose | Stored As |
|-----------|---------|-----------|
| User ID | Identity | Plain text UUID |
| Device hash | Device trust | SHA-256 hash |
| Location hash | Location anomaly detection | SHA-256 hash |
| Download count | Velocity detection | Integer counter |
| Session ID | Session continuity | UUID |

## What Is NOT Collected

- File content or file names (only hashes)
- Keystrokes, mouse movements, or screen content
- Raw GPS coordinates
- Passwords or authentication tokens
- Any real personally identifiable information
- Audio or video of any kind

## No Surveillance

TrustGate Flex does NOT:
- Log keystrokes or mouse movements
- Record audio or video
- Monitor communications
- Track physical location via GPS
- Build psychological profiles of employees
- Score employees for HR purposes

## Blockchain

Only SHA-256 hashes of audit event metadata are stored in the audit chain. No personal data, passwords, or file content are part of any hash.

## Production Considerations

A production deployment would require:
- A formal Privacy Impact Assessment
- Employee disclosure and informed consent
- Data retention and deletion policies
- Compliance review for GDPR and applicable local law
- A designated data protection officer

## Contact

This is a hackathon prototype. Questions via [GitHub Issues](https://github.com/Yogyaa20/trustgate-flex/issues).
