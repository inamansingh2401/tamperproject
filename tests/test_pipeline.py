"""Bounded synthetic signed events; isolated DB/outboxes, no cloud/hardware calls."""
import base64
import contextlib
import hashlib
import io
import json
import secrets
import sqlite3
import sys
import tempfile
import subprocess
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import test_security as fixture  # Establish isolated environment BEFORE importing main.
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils
from fastapi.testclient import TestClient
from database import SessionLocal
from evidence import export_record, verify_record
from models import SensorEvent

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'gateway'))
from gateway import Outbox, decode_record, send_one


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lifecycle = TestClient(fixture.app)
        cls.client = cls.lifecycle.__enter__()
        login = cls.client.post('/api/auth/login', json={'username':'admin', 'password':fixture.os.environ['BOOTSTRAP_ADMIN_PASSWORD']})
        cls.admin = {'Authorization':'Bearer ' + login.json()['access_token']}
        login = cls.client.post('/api/auth/login', json={'username':'Rahul Sharma', 'password':fixture.os.environ['DEMO_USER_PASSWORD']})
        cls.user = {'Authorization':'Bearer ' + login.json()['access_token']}
        cls.key = ec.generate_private_key(ec.SECP256R1())
        cls.public = cls.key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint).hex()
        cls.device = 'ESP32-S3-TRACKER-10'
        cls.shipment = 'PRCL-2024-05-21-010'
        response = cls.client.put(f'/api/devices/{cls.device}/assignment', json={'shipment_code':cls.shipment,'public_key':cls.public}, headers=cls.admin)
        assert response.status_code == 200, response.text
        cls.device_headers = {'x-device-key':fixture.os.environ['DEVICE_API_KEY']}

    @classmethod
    def tearDownClass(cls):
        cls.lifecycle.__exit__(None, None, None)
        fixture.engine.dispose()

    def payload(self, **updates):
        return {'event_id':secrets.token_hex(16),'device_id':self.device,'shipment_code':self.shipment,
                'temperature':4.5,'humidity':45.0,'ldr_raw':3900,'boot_id':'reboot-test','sequence':1, **updates}

    def envelope(self, payload):
        raw = json.dumps(payload, separators=(',', ':')).encode()
        der = self.key.sign(b'TrackSure:event:v1\0' + raw, ec.ECDSA(hashes.SHA256()))
        r, s = utils.decode_dss_signature(der)
        return {'record_b64':base64.b64encode(raw).decode(), 'signature_b64':base64.b64encode(r.to_bytes(32,'big')+s.to_bytes(32,'big')).decode(), 'signature_algorithm':'ECDSA_P256_SHA256','key_slot':0}

    def post(self, payload, **transport):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.client.post('/api/events', json={**payload,'signed_envelope':self.envelope(payload),**transport}, headers=self.device_headers)

    def test_a_signed_wifi_gateway_cloud_history_and_duplicate(self):
        with tempfile.TemporaryDirectory(prefix='tracksure-outbox-test-') as directory:
            keyfile = Path(directory) / 'public.txt'
            keyfile.write_text(self.public)
            config = {'device_id':self.device,'shipment_code':self.shipment,'public_key_file':str(keyfile),
                      'require_signature':True,'device_key':fixture.os.environ['DEVICE_API_KEY'],'cloud_url':'https://test.invalid'}
            outbox = Outbox(Path(directory) / 'outbox.db')
            payloads = [self.payload(sequence=i) for i in range(3)]
            for payload in payloads:
                original = json.dumps(self.envelope(payload)).encode()
                event_id, decoded, verified, signed = decode_record(original, config)
                self.assertTrue(outbox.enqueue(event_id, decoded, verified, signed))
                self.assertFalse(outbox.enqueue(event_id, decoded, verified, signed))
            # Gateway process restart: durable rows remain, all three reach API.
            outbox = Outbox(Path(directory) / 'outbox.db')
            requests = []
            testcase = self
            class Cloud:
                def post(self, url, json, headers):
                    requests.append(json['event_id'])
                    testcase.assertEqual(url, 'https://test.invalid/api/events')
                    with contextlib.redirect_stdout(io.StringIO()):
                        response = testcase.client.post('/api/events', json=json, headers=headers)
                    testcase.assertEqual(response.status_code, 200, response.text)
                    return response
            for _ in payloads:
                self.assertTrue(send_one(outbox, config, Cloud()))
            self.assertFalse(send_one(outbox, config, Cloud()))
            self.assertEqual(requests, [p['event_id'] for p in payloads])
            self.assertEqual(outbox.status()['counts'], {'sent':3})
            duplicate = self.post(payloads[0])
            self.assertEqual(duplicate.status_code, 200, duplicate.text)
            self.assertTrue(duplicate.json()['duplicate'])
            self.assertEqual(self.post({**payloads[0], 'temperature':8.5}).status_code, 409)
            page = self.client.get(f'/api/shipments/{self.shipment}/evidence', headers=self.admin).json()
            self.assertEqual(len(page['records']), 3)
            self.assertTrue(all(r['integrity']=='verified' and r['signature']=='verified' for r in page['verification']), page['verification'])
            detail = self.client.get(f'/api/shipments/{self.shipment}', headers=self.admin).json()
            self.assertEqual(len(detail['events']), 3)
            self.assertEqual(detail['shipment']['bound_device_ids'], [self.device])

    def test_b_enrollment_and_shipment_boundaries(self):
        self.assertEqual(self.client.get('/api/devices', headers=self.user).status_code, 403)
        self.assertEqual(self.client.get(f'/api/shipments/{self.shipment}/evidence', headers=self.user).status_code, 403)
        payload = self.payload(shipment_code='PRCL-2024-05-21-009')
        self.assertEqual(self.post(payload).status_code, 403)
        payload = self.payload()
        bad = self.envelope(payload)
        bad['signature_b64'] = base64.b64encode(bytes(64)).decode()
        self.assertEqual(self.client.post('/api/events', json={**payload,'signed_envelope':bad}, headers=self.device_headers).status_code, 422)
        self.assertEqual(self.client.post('/api/events', json=payload, headers=self.device_headers).status_code, 422)
        bad = self.envelope(payload)
        self.assertEqual(self.client.post('/api/events', json={**payload,'temperature':99,'signed_envelope':bad}, headers=self.device_headers).status_code, 422)
        response = self.client.put(f'/api/devices/{self.device}/assignment', json={'shipment_code':'PRCL-2024-05-21-009','public_key':self.public}, headers=self.admin)
        self.assertEqual(response.status_code, 409)

    def test_c_tampered_storage_and_chain_are_detected(self):
        self.assertEqual(self.post(self.payload()).status_code, 200)
        with SessionLocal() as db:
            event = db.query(SensorEvent).filter(SensorEvent.device_id == self.device).order_by(SensorEvent.id.desc()).first()
            record = export_record(event)
        self.assertEqual(verify_record(record)['signature'], 'verified')
        altered = {**record,'temperature':99.0}
        self.assertEqual(verify_record(altered)['integrity'], 'invalid')
        altered = {**record,'evidence_payload':record['evidence_payload'].replace('reboot-test','altered-boot')}
        self.assertEqual(verify_record(altered)['integrity'], 'invalid')
        self.assertEqual(verify_record(record, 'a'*64)['integrity'], 'invalid')
        changed_proof = json.loads(record['evidence_payload'])
        changed_proof['event']['accel_g'] = 99.0
        changed_bytes = json.dumps(changed_proof)
        altered = {**record,'accel_g':99.0,'evidence_payload':changed_bytes,'record_hash':hashlib.sha256(changed_bytes.encode()).hexdigest()}
        self.assertEqual(verify_record(altered)['integrity'], 'invalid')
        self.assertEqual(verify_record(record, expected_shipment='WRONG')['integrity'], 'invalid')
        # Independent verifier operates on an exported file without API/database.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'evidence.json'
            path.write_text(json.dumps({'records':[record], 'anchor_previous_hash':record['previous_hash']}))
            result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1]/'Tamper_admin/backend/evidence.py'), str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['signature_verified'], 1)

    def test_d_delayed_replay_does_not_overwrite_live_cards(self):
        fresh = self.payload(temperature=4.0)
        self.assertEqual(self.post(fresh).status_code, 200)
        old = self.payload(temperature=50.0,ldr_raw=0)
        then = (datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
        response = self.post(old, gateway_received_at=then)
        self.assertEqual(response.status_code, 200, response.text)
        live = self.client.get(f'/api/shipments/{self.shipment}/live', headers=self.admin).json()
        self.assertEqual(live['latest_telemetry']['event_id'], fresh['event_id'])
        self.assertEqual(live['shipment']['health_level'], 'Optimal')
        self.assertEqual(live['shipment']['seal_status'], 'INTACT')
        first = self.client.get(f'/api/shipments/{self.shipment}/evidence?limit=1', headers=self.admin).json()
        second = self.client.get(f"/api/shipments/{self.shipment}/evidence?after_id={first['next_after_id']}&limit=1", headers=self.admin).json()
        self.assertEqual(second['anchor_previous_hash'], first['records'][-1]['record_hash'])

    def test_e_gateway_retry_preserves_all_records(self):
        with tempfile.TemporaryDirectory() as directory:
            outbox = Outbox(Path(directory)/'outbox.db')
            for event_id in ['first','second']:
                outbox.enqueue(event_id, {'event_id':event_id}, False, '{}')
            class Unavailable:
                def post(self, *_args, **_kwargs):
                    import httpx
                    return httpx.Response(503)
            self.assertTrue(send_one(outbox, {'cloud_url':'https://test.invalid','device_key':'test'}, Unavailable()))
            self.assertEqual(outbox.status()['counts'], {'queued':2})
            self.assertIsNone(outbox.pending())  # Oldest waits; second cannot overtake.

    def test_f_device_reuse_keeps_old_history_and_routes_new_readings(self):
        old = self.payload()
        self.assertEqual(self.post(old).status_code, 200)
        target = 'PRCL-2024-05-21-009'
        response = self.client.put(f'/api/devices/{self.device}/assignment', json={'shipment_code':target,'public_key':self.public,'confirm_drained':True}, headers=self.admin)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.post(self.payload()).status_code, 403)
        self.assertTrue(self.post(old).json()['duplicate'])  # Lost cloud ACK can still be recovered.
        new = self.payload(shipment_code=target, boot_id='new-use', sequence=0)
        self.assertEqual(self.post(new).status_code, 200)
        live = self.client.get(f'/api/shipments/{target}/live', headers=self.admin).json()
        self.assertEqual(live['latest_telemetry']['event_id'], new['event_id'])
        history = self.client.get(f'/api/shipments/{self.shipment}/evidence', headers=self.admin).json()
        self.assertIn(old['event_id'], [r['event_id'] for r in history['records']])

    def test_g_legacy_hashes_are_checked_without_inventing_signatures(self):
        record = {'id':1,'event_id':None,'shipment_id':1,'device_id':'legacy','light_lux':0.0,
                  'temperature':4.5,'humidity':45.0,'accel_g':1.0,'previous_hash':'0'*64}
        record['record_hash'] = hashlib.sha256(f"1|legacy|0|4.5|45|1|{'0'*64}".encode()).hexdigest()
        result = verify_record(record, '0'*64)
        self.assertEqual(result['integrity'], 'verified')
        self.assertEqual(result['signature'], 'unavailable')
        self.assertEqual(verify_record({**record,'temperature':99})['integrity'], 'invalid')

    def test_h_startup_preserves_operator_vehicle_assignments(self):
        from models import Vehicle
        from main import startup_db_seed
        with SessionLocal() as db:
            vehicle = db.query(Vehicle).filter(Vehicle.vehicle_code=='TRK-MH-001').first()
            vehicle.assigned_shipments = '["OPERATOR-ASSIGNED"]'
            db.commit()
        startup_db_seed()
        with SessionLocal() as db:
            vehicle = db.query(Vehicle).filter(Vehicle.vehicle_code=='TRK-MH-001').first()
            self.assertEqual(vehicle.assigned_shipments, '["OPERATOR-ASSIGNED"]')

    def test_i_signed_capture_timestamp_keeps_offline_history_honest(self):
        # Device is assigned to 009 by the preceding reuse test.
        then = datetime.now(timezone.utc)-timedelta(days=1)
        payload = self.payload(shipment_code='PRCL-2024-05-21-009', captured_at_ms=int(then.timestamp()*1000),clock_source='sntp')
        response = self.post(payload)
        self.assertEqual(response.status_code,200,response.text)
        with SessionLocal() as db:
            event = db.query(SensorEvent).filter(SensorEvent.event_id==payload['event_id']).first()
            self.assertLess(abs((event.created_at-then.replace(tzinfo=None)).total_seconds()),0.01)
            record=export_record(event)
        self.assertEqual(verify_record(record)['integrity'],'verified')
        shifted=then.replace(tzinfo=None)+timedelta(hours=1)
        proof=json.loads(record['evidence_payload'])
        proof['event']['created_at']=shifted.isoformat()
        body=json.dumps(proof)
        altered={**record,'created_at':shifted.isoformat(),'evidence_payload':body,'record_hash':hashlib.sha256(body.encode()).hexdigest()}
        self.assertEqual(verify_record(altered)['integrity'],'invalid')
        detail = self.client.get('/api/shipments/PRCL-2024-05-21-009',headers=self.admin).json()
        old = next(r for r in detail['events'] if r['event_id']==payload['event_id'])
        self.assertEqual(old['light_unit'],'RELATIVE')
        self.assertEqual(old['time_quality'],'device_sntp')

    def test_j_outbox_health_and_recovery_inspection_do_not_mutate_rows(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'operations'))
        from inspect_outbox import inspect_outbox
        with tempfile.TemporaryDirectory(prefix='tracksure-inspection-') as directory:
            path=Path(directory)/'outbox.db'
            outbox=Outbox(path)
            payload=self.payload()
            outbox.enqueue(payload['event_id'],payload,True,json.dumps(self.envelope(payload)))
            outbox.mark(payload['event_id'],'blocked','Cloud HTTP 401')
            health=outbox.status()
            self.assertEqual(health['counts'],{'blocked':1})
            self.assertIsNotNone(health['last_verified_receipt_age_seconds'])
            self.assertIsNone(health['last_cloud_ack_age_seconds'])
            with outbox.connect() as db:
                before=[tuple(r) for r in db.execute('SELECT * FROM outbox')]
            inventory=inspect_outbox(path)
            self.assertTrue(inventory['read_only'])
            self.assertFalse(inventory['recovery_applied'])
            self.assertEqual(inventory['integrity'],'ok')
            self.assertEqual(len(inventory['recovery_candidates_first_20']),1)
            self.assertNotIn('original',inventory['recovery_candidates_first_20'][0])
            with outbox.connect() as db:
                self.assertEqual(before,[tuple(r) for r in db.execute('SELECT * FROM outbox')])

    def test_k_reports_are_calculated_from_stored_readings(self):
        self.assertEqual(self.client.get('/api/reports/summary',headers=self.user).status_code,403)
        report=self.client.get('/api/reports/summary',headers=self.admin).json()
        with SessionLocal() as db:
            events=db.query(SensorEvent).filter(SensorEvent.temperature.isnot(None)).all()
        in_range=sum(2<=event.temperature<=8 for event in events)
        self.assertEqual(report['temperature_readings'],len(events))
        self.assertEqual(report['temperature_in_range'],in_range)
        self.assertEqual(report['compliance_percentage'],round(100*in_range/len(events),2))
        self.assertEqual(sum(row['count'] for row in report['shipment_statuses']),report['total_shipments'])
        self.assertEqual(sum(row['count'] for row in report['vehicle_statuses']),report['total_vehicles'])
        self.assertIsNone(report['on_time_delivery_percentage'])

    def test_l_http_ingest_ack_and_health_in_isolated_local_only_gateway(self):
        import httpx
        import socket
        import time
        with tempfile.TemporaryDirectory(prefix='tracksure-lan-test-') as directory:
            scratch=Path(directory)
            public=scratch/'public.txt';public.write_text(self.public)
            with socket.socket() as reserve:
                reserve.bind(('127.0.0.1',0));port=reserve.getsockname()[1]
            config={'device_id':self.device,'shipment_code':self.shipment,'public_key_file':str(public),
                    'require_signature':False,'cloud_url':'https://test.invalid','device_key':'isolated-test-only',
                    'lan_bind':'127.0.0.1','lan_port':port}
            config_file=scratch/'gateway.local.json';config_file.write_text(json.dumps(config))
            outbox_file=scratch/'outbox.db'
            command=[sys.executable,str(Path(__file__).resolve().parents[1]/'gateway/gateway.py'),
                     '--config',str(config_file),'--outbox',str(outbox_file),'--log-file',str(scratch/'gateway.local.log'),
                     '--local-only','--max-wifi-ingest','1']
            process=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                with httpx.Client(timeout=3) as client:
                    health=None
                    for _ in range(40):
                        if process.poll() is not None:
                            self.fail('Isolated gateway exited before listener was ready')
                        try:
                            response=client.get(f'http://127.0.0.1:{port}/status')
                            if response.status_code==200:
                                health=response.json();break
                        except httpx.HTTPError:
                            time.sleep(0.1)
                    self.assertIsNotNone(health)
                    self.assertTrue(health['signature_required'])
                    self.assertFalse(health['cloud_upload_enabled'])
                    self.assertFalse(health['cloud_worker_alive'])
                    payload=self.payload()
                    self.assertEqual(client.post(f'http://127.0.0.1:{port}/ingest',json=payload).status_code,400)
                    response=client.post(f'http://127.0.0.1:{port}/ingest',json=self.envelope(payload))
                    self.assertEqual(response.status_code,200,response.text)
                    self.assertEqual(response.json()['event_id'],payload['event_id'])
                process.wait(timeout=8)
                self.assertEqual(process.returncode,0)
                outbox=Outbox(outbox_file)
                self.assertEqual(outbox.status()['counts'],{'queued':1})
                with outbox.connect() as db:
                    row=db.execute('SELECT event_id,verified FROM outbox').fetchone()
                    self.assertEqual(row['event_id'],payload['event_id'])
                    self.assertEqual(row['verified'],1)
            finally:
                if process.poll() is None:
                    process.terminate();process.wait(timeout=8)


if __name__ == '__main__':
    unittest.main()
