"""Opt-in report cache, fenced by a database revision committed with every write."""
from collections import OrderedDict
from copy import deepcopy
import json
import os
from threading import Lock
import time
from typing import Protocol
from urllib.parse import urlparse

from sqlalchemy import event
from database import SessionLocal
from models import CacheRevision, SensorEvent, Shipment, ShipmentAlert, Vehicle

NAMESPACE = 'reports'
REPORT_MODELS = (SensorEvent, Shipment, ShipmentAlert, Vehicle)
REPORT_TABLES = {model.__tablename__ for model in REPORT_MODELS}


class CacheBackend(Protocol):
    def get(self, key: str): ...
    def put(self, key: str, value: dict, ttl: float): ...


class MemoryTTLCache:
    def __init__(self, clock=time.monotonic, max_entries=32):
        self.clock = clock
        self.max_entries = max_entries
        self.entries = OrderedDict()
        self.lock = Lock()

    def get(self, key):
        with self.lock:
            entry = self.entries.get(key)
            if entry is None:
                return None
            expires, value = entry
            if expires <= self.clock():
                del self.entries[key]
                return None
            self.entries.move_to_end(key)
            return deepcopy(value)

    def put(self, key, value, ttl):
        with self.lock:
            self.entries[key] = (self.clock()+ttl, deepcopy(value))
            self.entries.move_to_end(key)
            while len(self.entries) > self.max_entries:
                self.entries.popitem(last=False)


class RedisTTLCache:
    def __init__(self, client):
        self.client = client

    def get(self, key):
        value = self.client.get(key)
        return json.loads(value) if value is not None else None

    def put(self, key, value, ttl):
        self.client.set(key, json.dumps(value, allow_nan=False), px=max(1, int(ttl*1000)))


class ReportCache:
    def __init__(self, backend=None, ttl=5, namespace='process'):
        if not 0 < ttl <= 30:
            raise ValueError('Report cache TTL must be greater than zero and at most 30 seconds')
        self.backend = backend
        self.ttl = ttl
        self.namespace = namespace
        self.counts = {'hits': 0, 'misses': 0, 'errors': 0}
        self.lock = Lock()

    @property
    def enabled(self):
        return self.backend is not None

    def revision(self, db):
        return db.query(CacheRevision.generation).filter(CacheRevision.namespace == NAMESPACE).scalar() or 0

    def key(self, revision):
        return f'safetrack:reports:v1:{self.namespace}:{revision}'

    def get(self, revision):
        try:
            value = self.backend.get(self.key(revision))
        except Exception:
            # Cache failures fall through to the authenticated database path.
            with self.lock:
                self.counts['errors'] += 1
            value = None
        with self.lock:
            self.counts['hits' if value is not None else 'misses'] += 1
        return value

    def put(self, revision, value):
        try:
            self.backend.put(self.key(revision), value, self.ttl)
        except Exception:
            with self.lock:
                self.counts['errors'] += 1

    def metrics(self):
        with self.lock:
            counters = dict(self.counts)
        requests = counters['hits'] + counters['misses']
        return dict(enabled=self.enabled, backend=type(self.backend).__name__ if self.enabled else 'off',
                    ttl_seconds=self.ttl, process_id=os.getpid(), **counters,
                    hit_rate=counters['hits']/requests if requests else 0,
                    scope='Reports only; process-local counters. Authorization and revision reads are never cached.')


def from_environment():
    mode = os.getenv('REPORT_CACHE_BACKEND', 'off')
    ttl = float(os.getenv('REPORT_CACHE_TTL_SECONDS', '5'))
    if mode == 'off':
        return ReportCache(ttl=ttl)
    if mode == 'memory':
        return ReportCache(MemoryTTLCache(), ttl=ttl)
    if mode == 'redis':
        uri = os.getenv('REDIS_URL', '')
        namespace = os.getenv('REPORT_CACHE_NAMESPACE', '')
        target = urlparse(uri)
        if not namespace or target.scheme not in ('redis', 'rediss'):
            raise RuntimeError('Redis caching requires REDIS_URL and a database-specific REPORT_CACHE_NAMESPACE')
        if target.scheme != 'rediss' and target.hostname not in ('localhost', '127.0.0.1', '::1'):
            raise RuntimeError('Remote Redis caching requires TLS')
        from redis import Redis
        return ReportCache(RedisTTLCache(Redis.from_url(uri, socket_timeout=.25, socket_connect_timeout=.25)),
                           ttl=ttl, namespace=namespace)
    raise RuntimeError('REPORT_CACHE_BACKEND must be off, memory or redis')


def advance_revision(db):
    """Must execute inside the data writer's transaction, including raw SQL writers."""
    if db.bind.dialect.name == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    statement = insert(CacheRevision).values(namespace=NAMESPACE, generation=1)
    db.execute(statement.on_conflict_do_update(
        index_elements=[CacheRevision.namespace],
        set_={'generation': CacheRevision.generation+1}))


def _mark_orm_changes(db, flush_context, instances):
    if any(isinstance(obj, REPORT_MODELS) for obj in list(db.new)+list(db.dirty)+list(db.deleted)):
        db.info['reports_changed'] = True


def _mark_statement_changes(state):
    statement = state.statement
    if getattr(statement, 'is_dml', False) and getattr(statement.table, 'name', None) in REPORT_TABLES:
        state.session.info['reports_changed'] = True


def _before_commit(db):
    _mark_orm_changes(db, None, None)
    if db.info.get('reports_changed'):
        advance_revision(db)


def _end_transaction(db, transaction):
    if transaction.parent is None:
        db.info.pop('reports_changed', None)


# ORM flushes and Session.execute/bulk writes share one transaction fence.
# Every application worker installs these rules, even with cache reads disabled.
event.listen(SessionLocal.class_, 'before_flush', _mark_orm_changes)
event.listen(SessionLocal.class_, 'do_orm_execute', _mark_statement_changes)
event.listen(SessionLocal.class_, 'before_commit', _before_commit)
event.listen(SessionLocal.class_, 'after_transaction_end', _end_transaction)

report_cache = from_environment()
