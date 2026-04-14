from datetime import datetime, timedelta


def get_mock_apps():
    today = datetime.utcnow()

    def days_ago(n):
        return (today - timedelta(days=n)).strftime("%Y-%m-%d")

    return [
        {"id": "app001", "name": "Slack Enterprise Grid", "type": "SAML", "status": "ACTIVE",
         "users": 312, "groups": 8, "last_login": days_ago(2), "scim_enabled": True, "scim_status": "Active"},
        {"id": "app002", "name": "GitHub Enterprise", "type": "OIDC", "status": "ACTIVE",
         "users": 280, "groups": 5, "last_login": days_ago(1), "scim_enabled": True, "scim_status": "Active"},
        {"id": "app003", "name": "Salesforce", "type": "SAML", "status": "ACTIVE",
         "users": 95, "groups": 3, "last_login": days_ago(5), "scim_enabled": True, "scim_status": "Error"},
        {"id": "app004", "name": "Old HR Portal", "type": "SWA", "status": "INACTIVE",
         "users": 0, "groups": 0, "last_login": "Never", "scim_enabled": False, "scim_status": "Not configured"},
        {"id": "app005", "name": "Zoom", "type": "SAML", "status": "ACTIVE",
         "users": 290, "groups": 4, "last_login": days_ago(3), "scim_enabled": False, "scim_status": "Not configured"},
        {"id": "app006", "name": "Box", "type": "SAML", "status": "ACTIVE",
         "users": 150, "groups": 6, "last_login": days_ago(15), "scim_enabled": True, "scim_status": "Active"},
        {"id": "app007", "name": "Legacy CRM admin", "type": "SWA", "status": "ACTIVE",
         "users": 0, "groups": 0, "last_login": days_ago(200), "scim_enabled": False, "scim_status": "Not configured"},
        {"id": "app008", "name": "Google Workspace", "type": "SAML", "status": "ACTIVE",
         "users": 315, "groups": 10, "last_login": days_ago(1), "scim_enabled": True, "scim_status": "Active"},
        {"id": "app009", "name": "Jira/Confluence", "type": "SAML", "status": "ACTIVE",
         "users": 200, "groups": 7, "last_login": days_ago(4), "scim_enabled": True, "scim_status": "Active"},
        {"id": "app010", "name": "Figma", "type": "SAML", "status": "ACTIVE",
         "users": 45, "groups": 2, "last_login": days_ago(10), "scim_enabled": False, "scim_status": "Not configured"},
        {"id": "app011", "name": "Old Vendor Portal", "type": "SWA", "status": "INACTIVE",
         "users": 0, "groups": 0, "last_login": "Never", "scim_enabled": False, "scim_status": "Not configured"},
        {"id": "app012", "name": "Workday", "type": "SAML", "status": "ACTIVE",
         "users": 310, "groups": 5, "last_login": days_ago(1), "scim_enabled": True, "scim_status": "Active"},
        {"id": "app013", "name": "Docusign", "type": "SAML", "status": "ACTIVE",
         "users": 80, "groups": 2, "last_login": days_ago(95), "scim_enabled": False, "scim_status": "Not configured"},
        {"id": "app014", "name": "Greenhouse ATS", "type": "OIDC", "status": "ACTIVE",
         "users": 12, "groups": 1, "last_login": days_ago(120), "scim_enabled": False, "scim_status": "Not configured"},
        {"id": "app015", "name": "Splunk admin", "type": "SAML", "status": "ACTIVE",
         "users": 0, "groups": 0, "last_login": days_ago(250), "scim_enabled": False, "scim_status": "Not configured"},
        {"id": "app016", "name": "Tableau", "type": "SAML", "status": "ACTIVE",
         "users": 30, "groups": 2, "last_login": days_ago(7), "scim_enabled": False, "scim_status": "Not configured"},
        {"id": "app017", "name": "1Password Teams", "type": "SAML", "status": "ACTIVE",
         "users": 300, "groups": 8, "last_login": days_ago(1), "scim_enabled": True, "scim_status": "Active"},
        {"id": "app018", "name": "Retool admin", "type": "OIDC", "status": "ACTIVE",
         "users": 0, "groups": 0, "last_login": "Never", "scim_enabled": False, "scim_status": "Not configured"},
        {"id": "app019", "name": "Notion", "type": "SAML", "status": "ACTIVE",
         "users": 180, "groups": 3, "last_login": days_ago(2), "scim_enabled": True, "scim_status": "Active"},
        {"id": "app020", "name": "ServiceNow", "type": "SAML", "status": "INACTIVE",
         "users": 5, "groups": 1, "last_login": days_ago(185), "scim_enabled": True, "scim_status": "Error"},
    ]
