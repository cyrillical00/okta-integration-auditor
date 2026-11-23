"""Read-only Okta API calls for the auditor.

The domain and the API token are typed by whoever is using the app, and the
server makes the requests. Two rules follow from that:

* the host must be one Okta operates, so the server cannot be pointed at an
  internal address and a token cannot be sent to a look-alike host;
* the token only ever goes to that one host: redirects are not followed and
  a pagination link to anywhere else is refused.
"""
import re
import time as time_module
from urllib.parse import quote, urlsplit

import requests

# A custom domain such as login.example.com cannot be told apart from an
# arbitrary host and is not accepted; use the org's own *.okta.com name.
_OKTA_HOST_RE = re.compile(
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"\.(?:okta\.com|oktapreview\.com|okta-emea\.com|okta-gov\.com|okta\.mil)"
)


def normalize_okta_domain(domain):
    """Return the bare Okta hostname for `domain`, or raise ValueError."""
    host = (domain or "").strip().lower()
    for scheme in ("https://", "http://"):
        if host.startswith(scheme):
            host = host[len(scheme):]
    host = host.rstrip("/")
    if not _OKTA_HOST_RE.fullmatch(host):
        raise ValueError(
            "Enter your Okta org domain, for example yourorg.okta.com "
            "(okta.com, oktapreview.com, okta-emea.com, okta-gov.com or okta.mil)."
        )
    return host


def okta_headers(token):
    return {
        "Authorization": f"SSWS {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _same_host(url, domain):
    target = urlsplit(url)
    return target.scheme == "https" and target.netloc.lower() == domain


def okta_get(url, domain, token, timeout=10):
    """GET a URL on the validated Okta host, never following a redirect."""
    if domain != normalize_okta_domain(domain) or not _same_host(url, domain):
        raise ValueError("Refusing to send the Okta token to a host other than the org's Okta domain.")
    return requests.get(url, headers=okta_headers(token), timeout=timeout, allow_redirects=False)


def _raise_unless_ok(response):
    response.raise_for_status()
    if response.status_code != 200:
        # A redirect or any other non-200 is not data.
        raise requests.HTTPError(f"Unexpected HTTP {response.status_code} from Okta", response=response)


def validate_okta(domain, token):
    r = okta_get(f"https://{domain}/api/v1/org", domain, token)
    _raise_unless_ok(r)
    return r.json()


def fetch_okta_apps(domain, token):
    apps = []
    url = f"https://{domain}/api/v1/apps?limit=200"
    while url:
        r = okta_get(url, domain, token, timeout=15)
        _raise_unless_ok(r)
        apps.extend(r.json())
        url = None
        for part in r.headers.get("Link", "").split(","):
            if 'rel="next"' in part:
                url = part.split(";")[0].strip().strip("<>")
        if url and not _same_host(url, domain):
            raise ValueError("Okta returned a next-page link to another host; not following it.")
        time_module.sleep(0.05)
    return apps


def normalize_live_apps(raw_apps, domain, token):
    results = []
    for app in raw_apps:
        features = app.get("features", [])
        scim_enabled = "PUSH_USER" in features or "IMPORT_USER_SCHEMA" in features

        try:
            ur = okta_get(
                f"https://{domain}/api/v1/apps/{quote(str(app['id']), safe='')}/users?limit=1",
                domain,
                token,
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
