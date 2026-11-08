"""Cache freshness, access control, expiry and transaction boundaries."""
import os
import secrets
import unittest
from unittest.mock import patch
import test_security as fixture
from fastapi.testclient import TestClient
from sqlalchemy import event
from database import SessionLocal, engine
from models import Shipment
import main
from report_cache import MemoryTTLCache, RedisTTLCache, ReportCache


class CacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lifecycle = TestClient(fixture.app)
        cls.client = cls.lifecycle.__enter__()
        login = cls.client.post('/api/auth/login',json={'username':'admin','password':os.environ['BOOTSTRAP_ADMIN_PASSWORD']})
        cls.admin = {'Authorization':'Bearer '+login.json()['access_token']}
        login = cls.client.post('/api/auth/login',json={'username':'Rahul Sharma','password':os.environ['DEMO_USER_PASSWORD']})
        cls.user = {'Authorization':'Bearer '+login.json()['access_token']}

    @classmethod
    def tearDownClass(cls):
        cls.lifecycle.__exit__(None,None,None)
        engine.dispose()

    def report(self, cache):
        statements = []
        def track(*args):
            statements.append(args[2])
        with patch.object(main,'report_cache',cache):
            event.listen(engine,'before_cursor_execute',track)
            try:
                response = self.client.get('/api/reports/summary',headers=self.admin)
            finally:
                event.remove(engine,'before_cursor_execute',track)
        self.assertEqual(response.status_code,200,response.text)
        return response.json(), len(statements)

    def test_new_tamper_event_invalidates_two_independent_worker_caches(self):
        first, second = ReportCache(MemoryTTLCache()), ReportCache(MemoryTTLCache())
        before, _ = self.report(first)
        self.report(second)
        _, hit_calls = self.report(first)
        self.assertEqual(hit_calls,2)  # Authorization + authoritative revision.
        response = self.client.post('/api/events',headers={'x-device-key':os.environ['DEVICE_API_KEY']},
            json={'event_id':secrets.token_hex(16),'device_id':'ESP32-S3-TRACKER-01',
                  'shipment_code':'PRCL-2024-05-21-001','temperature':4.5,'humidity':45,'ldr_raw':0})
        self.assertEqual(response.status_code,200,response.text)
        for cache in (first,second):
            after, calls = self.report(cache)
            self.assertGreater(calls,2)
            self.assertEqual(after['total_events'],before['total_events']+1)
            self.assertGreater(after['active_alerts_count'],before['active_alerts_count'])
        alerts = self.client.get('/api/alerts',headers=self.admin).json()
        self.assertTrue(any(row['status']=='Active' and 'Seal' in row['alert_type'] for row in alerts))
        tamper = next(row for row in alerts if row['shipment_id']=='PRCL-2024-05-21-001'
                      and row['status']=='Active' and 'Seal' in row['alert_type'])
        self.client.put(f"/api/alerts/{tamper['id']}/resolve",headers=self.admin).raise_for_status()
        resolved, calls = self.report(first)
        self.assertGreater(calls,2)
        self.assertEqual(resolved['active_alerts_count'],after['active_alerts_count']-1)

    def test_bulk_commit_invalidates_but_rollback_retains_revision(self):
        cache = ReportCache(MemoryTTLCache())
        self.report(cache)
        with SessionLocal() as db:
            revision = cache.revision(db)
            db.query(Shipment).filter(Shipment.shipment_code=='PRCL-2024-05-21-001').update({'status':'Cache test'})
            db.rollback()
        with SessionLocal() as db:
            self.assertEqual(cache.revision(db),revision)
        self.assertEqual(self.report(cache)[1],2)
        with SessionLocal() as db:
            shipment = db.query(Shipment).filter(Shipment.shipment_code=='PRCL-2024-05-21-001').one()
            original = shipment.status
            db.query(Shipment).filter(Shipment.id==shipment.id).update({'status':'Cache test'})
            db.commit()
        try:
            fresh, calls = self.report(cache)
            self.assertGreater(calls,2)
            self.assertTrue(any(row['status']=='Cache test' for row in fresh['shipment_statuses']))
        finally:
            with SessionLocal() as db:
                db.query(Shipment).filter(Shipment.shipment_code=='PRCL-2024-05-21-001').update({'status':original})
                db.commit()

    def test_old_revision_fill_cannot_resurrect_after_a_write(self):
        cache = ReportCache(MemoryTTLCache())
        with SessionLocal() as db:
            old = cache.revision(db)
            shipment = db.query(Shipment).first()
            shipment.latest_humidity += .01
            db.commit()
        cache.put(old,{'outdated':True})
        with SessionLocal() as db:
            self.assertIsNone(cache.get(cache.revision(db)))

    def test_cache_errors_fall_back_and_metrics_remain_admin_only(self):
        class Broken:
            def get(self,key):
                raise ConnectionError('cache unavailable')
            def put(self,*args):
                raise ConnectionError('cache unavailable')
        cache = ReportCache(Broken())
        report, calls = self.report(cache)
        self.assertIn('total_events',report)
        self.assertGreater(calls,2)
        with patch.object(main,'report_cache',cache):
            self.assertEqual(self.client.get('/api/admin/cache-metrics').status_code,401)
            self.assertEqual(self.client.get('/api/admin/cache-metrics',headers=self.user).status_code,403)
            metrics = self.client.get('/api/admin/cache-metrics',headers=self.admin).json()
            self.assertEqual(metrics['misses'],1)
            self.assertEqual(metrics['errors'],2)
            self.assertEqual(self.client.get('/api/reports/summary',headers=self.user).status_code,403)


class CacheBackendTests(unittest.TestCase):
    def test_memory_expiry_bound_and_copy_isolation(self):
        now = [0]
        cache = MemoryTTLCache(clock=lambda:now[0],max_entries=1)
        cache.put('one',{'count':1},5)
        returned = cache.get('one')
        returned['count'] = 99
        self.assertEqual(cache.get('one')['count'],1)
        now[0] = 5
        self.assertIsNone(cache.get('one'))
        cache.put('one',{},5)
        cache.put('two',{},5)
        self.assertIsNone(cache.get('one'))

    def test_optional_redis_adapter_preserves_json_and_expiry(self):
        class FakeRedis:
            def set(self,key,value,px):
                self.saved = (key,value,px)
            def get(self,key):
                return self.saved[1].encode()
        fake = FakeRedis()
        cache = RedisTTLCache(fake)
        cache.put('revision-key',{'count':3},5)
        self.assertEqual(fake.saved[2],5000)
        self.assertEqual(cache.get('revision-key'),{'count':3})
