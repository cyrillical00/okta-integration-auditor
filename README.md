# Okta Integration Auditor

Surfaces dormant apps, misconfigured SCIM provisioning, and stale integrations across an Okta tenant. Produces a prioritized remediation list with risk scores (0–100) and recommended actions.

Demonstrates 300+ Okta integration management expertise.

![Screenshot placeholder](screenshot.png)

## Features

- **Demo mode** — fully functional with 20 sample apps, no credentials needed
- Risk scoring engine (0–100) based on login recency, SCIM health, assignment state
- Critical / High / Medium / Low risk labels with expandable remediation cards
- Okta console deep links per app
- Full audit CSV, remediation CSV, and executive summary Markdown export

## Risk Score Logic

| Condition | Points |
|---|---|
| No logins ever | +60 |
| No logins in 90+ days | +40 |
| No logins in 180+ days | +20 additional |
| SCIM enabled but error state | +30 |
| Active app, 0 users, 0 groups | +25 |
| App name contains "admin" | +20 |

**Labels:** Critical = 60+, High = 40–59, Medium = 20–39, Low = 0–19

## Local Setup

```bash
git clone https://github.com/cyrillical00/okta-integration-auditor
cd okta-integration-auditor
pip install -r requirements.txt
streamlit run app.py
# Toggle "Demo mode" on in the sidebar to start immediately
```

## Live Okta Connection

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Add your Okta domain and API token
streamlit run app.py
```

API token requires: read-only access to Apps and Users.

## Deploy to Streamlit Cloud

[![Deploy to Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://streamlit.io/cloud)

Demo mode works without any secrets configured.

---

Built by [Oleg Strutsovski](https://linkedin.com/in/olegst)
