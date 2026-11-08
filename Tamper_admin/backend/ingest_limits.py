"""Bounded per-process token buckets; authenticated critical events bypass quotas."""
from collections import OrderedDict
import math
import os
from threading import Lock
import time


class IngestLimits:
    def __init__(self, device_rate=2., device_burst=120, ip_rate=1000., ip_burst=2000,
                 failure_rate=5., failure_burst=20, clock=time.monotonic):
        self.rules = {'device':(device_rate,device_burst), 'ip':(ip_rate,ip_burst),
                      'failed-ip':(failure_rate,failure_burst)}
        if any(not math.isfinite(rate) or rate <= 0 or burst < 1 for rate,burst in self.rules.values()):
            raise ValueError('Ingestion limits require positive rates and bursts of at least one')
        self.clock = clock
        self.buckets = OrderedDict()
        self.lock = Lock()

    def _take(self, keys):
        with self.lock:
            now = self.clock()
            remaining = {}
            wait = 0.
            for key in keys:
                rate,burst = self.rules[key[0]]
                tokens,previous = self.buckets.get(key,(float(burst),now))
                tokens = min(float(burst),tokens+max(0.,now-previous)*rate)
                remaining[key] = tokens
                wait = max(wait,(1.-tokens)/rate)
            for key,tokens in remaining.items():
                self.buckets[key] = (tokens-(1. if wait <= 0 else 0.),now)
                self.buckets.move_to_end(key)
            while len(self.buckets)>20000:
                self.buckets.popitem(last=False)
            return max(1,math.ceil(wait)) if wait>0 else 0

    def telemetry(self, device, ip, critical):
        if critical:
            return 0
        return self._take([('device',device),('ip',ip)])

    def failed_auth(self, ip):
        # Invalid credentials cannot spend the legitimate-producer IP budget.
        return self._take([('failed-ip',ip)])


def from_environment():
    return IngestLimits(
        device_rate=float(os.getenv('INGEST_DEVICE_RATE','2')),
        device_burst=int(os.getenv('INGEST_DEVICE_BURST','120')),
        ip_rate=float(os.getenv('INGEST_IP_RATE','1000')),
        ip_burst=int(os.getenv('INGEST_IP_BURST','2000')),
        failure_rate=float(os.getenv('INGEST_FAILURE_RATE','5')),
        failure_burst=int(os.getenv('INGEST_FAILURE_BURST','20')))
