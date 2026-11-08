"""Read-only, streaming stored-chain verification with an optional external anchor."""
from evidence import export_record, verify_record
from models import SensorEvent


def verify_shipment(db, shipment, expected_count=None, expected_tail_hash=None):
    previous = '0'*64
    checked = signed = 0
    # One ordered SELECT/cursor: PostgreSQL sees one statement snapshot.
    rows = db.query(SensorEvent).filter_by(shipment_id=shipment.id).order_by(SensorEvent.id).yield_per(500)
    for row in rows:
        result = verify_record(export_record(row),previous,shipment.shipment_code)
        checked += 1
        if result['integrity'] != 'verified':
            return dict(valid=False,checked=checked,signature_verified=signed,
                first_broken_id=row.id,first_broken_index=checked,errors=result['errors'])
        signed += result['signature'] == 'verified'
        previous = row.record_hash
    errors = []
    if expected_count is not None and checked != expected_count:
        errors.append('External event count mismatch')
    if expected_tail_hash is not None and previous != expected_tail_hash:
        errors.append('External tail hash mismatch')
    return dict(valid=not errors,checked=checked,signature_verified=signed,
        first_broken_id=None,first_broken_index=checked+1 if errors else None,
        tail_hash=previous,errors=errors,
        scope='Stored chain only; completeness requires an independently trusted count/tail checkpoint')
