# 🦁 Savanna Wi-Fi Hotspot System — v2

Savanna v2 is a Flask + SQLite MVP for a real hotspot workflow.

## What v2 contains

- Admin authentication
- Dashboard
- Daily / Weekly / Monthly packages
- Voucher generation
- Voucher activation
- One-voucher / one-device binding
- Automatic expiry validation
- Customer records
- Session records
- Multi-site inventory for routers and access points
- Sales records
- Captive portal prototype
- JSON authentication API
- Gateway authorization API contract
- Separate CSS and JavaScript
- SQLite database
- Health endpoint

## Integration status

The **Sites & Network** page currently records sites, MikroTik routers, and access points, including their relationships. It does not yet connect to or control the physical devices. Live RouterOS API/RADIUS integration, Selcom checkout and verified payment callbacks, and Beem SMS delivery are not enabled yet. They require active provider accounts, production credentials, public HTTPS callback URLs, and device connectivity details.

Never enter a customer's mobile-money PIN into this application. Selcom's secure wallet prompt is where the customer authorizes payment; HAFIDHI WFI should issue access only after verified payment confirmation.

## Requirements

- Ubuntu/Linux
- Python 3.10+
- pip
- Browser

## Run on Ubuntu

```bash
cd savanna_v2

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Default administrator

These credentials are created only when the database has no accounts. Change this password after the first sign-in.

```text
Username: admin
Password: admin123
```

The Super Admin can create staff accounts from **Admins** by assigning a username, role, and temporary password. Staff use those credentials on the regular login page, then change their password from **My password**. Temporary passwords should be shared privately.

Change the default credentials and application secret before production use.

## Provider credentials

Copy `.env.example` to `.env`, then fill in the Selcom and Beem values from the respective provider accounts. The `.env` file is excluded from Git. Restart the app after updating it. The **Integrations** page shows whether required values are present without displaying secrets. Never put mobile-money PINs or customer PINs in this file.

## Test the customer portal

Open:

```text
http://127.0.0.1:5000/portal
```

First create a voucher from the admin dashboard, then activate it with a test device ID.

Example:

```text
Device ID: TEST-DEVICE-001
```

Then use the same device ID in the portal.

Try another device:

```text
TEST-DEVICE-002
```

The voucher should be denied because it is bound to the first device.

## API

Health:

```text
GET /health
```

Authenticate:

```text
POST /api/v1/auth
Content-Type: application/json

{
  "code": "SVN-XXXX-XXXX",
  "device_id": "TEST-DEVICE-001"
}
```

Gateway authorization contract:

```text
POST /api/v1/gateway/authorize
Content-Type: application/json

{
  "code": "SVN-XXXX-XXXX",
  "device_id": "TEST-DEVICE-001"
}
```

## Important network note

This v2 project does NOT yet directly control a physical router.

The gateway endpoint is an integration contract. The next step is to identify your actual router/gateway and implement the correct integration method.

Depending on the hardware, that may involve:

- Router API
- RADIUS
- Captive portal integration
- OpenWrt
- MikroTik RouterOS
- pfSense/OPNsense
- another supported gateway/controller

Do not expose the Flask API directly to the public internet. Put it behind a protected management network/firewall when moving beyond local testing.
