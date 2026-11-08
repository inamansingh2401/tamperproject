"""Request-level query budgets and pagination, using the isolated test fixture."""
import os
import unittest
import test_security as fixture
from fastapi.testclient import TestClient
from sqlalchemy import event
from database import engine, SessionLocal
from models import Shipment, ShipmentAlert


class QueryCountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lifecycle = TestClient(fixture.app)
        cls.client = cls.lifecycle.__enter__()
        response = cls.client.post('/api/auth/login', json={
            'username': 'admin', 'password': os.environ['BOOTSTRAP_ADMIN_PASSWORD']})
        cls.headers = {'Authorization': 'Bearer ' + response.json()['access_token']}
        with SessionLocal() as db:
            shipment = db.query(Shipment).first()
            cls.code = shipment.shipment_code
            cls.rows = [ShipmentAlert(shipment_id=shipment.id, alert_type='Query budget',
                        message='isolated fixture') for _ in range(105)]
            db.add_all(cls.rows)
            db.commit()
            cls.ids = [row.id for row in cls.rows]

    @classmethod
    def tearDownClass(cls):
        with SessionLocal() as db:
            db.query(ShipmentAlert).filter(ShipmentAlert.id.in_(cls.ids)).delete(synchronize_session=False)
            db.commit()
        cls.lifecycle.__exit__(None, None, None)
        engine.dispose()

    def request_with_budget(self, path, expected):
        statements = []
        def count(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)
        event.listen(engine, 'before_cursor_execute', count)
        try:
            response = self.client.get(path, headers=self.headers)
        finally:
            event.remove(engine, 'before_cursor_execute', count)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(statements), expected, statements)
        return response.json()

    def test_alerts_have_constant_two_query_budget_and_keyset_pages(self):
        page = self.request_with_budget('/api/alerts?limit=100', 2)
        self.assertEqual(len(page), 100)
        second = self.request_with_budget('/api/alerts?limit=100&before_id='+str(page[-1]['id']), 2)
        self.assertTrue(second)
        self.assertTrue(set(row['id'] for row in page).isdisjoint(row['id'] for row in second))
        self.assertEqual([row['id'] for row in page], sorted((row['id'] for row in page), reverse=True))
        self.assertEqual(page[0]['shipment_id'], self.code)
        self.assertEqual(len(self.client.get('/api/alerts',headers=self.headers).json()), 100)
        for query in ('limit=0','limit=501','before_id=0'):
            self.assertEqual(self.client.get('/api/alerts?'+query,headers=self.headers).status_code,422)

    def test_shipments_have_constant_two_query_budget_with_missing_vehicle(self):
        with SessionLocal() as db:
            db.add(Shipment(shipment_code='QUERY-BUDGET-NO-VEHICLE', vehicle_id='missing'))
            db.commit()
        try:
            rows = self.request_with_budget('/api/shipments', 2)
            missing = next(row for row in rows if row['id'] == 'QUERY-BUDGET-NO-VEHICLE')
            self.assertIsNone(missing['vehicle_registration'])
            self.assertTrue(any(row['vehicle_registration'] for row in rows))
        finally:
            with SessionLocal() as db:
                db.query(Shipment).filter(Shipment.shipment_code == 'QUERY-BUDGET-NO-VEHICLE').delete()
                db.commit()
