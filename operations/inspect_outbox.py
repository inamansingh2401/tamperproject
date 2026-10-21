"""Read-only local outbox health/recovery inventory. Never leases, retries or deletes."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]


def inspect_outbox(path):
    path = Path(path).resolve(strict=True)
    # Do not use Outbox(): its constructor/connection setup performs writes.
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro', uri=True, timeout=10)) as db:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA query_only=ON')
        check = [r[0] for r in db.execute('PRAGMA quick_check')]
        counts = {r['state']: r['n'] for r in db.execute('SELECT state, COUNT(*) n FROM outbox GROUP BY state')}
        # Metadata only; no signed payloads, credentials or keys in terminal output.
        recovery = [dict(r) for r in db.execute("SELECT event_id,state,attempts,received FROM outbox WHERE state IN ('blocked','archived') ORDER BY rowid LIMIT 20")]
        oldest = db.execute("SELECT event_id,received FROM outbox WHERE state='queued' ORDER BY rowid LIMIT 1").fetchone()
        return {'checked_at': datetime.now(timezone.utc).isoformat(), 'read_only': True,
                'integrity': 'ok' if check == ['ok'] else 'FAILED (details withheld)',
                'counts': counts, 'oldest_queued': dict(oldest) if oldest else None,
                'recovery_candidates_first_20': recovery,
                'recovery_applied': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--outbox', type=Path, default=ROOT/'gateway/gateway-outbox.db')
    args = parser.parse_args()
    print(json.dumps(inspect_outbox(args.outbox), indent=2))


if __name__ == '__main__':
    main()
