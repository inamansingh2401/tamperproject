"""Benchmark safety and measurement contracts, without creating any database."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'operations'))
from seed_benchmark import validate_target
from benchmark_api import percentile


class BenchmarkTests(unittest.TestCase):
    def test_rejects_non_benchmark_targets_before_connecting(self):
        for url in ('sqlite:///production.db',
                    'postgresql+psycopg://localhost/production',
                    'postgresql+psycopg://db.example/safetrack_benchmark'):
            with self.assertRaises(ValueError):
                validate_target(url)
        self.assertEqual(validate_target('postgresql+psycopg://127.0.0.1/safetrack_benchmark').database,
                         'safetrack_benchmark')

    def test_percentiles_use_nearest_rank_and_accept_unsorted_samples(self):
        self.assertEqual(percentile(list(range(100, 0, -1)), .5), 50)
        self.assertEqual(percentile(list(range(1, 101)), .95), 95)
        self.assertEqual(percentile([8], .95), 8)
