"""Local software-signed replay and lifecycle regressions."""
import base64
import json
import os
import secrets
import time
import unittest
import test_security as fixture
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils
from fastapi.testclient import TestClient
from database import SessionLocal
from models import Device, Shipment, SensorEvent, ShipmentAlert, DeviceReplayNonce
import main


class DeviceSecurityTests(unittest.TestCase):
    def setUp(self):
        self.lifecycle = TestClient(main.app)
        self.client = self.lifecycle.__enter__()
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.point = self.key.public_key().public_bytes(serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint).hex()
        self.name = 'SEC-' + secrets.token_hex(8)
        self.secret = secrets.token_urlsafe(32)
        self.headers = {'x-device-key':self.secret}
        with SessionLocal() as db:
            ship = Shipment(shipment_code=self.name)
            db.add(ship)
            db.add(Device(device_id=self.name,api_key=self.secret,public_key=self.point,
                shipment_code=self.name,replay_policy='counter_v1'))
            db.commit()
            self.shipment_id = ship.id

    def tearDown(self):
        with SessionLocal() as db:
            for model, expression in [(DeviceReplayNonce,DeviceReplayNonce.device_id==self.name),
                (SensorEvent,SensorEvent.shipment_id==self.shipment_id),
                (ShipmentAlert,ShipmentAlert.shipment_id==self.shipment_id),
                (Device,Device.device_id==self.name),(Shipment,Shipment.id==self.shipment_id)]:
                db.query(model).filter(expression).delete()
            db.commit()
        self.lifecycle.__exit__(None,None,None)

    def signed(self, **updates):
        body = dict(event_id=secrets.token_hex(16),device_id=self.name,shipment_code=self.name,
            temperature=4.,humidity=45.,ldr_raw=3900,key_version=1,boot_counter=1,
            sequence=1,captured_at_ms=int(time.time()*1000))
        body.update(updates)
        raw = json.dumps(body,separators=(',',':')).encode()
        r,s = utils.decode_dss_signature(self.key.sign(b'TrackSure:event:v1\0'+raw,ec.ECDSA(hashes.SHA256())))
        return {**body,'signed_envelope':dict(record_b64=base64.b64encode(raw).decode(),
            signature_b64=base64.b64encode(r.to_bytes(32,'big')+s.to_bytes(32,'big')).decode())}

    def post(self, body):
        return self.client.post('/api/events',json=body,headers=self.headers)

    def test_replay_retry_and_counter_reuse(self):
        body = self.signed()
        first = self.post(body)
        self.assertEqual(first.status_code,200,first.text)
        # Lost ACK: original identity succeeds without adding a second row/counter.
        again = self.post(body)
        self.assertTrue(again.json()['duplicate'])
        self.assertEqual(again.json()['event_hash'], first.json()['event_hash'])
        self.assertEqual(self.post(self.signed()).status_code,409)
        with SessionLocal() as db:
            self.assertEqual(db.query(SensorEvent).filter_by(shipment_id=self.shipment_id).count(),1)

    def test_reordered_and_delayed_requests(self):
        self.assertEqual(self.post(self.signed(sequence=600)).status_code,200)
        # Offline, previously unseen sequence within window is valid.
        self.assertEqual(self.post(self.signed(sequence=599,captured_at_ms=int((time.time()-86400)*1000))).status_code,200)
        self.assertEqual(self.post(self.signed(sequence=1)).status_code,409)
        self.assertEqual(self.post(self.signed(sequence=601,captured_at_ms=int((time.time()-604801)*1000))).status_code,409)
        self.assertEqual(self.post(self.signed(sequence=602,captured_at_ms=int((time.time()+301)*1000))).status_code,409)

    def test_retry_after_window_expiry_and_atomic_batch_rollback(self):
        from unittest.mock import patch
        body = self.signed()
        self.assertEqual(self.post(body).status_code,200)
        with patch('device_security.time.time',return_value=time.time()+700000):
            self.assertTrue(self.post(body).json()['duplicate'])
        good,bad = self.signed(sequence=2),self.signed(sequence=2)
        response = self.client.post('/api/events/batch',json={'events':[good,bad]},headers=self.headers)
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.post(good).status_code,200)  # Rolled-back nonce was not consumed.

    def test_missing_epoch_and_old_boot_are_rejected(self):
        self.assertEqual(self.post(self.signed(key_version=None)).status_code,422)
        self.assertEqual(self.post(self.signed(key_version=2)).status_code,409)
        self.assertEqual(self.post(self.signed(boot_counter=20)).status_code,200)
        self.assertEqual(self.post(self.signed(boot_counter=1,sequence=2)).status_code,409)
