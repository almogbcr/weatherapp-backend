"""Exercise the real ASGI middleware without external APIs or a database server."""
import importlib
import unittest
from unittest.mock import AsyncMock, Mock, patch

import httpx
from fastapi.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families

from app.settings import Settings


class MetricsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch("app.settings.get_settings", return_value=Settings(
            api_key="test-api-key-private", database_url="sqlite:///:memory:"
        )):
            cls.main = importlib.import_module("app.main")
        # No lifespan is needed: these requests do not access database tables.
        cls.client = TestClient(cls.main.app, raise_server_exceptions=False)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.main.engine.dispose()

    def scrape(self):
        response = self.client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response.headers["content-type"])
        return response.text

    def samples(self, name):
        return [sample for family in text_string_to_metric_families(self.scrape())
                for sample in family.samples if sample.name == name]

    def count(self, handler, status):
        return sum(s.value for s in self.samples("http_requests_total")
                   if s.labels == {"handler": handler, "status": status})

    def test_success_and_exact_error_status_counts_preserve_responses(self):
        for path, handler, status, body in [
            ("/health", "/health", 200, {"status": "ok"}),
            ("/weather?lat=1&lon=2", "/weather", 400,
             {"detail": "X-Device-Id header required"}),
            ("/geocode", "/geocode", 422, None),
            ("/missing-metrics-test", "none", 404, {"detail": "Not Found"}),
        ]:
            with self.subTest(status=status):
                before = self.count(handler, str(status))
                response = self.client.get(path)
                self.assertEqual(response.status_code, status)
                if body is not None:
                    self.assertEqual(response.json(), body)
                self.assertEqual(self.count(handler, str(status)), before + 1)

    def test_response_duration_histograms_observe_requests(self):
        def observations():
            return sum(s.value for s in self.samples("http_request_duration_seconds_count")
                       if s.labels == {"handler": "/health"})

        before = observations()
        self.client.get("/health")
        self.assertEqual(observations(), before + 1)
        buckets = self.samples("http_request_duration_seconds_bucket")
        self.assertTrue(any(s.labels.get("handler") == "/health" and s.value > 0
                            for s in buckets))
        self.assertTrue(all(s.value >= 0 for s in self.samples(
            "http_request_duration_seconds_sum")))

    def test_upstream_and_unhandled_errors_are_counted(self):
        upstream_response = httpx.Response(503, request=httpx.Request("GET", "https://example.test"))
        upstream = AsyncMock()
        upstream.get.return_value = upstream_response
        context = AsyncMock()
        context.__aenter__.return_value = upstream
        before = self.count("/geocode", "502")
        with patch.object(self.main.httpx, "AsyncClient", return_value=context):
            response = self.client.get("/geocode?q=London")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"]["upstream_status"], 503)
        self.assertEqual(self.count("/geocode", "502"), before + 1)

        before = self.count("/weather", "500")
        with patch.object(self.main, "SessionLocal", Mock(begin=Mock(side_effect=RuntimeError("test failure")))):
            response = self.client.get("/weather?lat=1&lon=2", headers={"X-Device-Id": "test-device"})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.count("/weather", "500"), before + 1)

    def test_metrics_exclude_sensitive_data_and_bound_unknown_paths(self):
        private_values = ["test-api-key-private", "private-device-123", "private-address-456",
                          "private-path-789", "198.51.100.42", "31.123456", "35.654321"]
        before = self.count("none", "404")
        for index in range(12):
            self.client.get(f"/{private_values[3]}-{index}",
                            params={"q": private_values[2], "api_key": private_values[0]},
                            headers={"X-Device-Id": private_values[1],
                                     "X-Forwarded-For": private_values[4]})
        self.client.get("/weather", params={"lat": private_values[5], "lon": private_values[6],
                                            "api_key": private_values[0]})
        self.assertEqual(self.count("none", "404"), before + 12)
        output = self.scrape()
        for value in private_values:
            self.assertNotIn(value, output)
        for sample in self.samples("http_requests_total"):
            self.assertEqual(set(sample.labels), {"handler", "status"})
            self.assertIn(sample.labels["handler"],
                          {route.path for route in self.main.app.routes} | {"none"})

    def test_arbitrary_methods_do_not_create_labels_or_change_405(self):
        before = self.count("none", "405")
        for index in range(10):
            response = self.client.request(f"PRIVATE-METHOD-{index}", "/health")
            self.assertEqual(response.status_code, 405)
        self.assertEqual(self.count("none", "405"), before + 10)
        self.assertNotIn("PRIVATE-METHOD", self.scrape())

    def test_scrapes_are_not_counted_or_added_to_openapi(self):
        before = self.samples("http_requests_total")
        self.scrape()
        self.scrape()
        self.assertEqual(self.samples("http_requests_total"), before)
        self.assertNotIn("/metrics", self.main.app.openapi()["paths"])


if __name__ == "__main__":
    unittest.main()
