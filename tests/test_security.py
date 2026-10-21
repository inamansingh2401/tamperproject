"""Security regressions against an isolated temporary database; never contacts Render."""
import contextlib
import io
import os
from pathlib import Path
import secrets
import sys
import tempfile
import unittest

scratch = tempfile.TemporaryDirectory(prefix="tracksure-security-")
test_url = os.getenv('SAFETRACK_TEST_DATABASE_URL')
if test_url:
    from sqlalchemy import create_engine, inspect
    from sqlalchemy.engine import make_url
    url = make_url(test_url)
    if url.drivername != 'postgresql+psycopg' or url.host not in ('127.0.0.1','localhost') or url.database != 'safetrack_test':
        raise RuntimeError('Tests require a fresh loopback PostgreSQL safetrack_test database')
    probe = create_engine(url)
    try:
        if inspect(probe).get_table_names():
            raise RuntimeError('Refusing to run tests against a non-empty database')
    finally:
        probe.dispose()
os.environ["DATABASE_URL"] = test_url or "sqlite:///" + (Path(scratch.name) / "test.db").as_posix()
os.environ["SAFETRACK_ENV"] = "production"
os.environ["JWT_SECRET"] = secrets.token_urlsafe(48)
os.environ["DEVICE_API_KEY"] = secrets.token_urlsafe(48)
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = secrets.token_urlsafe(24)
os.environ["DEMO_USER_PASSWORD"] = secrets.token_urlsafe(24)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Tamper_admin" / "backend"))
from fastapi.testclient import TestClient
from main import app
from database import engine


class SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lifecycle = TestClient(app)
        cls.client = cls.lifecycle.__enter__()
        response = cls.client.post("/api/auth/login", json={"username": "Rahul Sharma", "password": os.environ["DEMO_USER_PASSWORD"]})
        assert response.status_code == 200, response.text
        cls.user_headers = {"Authorization": "Bearer " + response.json()["access_token"]}

    @classmethod
    def tearDownClass(cls):
        cls.lifecycle.__exit__(None, None, None)
        engine.dispose()
        scratch.cleanup()

    def payload(self):
        return {"event_id": secrets.token_hex(16), "device_id": "ESP32-S3-TRACKER-01", "shipment_code": "PRCL-2024-05-21-001", "temperature": 31, "humidity": 56, "ldr_raw": 3900}

    def test_read_requires_login(self):
        self.assertEqual(self.client.get("/api/shipments").status_code, 401)

    def test_role_and_shipment_boundaries(self):
        self.assertEqual(self.client.get("/api/users", headers=self.user_headers).status_code, 403)
        self.assertEqual(self.client.get("/api/shipments/PRCL-2024-05-21-002", headers=self.user_headers).status_code, 403)
        self.assertEqual(self.client.get("/api/shipments/PRCL-2024-05-21-001", headers=self.user_headers).status_code, 200)

    def test_shared_portal_live_and_admin_boundaries(self):
        self.assertEqual(self.client.get("/api/shipments/PRCL-2024-05-21-001/live").status_code, 401)
        self.assertEqual(self.client.get("/api/admin/dashboard", headers=self.user_headers).status_code, 403)
        self.assertEqual(self.client.get("/api/shipments/PRCL-2024-05-21-002/live", headers=self.user_headers).status_code, 403)
        self.assertEqual(self.client.get("/api/shipments/PRCL-2024-05-21-001/live", headers=self.user_headers).status_code, 200)

    def test_device_key_is_never_logged(self):
        buffer = io.StringIO()
        rejected_key = secrets.token_hex(24)
        with contextlib.redirect_stdout(buffer):
            result = self.client.post("/api/events", json=self.payload(), headers={"x-device-key": rejected_key})
        self.assertEqual(result.status_code, 401)
        self.assertNotIn(rejected_key, buffer.getvalue())
        self.assertNotIn(os.environ["DEVICE_API_KEY"], buffer.getvalue())

    def test_reading_validation_and_duplicate(self):
        payload = self.payload()
        headers = {"x-device-key": os.environ["DEVICE_API_KEY"]}
        self.assertEqual(self.client.post("/api/events", json={**payload, "humidity": 101}, headers=headers).status_code, 422)
        self.assertEqual(self.client.post("/api/events", json={**payload, "ldr_raw": -1}, headers=headers).status_code, 422)
        self.assertEqual(self.client.post("/api/events", json={**payload, "temperature": "NaN"}, headers=headers).status_code, 422)
        self.assertEqual(self.client.post("/api/events", json=payload, headers=headers).status_code, 200)
        response = self.client.post("/api/events", json=payload, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["duplicate"])
        conflict = self.client.post("/api/events", json={**payload, "device_id": "ESP32-S3-TRACKER-02"}, headers=headers)
        self.assertEqual(conflict.status_code, 409)

    def test_ldr_dark_and_exposed_polarity(self):
        headers = {"x-device-key": os.environ["DEVICE_API_KEY"]}
        for raw, exposed in [(4095, False), (3900, False), (127, True), (0, True), (4095, False)]:
            response = self.client.post("/api/events", json={**self.payload(), "ldr_raw": raw}, headers=headers)
            self.assertEqual(response.status_code, 200)
            value = response.json()
            self.assertEqual(value["is_light_detected"], exposed)
            self.assertEqual(value["seal_status"], "COMPROMISED" if exposed else "INTACT")
            self.assertEqual(value["effective_light"] > 800, exposed)
            live = self.client.get("/api/shipments/PRCL-2024-05-21-001/live", headers=self.user_headers).json()
            self.assertAlmostEqual(live["latest_telemetry"]["light_lux"], value["effective_light"])

    def test_cors_allows_only_configured_origin(self):
        headers = {"Origin": "https://untrusted.example", "Access-Control-Request-Method": "GET"}
        response = self.client.options("/api/shipments", headers=headers)
        self.assertNotIn("access-control-allow-origin", response.headers)
        headers["Origin"] = "https://safetrack-admin-live-mu.vercel.app"
        self.assertEqual(self.client.options("/api/shipments", headers=headers).headers["access-control-allow-origin"], headers["Origin"])

    def test_private_responses_are_not_cached(self):
        response = self.client.get("/api/shipments", headers=self.user_headers)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")


if __name__ == "__main__":
    unittest.main()
