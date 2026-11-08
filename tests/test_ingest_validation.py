import contextlib
import io
import json
import os
import secrets
import unittest
import test_security as fixture
from fastapi.testclient import TestClient
from database import SessionLocal
from models import SensorEvent
from main import app, GPSSensorIngestPayload


class IngestValidationTests(unittest.TestCase):
    def setUp(self):
        self.lifecycle = TestClient(app)
        self.client = self.lifecycle.__enter__()
        self.body = dict(event_id=secrets.token_hex(16),device_id='ESP32-S3-TRACKER-01',
            shipment_code='PRCL-2024-05-21-001',temperature=4.,humidity=45.,ldr_raw=3900)
        self.headers = {'x-device-key':os.environ['DEVICE_API_KEY']}

    def tearDown(self):
        self.lifecycle.__exit__(None,None,None)

    def test_field_boundaries_and_batch_unknown_fields(self):
        cases = dict(accel_g=10001,accel_x_g=-10001,gyro_dps=100001,shock_reading_g=-1,
            light_lux=1e10,boot_id='x'*65,sequence=-1,boot_counter=2**63,uptime_ms=-1,
            clock_source='x'*33,firmware_version='x'*65,temperature_age_ms=-1,
            shock_axis_mode='x'*33,light_measurement_kind='x'*65,signature_status='x'*65,
            warehouse_location='x'*129,arbitrary_extra={'nested':'unbounded'},
            signed_envelope={'record_b64':'x'*10925,'signature_b64':'x'*88})
        for name,value in cases.items():
            with self.subTest(name=name):
                response = self.client.post('/api/events',json={**self.body,name:value},headers=self.headers)
                self.assertEqual(response.status_code,422,response.text)
        self.assertEqual(self.client.post('/api/events/batch',json={'events':[self.body],'extra':1},headers=self.headers).status_code,422)
        self.assertEqual(self.client.post('/api/events/batch',json={'events':[self.body]*101},headers=self.headers).status_code,422)

    def test_body_caps_chunking_duplicate_json_and_content_type(self):
        headers = {**self.headers,'content-type':'application/json'}
        for path, count in [('/api/events',33000),('/api/events/batch',2098000)]:
            response = self.client.post(path,content=iter([b' '*10000]* (count//10000+1)),headers=headers)
            self.assertEqual(response.status_code,413,response.text)
            self.assertEqual(response.headers['cache-control'],'no-store')
        self.assertEqual(self.client.post('/api/events',content='{}',headers=self.headers).status_code,415)
        for raw in ('{"device_id":"first","device_id":"second"}','{"humidity":NaN}', '{'):
            self.assertEqual(self.client.post('/api/events',content=raw,headers=headers).status_code,422)
        headers['content-length']='40000'
        self.assertEqual(self.client.post('/api/events',content='{}',headers=headers).status_code,413)

    def test_credentials_never_echo_log_or_persist_and_cors_headers(self):
        secret = os.environ['DEVICE_API_KEY']
        output = io.StringIO()
        with contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):
            bad = self.client.post('/api/events',json={**self.body,'device_key':secret*10})
            self.assertEqual(bad.status_code,422)
            good = self.client.post('/api/events',json={**self.body,'api_key':secret})
            self.assertEqual(good.status_code,200,good.text)
        self.assertNotIn(secret,bad.text+good.text+output.getvalue())
        with SessionLocal() as db:
            stored = db.query(SensorEvent).filter_by(event_id=self.body['event_id']).one()
            self.assertNotIn(secret,stored.evidence_payload)
        for origin,allowed in [('https://evil.invalid',False),('http://localhost:5500',True)]:
            response = self.client.options('/api/events',headers={'Origin':origin,
                'Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'X-Device-Key'})
            self.assertEqual('access-control-allow-origin' in response.headers,allowed)
        response = self.client.get('/api/shipments')
        self.assertEqual(response.headers['x-frame-options'],'DENY')
        self.assertEqual(response.headers['x-content-type-options'],'nosniff')

    def test_legacy_body_key_retry_remains_idempotent_without_rewriting_history(self):
        import hashlib
        from evidence import canonical
        body = {**self.body,'api_key':os.environ['DEVICE_API_KEY']}
        self.assertEqual(self.client.post('/api/events',json=body).status_code,200)
        with SessionLocal() as db:
            row = db.query(SensorEvent).filter_by(event_id=self.body['event_id']).one()
            proof = json.loads(row.evidence_payload)
            # Reconstruct the old code's proof/digest, including its credential.
            proof['source']['api_key'] = body['api_key']
            proof['ingest_digest'] = hashlib.sha256(canonical(proof['source']).encode()).hexdigest()
            row.evidence_payload = canonical(proof)
            row.record_hash = hashlib.sha256(row.evidence_payload.encode()).hexdigest()
            historic_payload = row.evidence_payload
            db.commit()
        response = self.client.post('/api/events',json=body)
        self.assertEqual(response.status_code,200,response.text)
        self.assertTrue(response.json()['duplicate'])
        self.assertEqual(self.client.post('/api/events',json={**body,'temperature':5.}).status_code,409)
        with SessionLocal() as db:
            row = db.query(SensorEvent).filter_by(event_id=self.body['event_id']).one()
            self.assertEqual(row.evidence_payload,historic_payload)
