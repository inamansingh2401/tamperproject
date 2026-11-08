import unittest
import test_device_security as fixture
from database import SessionLocal
from models import Shipment, SensorEvent
from chain_verifier import verify_shipment


class ChainVerifierTests(unittest.TestCase):
    # Reuse fixture helpers without inheriting/re-running the replay test methods.
    setUp = fixture.DeviceSecurityTests.setUp
    tearDown = fixture.DeviceSecurityTests.tearDown
    signed = fixture.DeviceSecurityTests.signed
    post = fixture.DeviceSecurityTests.post
    admin = fixture.DeviceSecurityTests.admin

    def records(self):
        for sequence in (1,2,3):
            response = self.post(self.signed(sequence=sequence))
            self.assertEqual(response.status_code,200,response.text)

    def test_modified_deleted_and_reordered_rows_report_first_break(self):
        self.records()
        with SessionLocal() as db:
            shipment = db.get(Shipment,self.shipment_id)
            rows = db.query(SensorEvent).filter_by(shipment_id=self.shipment_id).order_by(SensorEvent.id).all()
            original_ids = [r.id for r in rows]
            self.assertTrue(verify_shipment(db,shipment)['valid'])
            rows[1].temperature += 1
            db.flush()
            result = verify_shipment(db,shipment)
            self.assertEqual(result['first_broken_id'], original_ids[1])
            db.rollback()
            db.delete(db.get(SensorEvent,original_ids[1]))
            db.flush()
            result = verify_shipment(db,shipment)
            self.assertEqual(result['first_broken_id'], original_ids[2])
            db.rollback()
            # Swap primary-key ordering without altering either event's evidence.
            row = db.get(SensorEvent,original_ids[0])
            row.id = -999999
            db.flush()
            db.get(SensorEvent,original_ids[1]).id = original_ids[0]
            db.flush()
            row.id = original_ids[1]
            db.flush()
            self.assertFalse(verify_shipment(db,shipment)['valid'])
            self.assertEqual(verify_shipment(db,shipment)['first_broken_index'],1)
            db.rollback()

    def test_tail_deletion_requires_external_checkpoint_and_endpoint_is_protected(self):
        self.records()
        with SessionLocal() as db:
            ship = db.get(Shipment,self.shipment_id)
            checkpoint = verify_shipment(db,ship)
            last = db.query(SensorEvent).filter_by(shipment_id=self.shipment_id).order_by(SensorEvent.id.desc()).first()
            db.delete(last)
            db.flush()
            self.assertTrue(verify_shipment(db,ship)['valid'])  # Cannot magically detect a removed suffix.
            result = verify_shipment(db,ship,checkpoint['checked'],checkpoint['tail_hash'])
            self.assertFalse(result['valid'])
            self.assertEqual(len(result['errors']),2)
            db.rollback()
        path = '/api/shipments/'+self.name+'/evidence/verify'
        self.assertEqual(self.client.get(path).status_code,401)
        response = self.client.get(path,headers=self.admin())
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['signature_verified'],3)
