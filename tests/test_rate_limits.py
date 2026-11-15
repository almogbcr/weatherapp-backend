"""Quota tests; set TEST_POSTGRES_URL to an isolated test server for locking tests.

Each test owns a randomly named schema; existing tables/data are never reset.
"""
import importlib
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text

from app.db import Base, build_session_factory
from app.limit_store import check_and_increment
from app.models import DailyGlobalCount, DailyIpCount, DailyDeviceCount, DailyPairCount
from app.settings import Settings, get_settings


class RateLimitTests(unittest.TestCase):
    def setUp(self):
        self.url = os.getenv("TEST_POSTGRES_URL")
        self.temp = tempfile.TemporaryDirectory()
        self.schema = "quota_test_" + uuid4().hex
        self.url = self.url or f"sqlite:///{self.temp.name}/quota.db"
        self.root = create_engine(self.url)
        self.postgres = self.root.dialect.name == "postgresql"
        if self.postgres:
            with self.root.begin() as conn:
                conn.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        self.engine = self.new_engine()
        Base.metadata.create_all(self.engine)
        self.sessions = build_session_factory(self.engine)

    def new_engine(self):
        engine = create_engine(self.url)
        if self.postgres:
            engine = engine.execution_options(schema_translate_map={None: self.schema})
        return engine

    def tearDown(self):
        self.engine.dispose()
        if self.postgres:
            with self.root.begin() as conn:
                conn.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))
        self.root.dispose()
        self.temp.cleanup()

    def admit(self, ip="ip", device="device", limit=100, global_limit=999, factory=None):
        with (factory or self.sessions).begin() as session:
            return check_and_increment(session, ip, device, limit, global_limit)

    def counts(self):
        with self.sessions() as session:
            return [session.scalars(select(model.count)).all() for model in
                    (DailyGlobalCount, DailyIpCount, DailyDeviceCount, DailyPairCount)]

    def test_global_quota_shared_by_different_clients(self):
        for i in range(3):
            self.assertFalse(self.admit(str(i), str(i), global_limit=3).blocked)
        denied = self.admit("new", "new", global_limit=3)
        self.assertEqual(denied.reason, "global_daily_limit")
        self.assertEqual(self.counts(), [[3], [1, 1, 1], [1, 1, 1], [1, 1, 1]])
        self.assertEqual(set(denied.to_dict()),
                         {"day", "limit", "ip_count", "device_count", "pair_count", "blocked"})

    def test_personal_quota_preserves_all_identity_counters(self):
        self.admit(limit=1)
        for ip, device in [("ip", "other"), ("other", "device"), ("ip", "device")]:
            self.assertEqual(self.admit(ip, device, limit=1).reason, "personal_daily_limit")
        self.assertEqual(self.counts(), [[1], [1], [1], [1]])

    def test_daily_reset_preserves_previous_day(self):
        self.admit(limit=1, global_limit=1)
        tomorrow = date.today() + timedelta(days=1)
        with patch("app.limit_store.date") as clock:
            clock.today.return_value = tomorrow
            result = self.admit(limit=1, global_limit=1)
        self.assertFalse(result.blocked)
        self.assertEqual(result.day, tomorrow.isoformat())
        self.assertEqual(self.counts(), [[1, 1], [1, 1], [1, 1], [1, 1]])

    def test_additive_initialization_preserves_preexisting_client_data(self):
        # This schema belongs only to this test. Simulate the pre-upgrade layout.
        DailyGlobalCount.__table__.drop(self.engine)
        today = date.today()
        with self.sessions.begin() as session:
            session.add_all([
                DailyIpCount(day=today, ip="existing", count=2),
                DailyDeviceCount(day=today, device_id="existing", count=2),
                DailyPairCount(day=today, ip="existing", device_id="existing", count=2),
            ])
        Base.metadata.create_all(self.engine)
        self.assertEqual(self.counts(), [[], [2], [2], [2]])
        result = self.admit("existing", "existing", limit=3)
        self.assertFalse(result.blocked)
        self.assertEqual(self.counts(), [[1], [3], [3], [3]])

    def test_restart_keeps_existing_counters_and_application_tables(self):
        self.admit(limit=1)
        self.engine.dispose()
        restarted = self.new_engine()
        try:
            Base.metadata.create_all(restarted)
            factory = build_session_factory(restarted)
            self.assertEqual(self.admit(limit=1, factory=factory).reason, "personal_daily_limit")
            self.assertEqual(self.admit("new", "new", global_limit=1, factory=factory).reason,
                             "global_daily_limit")
            self.assertEqual(self.counts(), [[1], [1], [1], [1]])
        finally:
            restarted.dispose()

    def test_transaction_rollback_does_not_consume_quota(self):
        with self.assertRaises(RuntimeError):
            with self.sessions.begin() as session:
                check_and_increment(session, "ip", "device", 100, 999)
                raise RuntimeError("rollback")
        self.assertFalse(self.admit(limit=1, global_limit=1).blocked)
        self.assertEqual(self.counts(), [[1], [1], [1], [1]])

    def concurrent_admissions(self, same_client):
        if not self.postgres:
            self.skipTest("Real PostgreSQL required to prove cross-instance locking")
        engines = [self.new_engine(), self.new_engine()]
        factories = [build_session_factory(engine) for engine in engines]
        barrier = Barrier(12)
        def request(i):
            barrier.wait(timeout=15)
            identity = "shared" if same_client else str(i)
            return self.admit(identity, identity, limit=3 if same_client else 100,
                              global_limit=5, factory=factories[i % 2])
        try:
            with ThreadPoolExecutor(max_workers=12) as workers:
                results = list(workers.map(request, range(12)))
            accepted = 3 if same_client else 5
            self.assertEqual(sum(not result.blocked for result in results), accepted)
            self.assertEqual(self.counts()[0], [accepted])
            for counts in self.counts()[1:]:
                self.assertEqual(sum(counts), accepted)
        finally:
            for engine in engines:
                engine.dispose()

    def test_concurrent_first_creation_multiple_instances_global_limit(self):
        self.concurrent_admissions(same_client=False)

    def test_concurrent_first_creation_multiple_instances_personal_limit(self):
        self.concurrent_admissions(same_client=True)

    def test_http_429_no_upstream_and_endpoint_compatibility(self):
        with patch("app.settings.get_settings", return_value=Settings(
                api_key="test-only", database_url="sqlite:///:memory:")):
            main = importlib.import_module("app.main")
        for personal, global_limit, code, message in [
            (1, 10, "personal_daily_limit", "You have reached your daily request limit."),
            (100, 1, "global_daily_limit", "The weather service has reached its daily usage limit. Please try again later."),
        ]:
            # Separate dates avoid clearing any data between scenarios.
            day = date.today() + timedelta(days=10 if personal == 1 else 11)
            upstream = AsyncMock(return_value={"coord": {"lat": 1, "lon": 2}, "main": {"temp": 20}})
            with patch.object(main, "SessionLocal", self.sessions), patch.object(
                main, "settings", Settings(api_key="test-only", daily_limit=personal,
                                           global_daily_limit=global_limit)
            ), patch.object(main.client, "current_weather", upstream), patch("app.limit_store.date") as clock:
                clock.today.return_value = day
                client = TestClient(main.app)
                try:
                    self.assertEqual(client.get("/health").json(), {"status": "ok"})
                    self.assertEqual(client.get("/weather?lat=1&lon=2").status_code, 400)
                    self.assertEqual(client.get("/weather?lat=x&lon=2", headers={"X-Device-Id": "device"}).status_code, 422)
                    response = client.get("/weather?lat=1&lon=2", headers={"X-Device-Id": "device"})
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(set(response.json()), {"lat", "lon", "timezone", "current", "rate_limit"})
                    self.assertEqual(response.json()["current"]["temp"], 20)
                    denied = client.get("/weather?lat=1&lon=2", headers={"X-Device-Id": "device"})
                    self.assertEqual(denied.status_code, 429)
                    self.assertEqual(denied.json()["detail"]["code"], code)
                    self.assertEqual(denied.json()["detail"]["message"], message)
                    self.assertNotIn("global", str(denied.json()["detail"]["rate_limit"]))
                    upstream.assert_awaited_once()
                finally:
                    client.close()


class SettingsTests(unittest.TestCase):
    def test_independent_defaults_and_overrides(self):
        with patch.dict(os.environ, {"OPENWEATHER_API_KEY": "test-only", "DATABASE_URL": "sqlite://"}, clear=True):
            self.assertEqual((get_settings().daily_limit, get_settings().global_daily_limit), (100, 999))
            os.environ["DAILY_REQUEST_LIMIT"] = "7"
            self.assertEqual((get_settings().daily_limit, get_settings().global_daily_limit), (7, 999))
            os.environ["GLOBAL_DAILY_REQUEST_LIMIT"] = "12"
            self.assertEqual((get_settings().daily_limit, get_settings().global_daily_limit), (7, 12))
