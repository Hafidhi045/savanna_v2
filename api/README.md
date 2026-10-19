# Savanna Gateway API

The application exposes these endpoints:

- `POST /api/v1/auth`
- `POST /api/v1/gateway/authorize`
- `GET /api/v1/voucher/<code>` (admin session required)
- `GET /health`

The gateway endpoint returns an allow/deny decision.

A real gateway integration must be implemented according to the exact router/controller hardware. Do not treat the Flask endpoint alone as a network firewall.
