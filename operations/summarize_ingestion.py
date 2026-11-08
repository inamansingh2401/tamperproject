"""Nearest-rank run percentiles summarized across five independent runs."""
import argparse
import json
from pathlib import Path
import statistics
from seed_benchmark import ROOT


def summarize(directory, modes, concurrencies):
    summary = {}
    for concurrency in concurrencies:
        summary[str(concurrency)] = {}
        for mode in modes:
            runs = [json.loads((directory/f'{mode}-c{concurrency}-r{run}.json').read_text())
                    for run in range(1,6)]
            metrics = {}
            names = ['events_per_second','p50_ms','p95_ms','error_rate','sql_per_request','revision_writes']
            if all('sensor_relation_growth_bytes' in row for row in runs):
                names.append('sensor_relation_growth_bytes')
            for name in names:
                values = [row[name] for row in runs]
                metrics[name] = dict(median=statistics.median(values),minimum=min(values),
                    maximum=max(values),spread=max(values)-min(values),runs=values)
            summary[str(concurrency)][mode] = metrics
        first,second = (summary[str(concurrency)][mode] for mode in modes)
        assessment = {}
        for name in ('events_per_second','p50_ms','p95_ms'):
            a,b = first[name],second[name]
            assessment[name] = ('overlapping ranges; within observed noise'
                if max(a['minimum'],b['minimum'])<=min(a['maximum'],b['maximum'])
                else 'non-overlapping observed ranges')
        summary[str(concurrency)]['assessment'] = assessment
    return summary


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch-comparison',action='store_true')
    args = parser.parse_args()
    directory = ROOT/'docs/benchmarks/ingestion'
    data = summarize(directory,('single','batch10') if args.batch_comparison else ('revision','bypass'),
                     [10] if args.batch_comparison else [1,5,10,20])
    (directory/('batch-summary.json' if args.batch_comparison else 'revision-summary.json')).write_text(
        json.dumps(data,indent=2),encoding='utf-8')
    print(json.dumps(data,indent=2))
