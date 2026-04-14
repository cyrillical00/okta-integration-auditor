import streamlit as st
import requests
import pandas as pd
import time as time_module
from datetime import datetime, timedelta
from utils.mock_data import get_mock_apps

st.set_page_config(page_title="Okta Integration Auditor", page_icon="🔐", layout="wide")

st.sidebar.markdown("## 🔐 Okta Integration Auditor")
st.sidebar.markdown("Audit Okta integrations for dormant, misconfigured, and risky apps.")
st.sidebar.markdown("---")
st.sidebar.subheader("Connection")

demo_mode = st.sidebar.toggle("Demo mode (no credentials needed)", value=True)

if not demo_mode:
    okta_domain_input = st.sidebar.text_input("Okta domain (e.g. yourorg.okta.com)")
    api_token_input = st.sidebar.text_input("Okta API Token", type="password")
    connect = st.sidebar.button("Connect", type="primary")
else:
    okta_domain_input = "demo.okta.com"
    api_token_input = ""
    connect = True


def okta_headers(token):
    return {
        "Authorization": f"SSWS {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def validate_okta(domain, token):
    r = requests.get(f"https://{domain}/api/v1/org", headers=okta_headers(token), timeout=10)
    r.raise_for_status()
    return r.json()


def compute_risk_score(app):
    score = 0
    reasons = []
    last_login = app.get("last_login", "Never")
    now = datetime.utcnow()

    if last_login == "Never":
        score += 60
        reasons.append("No user logins ever recorded")
    else:
        try:
            last_dt = datetime.strptime(last_login, "%Y-%m-%d")
            days_ago = (now - last_dt).days
            if days_ago >= 180:
                score += 60  # 40 base + 20 bonus
                reasons.append(f"No logins in {days_ago} days (180+ day threshold)")
            elif days_ago >= 90:
                score += 40
                reasons.append(f"No logins in {days_ago} days (90+ day threshold)")
        except ValueError:
            pass

    if app.get("scim_enabled") and app.get("scim_status") == "Error":
        score += 30
        reasons.append("SCIM enabled but in error state")

    if app.get("users", 0) == 0 and app.get("groups", 0) == 0 and app.get("status") == "ACTIVE":
        score += 25
        reasons.append("Active app with zero users and zero groups assigned")

    if "admin" in app.get("name", "").lower():
        score += 20
        reasons.append("App name contains 'admin' — verify MFA enforcement")

    return min(score, 100), reasons


def risk_label(score):
    if score >= 60:
        return "Critical"
    elif score >= 40:
        return "High"
    elif score >= 20:
        return "Medium"
    return "Low"


def fetch_okta_apps(domain, token):
    apps = []
    url = f"https://{domain}/api/v1/apps?limit=200"
    while url:
        r = requests.get(url, headers=okta_headers(token), timeout=15)
        r.raise_for_status()
        apps.extend(r.json())
        url = None
        for part in r.headers.get("Link", "").split(","):
            if 'rel="next"' in part:
                url = part.split(";")[0].strip().strip("<>")
        time_module.sleep(0.05)
    return apps


def normalize_live_apps(raw_apps, domain, token):
    results = []
    for app in raw_apps:
        features = app.get("features", [])
        scim_enabled = "PUSH_USER" in features or "IMPORT_USER_SCHEMA" in features

        try:
            ur = requests.get(
                f"https://{domain}/api/v1/apps/{app['id']}/users?limit=1",
                headers=okta_headers(token),
                timeout=10,
            )
            users_count = len(ur.json()) if ur.status_code == 200 else 0
        except Exception:
            users_count = 0

        results.append({
            "id": app["id"],
            "name": app.get("label", "Unknown"),
            "type": app.get("signOnMode", "Unknown"),
            "status": app.get("status", "Unknown"),
            "users": users_count,
            "groups": 0,
            "last_login": "Unknown",
            "scim_enabled": scim_enabled,
            "scim_status": "Active" if scim_enabled else "Not configured",
        })
        time_module.sleep(0.05)
    return results


# Session state
for key in ("okta_connected", "okta_domain", "okta_apps"):
    if key not in st.session_state:
        st.session_state[key] = None
if st.session_state.okta_connected is None:
    st.session_state.okta_connected = False

if connect:
    if demo_mode:
        st.session_state.okta_connected = True
        st.session_state.okta_domain = "demo.okta.com"
        st.session_state.okta_apps = get_mock_apps()
        st.sidebar.success("Demo mode active — showing sample data")
    else:
        if not okta_domain_input or not api_token_input:
            st.sidebar.error("Enter both domain and API token.")
        else:
            domain = okta_domain_input.replace("https://", "").replace("http://", "").strip("/")
            with st.spinner("Connecting to Okta..."):
                try:
                    validate_okta(domain, api_token_input)
                    with st.spinner("Fetching apps..."):
                        raw = fetch_okta_apps(domain, api_token_input)
                        apps = normalize_live_apps(raw, domain, api_token_input)
                    st.session_state.okta_connected = True
                    st.session_state.okta_domain = domain
                    st.session_state.okta_apps = apps
                    st.sidebar.success(f"Connected: {domain}")
                except Exception as e:
                    st.sidebar.error(f"Connection failed: {e}")

if st.session_state.okta_connected and st.session_state.okta_apps:
    apps = st.session_state.okta_apps
    domain = st.session_state.okta_domain
    now = datetime.utcnow()
    cutoff_30 = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    cutoff_90 = (now - timedelta(days=90)).strftime("%Y-%m-%d")

    # Enrich with risk scores
    enriched = []
    for app in apps:
        score, reasons = compute_risk_score(app)
        enriched.append({**app, "risk_score": score, "risk_label": risk_label(score), "risk_reasons": reasons})
    df = pd.DataFrame(enriched)

    # Metric calculations
    def is_active(row):
        ll = row.get("last_login", "Never")
        if ll in ("Never", "Unknown"):
            return False
        try:
            return ll >= cutoff_30
        except Exception:
            return False

    def is_dormant(row):
        ll = row.get("last_login", "Never")
        if ll in ("Never", "Unknown"):
            return True
        try:
            return ll < cutoff_90
        except Exception:
            return False

    def is_misconfigured(row):
        return (row.get("scim_enabled") and row.get("scim_status") == "Error") or (
            row.get("users", 0) == 0 and row.get("groups", 0) == 0 and row.get("status") == "ACTIVE"
        )

    total = len(df)
    active_count = sum(1 for _, r in df.iterrows() if is_active(r))
    dormant_count = sum(1 for _, r in df.iterrows() if is_dormant(r))
    misconfig_count = sum(1 for _, r in df.iterrows() if is_misconfigured(r))

    st.title("Okta Integration Auditor")
    if demo_mode:
        st.info("Running in **demo mode** with 20 sample apps. Toggle off in sidebar to connect to a real Okta tenant.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Apps", total)
    c2.metric("Active (30d)", active_count)
    c3.metric("Dormant (90d+)", dormant_count)
    c4.metric("Misconfigured", misconfig_count)

    st.subheader("Integration Health Dashboard")
    display_cols = [
        "name", "type", "status", "users", "groups",
        "last_login", "scim_enabled", "scim_status", "risk_score", "risk_label",
    ]
    risk_filter = st.multiselect(
        "Filter by risk", ["Critical", "High", "Medium", "Low"],
        default=["Critical", "High", "Medium", "Low"],
    )
    status_filter = st.multiselect(
        "Filter by status", ["ACTIVE", "INACTIVE"], default=["ACTIVE", "INACTIVE"]
    )
    filtered = df[df["risk_label"].isin(risk_filter) & df["status"].isin(status_filter)]
    st.dataframe(
        filtered[display_cols].sort_values("risk_score", ascending=False),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Remediation Recommendations")
    critical_high = df[df["risk_label"].isin(["Critical", "High"])].sort_values("risk_score", ascending=False)

    def pick_action(reasons):
        for reason in reasons:
            if "Never" in reason or "logins" in reason:
                return "Deactivate app"
            if "SCIM" in reason:
                return "Review SCIM configuration"
            if "zero users" in reason:
                return "Remove unused assignment"
            if "admin" in reason.lower():
                return "Request access review from app owner"
        return "Request access review from app owner"

    for _, row in critical_high.iterrows():
        badge = "🔴" if row["risk_label"] == "Critical" else "🟠"
        with st.expander(f"{badge} {row['name']} — {row['risk_label']} (Score: {row['risk_score']})"):
            st.markdown("**Why flagged:**")
            for reason in row.get("risk_reasons", []):
                st.markdown(f"- {reason}")
            action = pick_action(row.get("risk_reasons", []))
            st.markdown(f"**Recommended action:** {action}")
            if domain != "demo.okta.com":
                st.markdown(f"[Open in Okta Console](https://{domain}/admin/app/{row['id']}/general)")

    st.subheader("Export")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button(
            "Download Full Audit as CSV",
            data=df[display_cols].to_csv(index=False),
            file_name="okta_full_audit.csv",
            mime="text/csv",
        )
    with col2:
        remed = df[df["risk_label"].isin(["Critical", "High"])][display_cols]
        st.download_button(
            "Download Remediation List as CSV",
            data=remed.to_csv(index=False),
            file_name="okta_remediation.csv",
            mime="text/csv",
        )
    with col3:
        top5 = df.sort_values("risk_score", ascending=False).head(5)
        exec_lines = [
            f"# Okta Integration Audit — Executive Summary",
            f"**Organization:** {domain}  \n**Audit Date:** {now.strftime('%Y-%m-%d')}",
            "## Overview",
            "| Metric | Count |",
            "| --- | --- |",
            f"| Total Apps | {total} |",
            f"| Active (30d logins) | {active_count} |",
            f"| Dormant (90d+ no logins) | {dormant_count} |",
            f"| Misconfigured | {misconfig_count} |",
            f"| Critical Risk | {len(df[df['risk_label']=='Critical'])} |",
            f"| High Risk | {len(df[df['risk_label']=='High'])} |",
            "## Top 5 Highest-Risk Apps",
        ]
        for _, r in top5.iterrows():
            exec_lines.append(f"\n### {r['name']} — {r['risk_label']} (Score: {r['risk_score']})")
            for reason in r.get("risk_reasons", []):
                exec_lines.append(f"- {reason}")
            exec_lines.append(f"**Action:** {pick_action(r.get('risk_reasons', []))}")
        st.download_button(
            "Download Executive Summary as Markdown",
            data="\n\n".join(exec_lines),
            file_name="okta_exec_summary.md",
            mime="text/markdown",
        )

else:
    st.title("Okta Integration Auditor")
    st.info("Enable **Demo mode** in the sidebar to explore the tool without credentials, or enter your Okta domain and API token.")

st.sidebar.markdown("---")
st.sidebar.markdown("Built by [Oleg Strutsovski](https://linkedin.com/in/olegst)")
