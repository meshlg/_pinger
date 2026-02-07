# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.1.x   | :white_check_mark: |
| 2.0.x   | :white_check_mark: |
| < 2.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in network-pinger, please report it responsibly.

**Do NOT open a public issue** for security vulnerabilities.

**Discord:** meshlg
**Email:** meshlgfox@gmail.com

Please include:
- Description of the vulnerability
- Steps to reproduce (if applicable)
- Potential impact
- Suggested fix (if any)

## Response Time

- **Acknowledgment**: Within 48 hours
- **Initial assessment**: Within 7 days
- **Fix and release**: Depends on severity
  - Critical: 1-2 weeks
  - High: 2-4 weeks
  - Medium/Low: Next release cycle

## Disclosure Policy

We follow responsible disclosure:
1. Report received and acknowledged
2. Vulnerability confirmed and assessed
3. Fix developed and tested
4. Security advisory published
5. Fix released
6. Public disclosure after 30 days (or sooner if already public)

## Security Features

This project implements the following security measures:
- No external network connections except configured ping targets
- Local-only log files (in user's home directory)
- No credential storage
- Input validation on all network operations

## Known Limitations

- Requires system-level `ping` and `traceroute` commands
- Network monitoring may be detected by target systems
- No built-in authentication (single-user tool)
