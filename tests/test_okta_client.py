"""The auditor must only ever send a visitor's token to an Okta-operated host."""
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import requests  # noqa: E402

from utils import okta_client  # noqa: E402

TOKEN = "not-a-real-token"
HOST = "https://acme.okta.com"


class _Response:
    def __init__(self, payload=None, status=200, link=None):
        self.status_code = status
        self._payload = payload if payload is not None else []
        self.headers = {"Link": link} if link else {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


class _FakeOkta:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        for needle, response in self.routes:
            if needle in url:
                return response(url) if callable(response) else response
        return _Response(status=404)


def _next(url):
    return f'<{url}>; rel="next"'


class DomainTests(unittest.TestCase):
    def test_okta_hosts_are_accepted_and_normalised(self):
        for raw, expected in {
            "acme.okta.com": "acme.okta.com",
            " https://ACME.okta.com/ ": "acme.okta.com",
            "http://acme.okta.com": "acme.okta.com",
            "acme-admin.okta.com": "acme-admin.okta.com",
            "dev-123456.oktapreview.com": "dev-123456.oktapreview.com",
            "acme.okta-emea.com": "acme.okta-emea.com",
            "acme.okta-gov.com": "acme.okta-gov.com",
            "acme.okta.mil": "acme.okta.mil",
        }.items():
            self.assertEqual(okta_client.normalize_okta_domain(raw), expected, raw)

    def test_everything_else_is_refused(self):
        for raw in (
            "", None, "okta.com", "demo", "localhost", "127.0.0.1", "169.254.169.254", "[::1]",
            "internal:8443/x?", "internal.corp.example", "login.example.com",
            "acme.okta.com.evil.example", "evil.example/acme.okta.com", "evil.example#.okta.com",
            "evil.example?.okta.com", "acme.okta.com@evil.example", "evil.example\\.okta.com",
            "acme.okta.com:8443", "acme.okta.com/api/v1/apps", "a.b.okta.com", "-acme.okta.com",
            "acmeokta.com", "acme.notokta.com", "acme.okta.com\nHost: evil.example", "ftp://acme.okta.com",
        ):
            with self.assertRaises(ValueError, msg=repr(raw)):
                okta_client.normalize_okta_domain(raw)


class RequestTests(unittest.TestCase):
    def test_every_helper_refuses_an_unvalidated_host_without_sending(self):
        with mock.patch.object(okta_client.requests, "get") as get:
            for domain in ("internal:8443/x?", "evil.example", "ACME.okta.com", "169.254.169.254"):
                with self.assertRaises(ValueError, msg=domain):
                    okta_client.validate_okta(domain, TOKEN)
                with self.assertRaises(ValueError, msg=domain):
                    okta_client.fetch_okta_apps(domain, TOKEN)
            with self.assertRaises(ValueError):
                okta_client.okta_get("https://evil.example/api/v1/org", "acme.okta.com", TOKEN)
            with self.assertRaises(ValueError):
                okta_client.okta_get("http://acme.okta.com/api/v1/org", "acme.okta.com", TOKEN)
            get.assert_not_called()

    def test_requests_stay_on_the_org_and_follow_no_redirect(self):
        fake = _FakeOkta([
            ("/api/v1/org", _Response({"companyName": "Acme"})),
            ("/users?limit=1", _Response([{"id": "u1"}])),
            ("/api/v1/apps?", _Response([{"id": "0oa1", "label": "Slack", "features": ["PUSH_USER"]}])),
        ])
        with mock.patch.object(okta_client.requests, "get", side_effect=fake), \
                mock.patch.object(okta_client.time_module, "sleep"):
            self.assertEqual(okta_client.validate_okta("acme.okta.com", TOKEN), {"companyName": "Acme"})
            raw = okta_client.fetch_okta_apps("acme.okta.com", TOKEN)
            apps = okta_client.normalize_live_apps(raw, "acme.okta.com", TOKEN)

        self.assertEqual(apps[0]["name"], "Slack")
        self.assertEqual(apps[0]["users"], 1)
        self.assertTrue(apps[0]["scim_enabled"])
        self.assertEqual(len(fake.calls), 3)
        for url, kwargs in fake.calls:
            self.assertTrue(url.startswith(HOST + "/api/v1/"), url)
            self.assertIs(kwargs.get("allow_redirects"), False, url)
            self.assertEqual(kwargs["headers"]["Authorization"], f"SSWS {TOKEN}")

    def test_pagination_follows_same_host_links(self):
        def apps(url):
            if "after=p2" in url:
                return _Response([{"id": "0oa2"}])
            return _Response([{"id": "0oa1"}], link=_next(f"{HOST}/api/v1/apps?after=p2&limit=200"))

        fake = _FakeOkta([("/api/v1/apps?", apps)])
        with mock.patch.object(okta_client.requests, "get", side_effect=fake), \
                mock.patch.object(okta_client.time_module, "sleep"):
            result = okta_client.fetch_okta_apps("acme.okta.com", TOKEN)
        self.assertEqual([a["id"] for a in result], ["0oa1", "0oa2"])

    def test_a_next_link_to_another_host_is_refused(self):
        for link in (
            "https://evil.example/api/v1/apps?after=p2",
            "http://acme.okta.com/api/v1/apps?after=p2",
            "https://acme.okta.com.evil.example/api/v1/apps?after=p2",
            "https://acme.okta.com@evil.example/api/v1/apps?after=p2",
            "https://acme.okta.com:8443/api/v1/apps?after=p2",
            "//evil.example/api/v1/apps",
        ):
            fake = _FakeOkta([("/api/v1/apps?", _Response([{"id": "0oa1"}], link=_next(link)))])
            with mock.patch.object(okta_client.requests, "get", side_effect=fake), \
                    mock.patch.object(okta_client.time_module, "sleep"):
                with self.assertRaises(ValueError, msg=link):
                    okta_client.fetch_okta_apps("acme.okta.com", TOKEN)
            self.assertEqual([url for url, _ in fake.calls], [f"{HOST}/api/v1/apps?limit=200"], link)

    def test_a_redirect_is_an_error_not_data(self):
        redirect = _Response(status=302)
        redirect.headers["Location"] = "https://evil.example/"
        with mock.patch.object(okta_client.requests, "get", return_value=redirect) as get:
            with self.assertRaises(requests.HTTPError):
                okta_client.validate_okta("acme.okta.com", TOKEN)
            with self.assertRaises(requests.HTTPError):
                okta_client.fetch_okta_apps("acme.okta.com", TOKEN)
            self.assertEqual(get.call_count, 2)

    def test_app_ids_cannot_reshape_the_request_path(self):
        fake = _FakeOkta([("/users?limit=1", _Response([]))])
        with mock.patch.object(okta_client.requests, "get", side_effect=fake), \
                mock.patch.object(okta_client.time_module, "sleep"):
            okta_client.normalize_live_apps([{"id": "../../users?x=1#"}], "acme.okta.com", TOKEN)
        url = fake.calls[0][0]
        self.assertEqual(url, f"{HOST}/api/v1/apps/..%2F..%2Fusers%3Fx%3D1%23/users?limit=1")


class AppFlowTests(unittest.TestCase):
    """Drive the real page under Streamlit's test harness."""

    def setUp(self):
        try:
            from streamlit.testing.v1 import AppTest
        except Exception:  # pragma: no cover - older Streamlit
            self.skipTest("streamlit.testing is not available")
        self.AppTest = AppTest

    def _connect(self, domain):
        at = self.AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
        at.run()
        at.sidebar.toggle[0].set_value(False).run()
        at.sidebar.text_input[0].input(domain)
        at.sidebar.text_input[1].input(TOKEN)
        at.sidebar.button[0].click().run()
        return at

    def test_a_non_okta_domain_is_rejected_before_any_request(self):
        for domain in ("internal:8443/x?", "169.254.169.254", "login.example.com"):
            with mock.patch.object(okta_client.requests, "get") as get:
                at = self._connect(domain)
                get.assert_not_called()
            self.assertFalse(at.exception, [e.value for e in at.exception])
            self.assertTrue(any("Okta org domain" in e.value for e in at.sidebar.error), domain)
            # Nothing was connected: the session still holds the sample tenant.
            self.assertEqual(at.session_state["okta_domain"], "demo.okta.com")

    def test_a_valid_domain_connects(self):
        fake = _FakeOkta([
            ("/api/v1/org", _Response({"companyName": "Acme"})),
            ("/users?limit=1", _Response([])),
            ("/api/v1/apps?", _Response([{"id": "0oa1", "label": "Slack", "status": "ACTIVE"}])),
        ])
        with mock.patch.object(okta_client.requests, "get", side_effect=fake), \
                mock.patch.object(okta_client.time_module, "sleep"):
            at = self._connect("https://Acme.okta.com/")
        self.assertFalse(at.exception, [e.value for e in at.exception])
        self.assertTrue(at.session_state["okta_connected"])
        self.assertEqual(at.session_state["okta_domain"], "acme.okta.com")
        self.assertTrue(all(url.startswith(HOST + "/") for url, _ in fake.calls))

    def test_demo_mode_needs_no_network(self):
        with mock.patch.object(okta_client.requests, "get") as get:
            at = self.AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
            at.run()
            get.assert_not_called()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        self.assertEqual(at.metric[0].value, "20")


if __name__ == "__main__":
    unittest.main()
