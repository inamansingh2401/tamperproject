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


