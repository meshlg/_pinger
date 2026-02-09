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

**Discord:** meshlg [Link](https://discordapp.com/users/268440099828662274)

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
- Health endpoints bind to localhost by default (127.0.0.1)
- Authentication required for non-localhost bindings (Basic or Token)
- GET-only endpoints (immune to CSRF attacks)

## Health Endpoints Security

### Default Configuration (Secure)

Health endpoints (`/health`, `/ready`) are configured with security best practices:

| Setting | Default | Purpose | Required for |
|---------|---------|---------|--------------|
| `HEALTH_ADDR` | `127.0.0.1` | Localhost-only binding | Always secure |
| `HEALTH_PORT` | `8001` | Non-privileged port | Always |
| `HEALTH_AUTH_USER` | (optional) | Basic Auth username | With `HEALTH_AUTH_PASS` |
| `HEALTH_AUTH_PASS` | (optional) | Basic Auth password | With `HEALTH_AUTH_USER` |
| `HEALTH_TOKEN` | (optional) | Token for `X-Health-Token` header | Non-localhost (alternative to Basic) |
| `HEALTH_TOKEN_HEADER` | `X-Health-Token` | Custom header name | Optional |

### Authentication Methods

#### Method 1: Basic Auth
```bash
export HEALTH_AUTH_USER=admin
export HEALTH_AUTH_PASS=secret
```

#### Method 2: Token Auth (Recommended for load balancers/Prometheus)
```bash
export HEALTH_TOKEN=your-secret-token
# Custom header name (optional)
export HEALTH_TOKEN_HEADER=X-Custom-Auth
```

#### Both Methods
Either authentication method is accepted:
```bash
export HEALTH_AUTH_USER=admin
export HEALTH_AUTH_PASS=secret
export HEALTH_TOKEN=fallback-token
```

### Security Enforcement

**Authentication is REQUIRED for non-localhost bindings:**

- If `HEALTH_ADDR=0.0.0.0` (or any non-localhost), configure at least one authentication method
- Without authentication, the server will refuse to start with a security error
- Set `HEALTH_ALLOW_NO_AUTH=1` ONLY for development/testing (logs warning)

### Prometheus Configuration (Token Auth)

```yaml
scrape_configs:
  - job_name: pinger-health
    metrics_path: /health
    static_configs:
      - targets: [pinger:8001]
    scheme: http
    http_headers:
      X-Health-Token: ${HEALTH_TOKEN}
```

### ⚠️ Important Security Notes

**DO NOT expose health HTTP endpoints to public internet!**

These endpoints are designed for:
- Kubernetes liveness/readiness probes
- Local monitoring tools
- Docker health checks

If you need external access:
1. Use a reverse proxy with HTTPS termination
2. Add proper authentication (OAuth, JWT, etc.)
3. Or use the Prometheus metrics endpoint with network isolation

### Deployment Examples

#### Docker (Local)
```yaml
# Health endpoint available only at localhost:8001
ports:
  - "127.0.0.1:8001:8001"
```

#### Kubernetes (Internal Network)
```yaml
# For internal cluster access, explicitly set address
env:
  - name: HEALTH_ADDR
    value: "0.0.0.0"
# Service without externalIP = internal only
```

#### Using Basic Auth
```yaml
env:
  - name: HEALTH_AUTH_USER
    valueFrom:
      secretKeyRef:
        name: pinger-secrets
        key: health-username
  - name: HEALTH_AUTH_PASS
    valueFrom:
      secretKeyRef:
        name: pinger-secrets
        key: health-password
```

### Why No CSRF Protection?

CSRF protection is unnecessary because:
- Endpoints are GET-only (read operations)
- No session cookies are used
- Designed for non-browser clients (Kubernetes, Prometheus, curl)

## Known Limitations

- Requires system-level `ping` and `traceroute` commands
- Network monitoring may be detected by target systems
- Health endpoints are HTTP (not HTTPS) - use reverse proxy for encryption
