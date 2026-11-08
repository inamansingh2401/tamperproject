"""Signed retries, batch atomicity/ordering and admission of critical records."""
import base64
from datetime import datetime, timezone
import json
import os
import secrets
import unittest
from unittest.mock import patch
import test_security as fixture
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils
from fastapi.testclient import TestClient
from database import engine, SessionLocal
from models import Device, Shipment, SensorEvent, ShipmentAlert
from evidence import export_record, verify_record
from ingest_limits import IngestLimits
import main
import httpx


class IngestionFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lifecycle = TestClient(main.app)
        cls.client = cls.lifecycle.__enter__()
        cls.key = ec.generate_private_key(ec.SECP256R1())
        point = cls.key.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint).hex()
        with SessionLocal() as db:
            shipment = Shipment(shipment_code='PHASE3-SHIPMENT')
            db.add(shipment)
            db.add(Device(device_id='PHASE3-DEVICE',api_key=os.environ['DEVICE_API_KEY'],
                          shipment_code='PHASE3-SHIPMENT',public_key=point))
            db.commit()
            cls.shipment_id = shipment.id
        cls.headers = {'x-device-key':os.environ['DEVICE_API_KEY']}

    @classmethod
    def tearDownClass(cls):
        with SessionLocal() as db:
            db.query(SensorEvent).filter(SensorEvent.shipment_id==cls.shipment_id).delete()
            db.query(ShipmentAlert).filter(ShipmentAlert.shipment_id==cls.shipment_id).delete()
            db.query(Device).filter(Device.device_id=='PHASE3-DEVICE').delete()
            db.query(Shipment).filter(Shipment.id==cls.shipment_id).delete()
            db.commit()
        cls.lifecycle.__exit__(None,None,None)
        engine.dispose()

    def signed(self, **updates):
        payload = dict(event_id=secrets.token_hex(16),device_id='PHASE3-DEVICE',
            shipment_code='PHASE3-SHIPMENT',temperature=4.5,humidity=45.,ldr_raw=3900)
        payload.update(updates)
        raw = json.dumps(payload,separators=(',',':')).encode()
        signature = self.key.sign(b'TrackSure:event:v1\0'+raw,ec.ECDSA(hashes.SHA256()))
        r,s = utils.decode_dss_signature(signature)
        return {**payload,'signed_envelope':dict(record_b64=base64.b64encode(raw).decode(),
            signature_b64=base64.b64encode(r.to_bytes(32,'big')+s.to_bytes(32,'big')).decode())}

    def chain(self):
        with SessionLocal() as db:
            records = [export_record(row) for row in db.query(SensorEvent).filter(
                SensorEvent.shipment_id==self.shipment_id).order_by(SensorEvent.id)]
        previous = '0'*64
        for record in records:
            self.assertEqual(verify_record(record,previous,'PHASE3-SHIPMENT')['integrity'],'verified')
            previous = record['record_hash']
        return records




    def test_a_timeout_retry_and_delayed_capture_preserve_chain(self):
        stamp = int(datetime.now(timezone.utc).timestamp()*1000)-5000
        newest = self.signed(captured_at_ms=stamp,temperature=6.)
        older = self.signed(captured_at_ms=stamp-1000,temperature=3.)
        with self.assertRaises(httpx.ReadTimeout):
            response = self.client.post('/api/events',json=newest,headers=self.headers)
            self.assertEqual(response.status_code,200,response.text)
            raise httpx.ReadTimeout('Injected lost acknowledgment after commit')
        retry = self.client.post('/api/events',json=newest,
            headers={**self.headers,'Idempotency-Key':newest['event_id']})
        self.assertTrue(retry.json()['duplicate'])
        self.assertEqual(retry.json()['event_hash'],response.json()['event_hash'])
        self.assertEqual(self.client.post('/api/events',json=older,headers=self.headers).status_code,200)
        records = self.chain()
        self.assertEqual(sum(row['event_id'] in (newest['event_id'],older['event_id']) for row in records),2)
        with SessionLocal() as db:
            self.assertEqual(db.get(Shipment,self.shipment_id).latest_temperature,6.)

    def test_header_only_legacy_idempotency_and_changed_readings_conflict(self):
        body = dict(device_id='ESP32-S3-TRACKER-01',shipment_code='PRCL-2024-05-21-001',
                    temperature=4.5,humidity=45.,ldr_raw=3900)
        headers = {**self.headers,'Idempotency-Key':secrets.token_hex(16)}
        self.assertEqual(self.client.post('/api/events',json=body,headers=headers).status_code,200)
        self.assertTrue(self.client.post('/api/events',json=body,headers=headers).json()['duplicate'])
        self.assertEqual(self.client.post('/api/events',json={**body,'temperature':7.},headers=headers).status_code,409)



    def test_batch_retry_and_out_of_order_capture_preserve_chain(self):
        stamp = int(datetime.now(timezone.utc).timestamp()*1000)-5000
        newest = self.signed(captured_at_ms=stamp,temperature=6.)
        older = self.signed(captured_at_ms=stamp-1000,temperature=3.)
        batch = {'events':[newest,older]}
        response = self.client.post('/api/events/batch',json=batch,headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        first_hashes = [r['event_hash'] for r in response.json()['results']]
        # Client loses/ignores the successful response, then retries identical IDs.
        retry = self.client.post('/api/events/batch',json=batch,headers=self.headers)
        self.assertEqual(retry.status_code,200,retry.text)
        self.assertTrue(all(row['duplicate'] for row in retry.json()['results']))
        self.assertEqual([r['event_hash'] for r in retry.json()['results']],first_hashes)
        records = self.chain()
        self.assertEqual(sum(row['event_id'] in (newest['event_id'],older['event_id']) for row in records),2)
        with SessionLocal() as db:
            shipment = db.get(Shipment,self.shipment_id)
            self.assertEqual(shipment.latest_temperature,6.)

    def test_bad_batch_rolls_back_and_requires_bounded_single_device_events(self):
        first = self.signed()
        corrupt = self.signed()
        corrupt['temperature'] = 99.
        response = self.client.post('/api/events/batch',json={'events':[first,corrupt]},headers=self.headers)
        self.assertEqual(response.status_code,422,response.text)
        with SessionLocal() as db:
            self.assertIsNone(db.query(SensorEvent).filter(SensorEvent.event_id==first['event_id']).first())
        for items in ([], [self.signed()]*101):
            self.assertEqual(self.client.post('/api/events/batch',json={'events':items},headers=self.headers).status_code,422)
        self.chain()

    def test_ordinary_quotas_cannot_reject_critical_records_or_retries(self):
        limits = IngestLimits(device_burst=1,ip_burst=1,failure_burst=1,clock=lambda:0)
        with patch.object(main,'ingest_limits',limits):
            first = self.signed()
            accepted = self.client.post('/api/events',json=first,headers=self.headers)
            self.assertEqual(accepted.status_code,200)
            replay = self.client.post('/api/events',json=first,headers={**self.headers,'Idempotency-Key':first['event_id']})
            self.assertTrue(replay.json()['duplicate'])
            limited = self.client.post('/api/events',json=self.signed(),headers=self.headers)
            self.assertEqual(limited.status_code,429)
            self.assertGreater(int(limited.headers['Retry-After']),0)
            for _ in range(2):
                self.client.post('/api/events',json=self.signed(),headers={'x-device-key':'invalid-fixture-key'})
            critical = self.signed(ldr_raw=0)
            response = self.client.post('/api/events/batch',json={'events':[self.signed(),critical]},headers=self.headers)
            self.assertEqual(response.status_code,207,response.text)
            self.assertEqual([row['status_code'] for row in response.json()['results']],[429,200])
        self.chain()


class LimiterTests(unittest.TestCase):
    def test_failed_auth_budget_and_shared_ip_do_not_block_critical_lane(self):
        clock = [0.]
        limits = IngestLimits(device_burst=1,ip_burst=2,failure_burst=1,clock=lambda:clock[0])
        self.assertEqual(limits.failed_auth('shared'),0)
        self.assertGreater(limits.failed_auth('shared'),0)
        self.assertEqual(limits.telemetry('one','shared',False),0)
        self.assertGreater(limits.telemetry('one','shared',False),0)
        self.assertEqual(limits.telemetry('two','shared',False),0)
        self.assertGreater(limits.telemetry('three','shared',False),0)
        self.assertEqual(limits.telemetry('three','shared',True),0)
        clock[0] += 1
        self.assertEqual(limits.telemetry('three','shared',False),0)
