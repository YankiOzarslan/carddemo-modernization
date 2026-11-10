# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x     | ✅        |

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it
responsibly:

1. **Do NOT** open a public issue.
2. Email: yankiozarslan@gmail.com (or open a private GitHub Security Advisory).
3. Include steps to reproduce and potential impact.
4. You will receive a response within 48 hours.

## Security Design

This project follows secure-by-design principles:

- **No secrets in code**: All configuration via environment variables.
- **Input validation**: Date parameters validated via `datetime.strptime`.
- **No SQL injection**: Uses dict lookups, not raw SQL.
- **Decimal precision**: Money handled with `Decimal`, no float drift.
- **Dependency scanning**: `pip-audit` in CI.
- **Static analysis**: `bandit` + `ruff` in CI.
- **Least privilege**: Lambda function has minimal IAM permissions.
- **No PII in logs**: Transaction data is not logged.
- **Container security**: Non-root user in Dockerfile.

## Threat Model

| Threat | Mitigation |
|--------|------------|
| Path traversal in data_dir | Validated; only reads expected filenames |
| Malformed fixed-width records | Graceful parsing with defaults |
| Oversized input | Lambda timeout + memory limits |
| Dependency vulnerabilities | Automated `pip-audit` in CI |
| Secret leakage | `.env` in `.gitignore`, `.env.example` provided |
EOF