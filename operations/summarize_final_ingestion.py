"""Generate final comparisons directly from all five interleaved raw runs."""
import hashlib
import argparse
import json
from pathlib import Path
import statistics
from seed_benchmark import ROOT

DIRECTORY = ROOT/'docs/benchmarks/final-ingestion'
METRICS = ('events_per_second','p50_ms','p95_ms','sql_per_request','error_rate')

def aggregate(rows):
    return {name:dict(median=statistics.median(values),minimum=min(values),maximum=max(values),
                      spread=max(values)-min(values),runs=values)
            for name in METRICS for values in [[row[name] for row in rows]]}

def overlap(a,b):
    return max(a['minimum'],b['minimum']) <= min(a['maximum'],b['maximum'])

def cell(metric):
    return f"{metric['median']:.2f} [{metric['minimum']:.2f}, {metric['maximum']:.2f}]"

def main():
    global DIRECTORY
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir',type=Path,default=DIRECTORY)
    args = parser.parse_args()
    DIRECTORY = args.input_dir.resolve()
    expected = [DIRECTORY/f'{mode}-b{batch}-c{concurrency}-r{run}.json'
                for mode in ('legacy','strict') for batch in (1,10)
                for concurrency in (1,5,10,20) for run in range(1,6)]
    if any(not path.exists() for path in expected):
        raise SystemExit('Incomplete experiment: all five matched runs are required; no final report written.')
    data = {}
    raw = []
    for concurrency in (1,5,10,20):
        for batch in (1,10):
            key = f'b{batch}-c{concurrency}'
            data[key] = {}
            for mode in ('legacy','strict'):
                rows = [json.loads((DIRECTORY/f'{mode}-b{batch}-c{concurrency}-r{run}.json').read_text()) for run in range(1,6)]
                assert all(row['error_rate']==0 and row['events_stored']==400 and row['initial_events']==100020 and row['cache_backend']=='off' for row in rows)
                raw.extend(rows)
                data[key][mode] = aggregate(rows)
            a,b = data[key]['legacy'],data[key]['strict']
            data[key]['comparison'] = {name:dict(
                change_percent=(b[name]['median']/a[name]['median']-1)*100,
                paired_differences=[y-x for x,y in zip(a[name]['runs'],b[name]['runs'])],
                assessment='within observed noise (ranges overlap)' if overlap(a[name],b[name]) else 'outside observed run ranges')
                for name in ('events_per_second','p50_ms','p95_ms')}
    source = {str(file.relative_to(ROOT)):hashlib.sha256(file.read_bytes()).hexdigest()
              for file in sorted((ROOT/'Tamper_admin/backend').glob('*.py'))}
    summary = dict(cases=len(raw),events=sum(row['events_stored'] for row in raw),
        requests=sum(row['requests'] for row in raw),source_sha256=source,
        dependency_versions=raw[0]['dependency_versions'],results=data)
    (DIRECTORY/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    lines = ['# Final ingestion: Phase 4 controls enabled', '',
        'Local PostgreSQL only; synthetic data and software P-256 signatures. Caching OFF, revision writes ON. No hosted operations or hardware signing.', '',
        '## Method', '',
        f"Completed {summary['cases']} fresh-cluster cases, {summary['events']} accepted timed events and {summary['requests']} HTTP requests, with zero timed errors. Every case uses the original seed 20261108: 100,000 events / 100 devices, then 20 signed warmups and 400 timed events across 40 device/shipment streams. One Uvicorn process and the original 5+5 connection pool; concurrency 1/5/10/20. Single requests and batches of ten are repeated five times per mode/concurrency. Each round interleaves compatibility and strict modes and both batch sizes; even rounds reverse the four-case order. No cases run concurrently with other benchmarks.", '',
        'Strict mode uses digest-only device credentials, key epoch, boot counter, sequence and capture time; compatibility mode retains the existing credential check without the replay ledger. Both use the final API, including signature verification, body guards, validation, chain writes and commits. Payloads are identical between these modes. Warmups and timed events use separate boot counters to avoid nonce reuse. Signing, client construction, seeding and startup are outside the timer. p50/p95 measure the whole request, so batch latency is not per-event latency.', '',
        'Cells are median of five run metrics [minimum, maximum]; summary.json also records spread, every run value, paired differences, dependency versions and backend source hashes. Overlapping ranges mean an effect is not established outside observed noise; disjoint observed ranges are not a formal statistical confidence interval. Short closed-loop local runs do not establish sustained fleet or hosted capacity.', '',
        '## Final code, measured rates and request latency', '',
        '| Concurrency | Events/request | Device mode | Events/sec median [min, max] | p50 ms median [min, max] | p95 ms median [min, max] | SQL/request |',
        '| ---: | ---: | --- | ---: | ---: | ---: | ---: |']
    for concurrency in (1,5,10,20):
        for batch in (1,10):
            for mode in ('legacy','strict'):
                m = data[f'b{batch}-c{concurrency}'][mode]
                lines.append(f"| {concurrency} | {batch} | {mode} | {cell(m['events_per_second'])} | {cell(m['p50_ms'])} | {cell(m['p95_ms'])} | {m['sql_per_request']['median']:.4f} |")
    lines += ['', '## Incremental strict-device cost on the same final code', '',
        'This comparison isolates the combined digest credential check and replay-ledger path relative to compatibility mode; it does not isolate each SQL operation or cryptographic primitive. Signature verification already existed in Phase 3 and runs in both modes.', '',
        '| Concurrency | Events/request | Throughput change strict vs compatibility | Assessment | p50 change | Assessment | p95 change | Assessment |',
        '| ---: | ---: | ---: | --- | ---: | --- | ---: | --- |']
    for concurrency in (1,5,10,20):
        for batch in (1,10):
            m = data[f'b{batch}-c{concurrency}']['comparison']
            values = ' | '.join(f"{m[name]['change_percent']:+.1f}% | {m[name]['assessment']}" for name in ('events_per_second','p50_ms','p95_ms'))
            lines.append(f'| {concurrency} | {batch} | {values} |')
    historical_a = json.loads((ROOT/'docs/benchmarks/ingestion/revision-summary.json').read_text())
    historical_b = json.loads((ROOT/'docs/benchmarks/ingestion/batch-summary.json').read_text())
    lines += ['', '## Historical Phase 3 comparison', '',
        'Phase 3A supplies single-request references at all tested concurrencies; Phase 3B supplies the later single/batch pair only at concurrency 10. Both are shown at concurrency 10 to avoid cherry-picking. Phase 3 had no batch measurements at concurrency 1/5/20. These are historical runs, not freshly interleaved old-code controls: the API, dependency patches and measurement time changed. Differences cannot be attributed solely to replay/authentication. Use the fresh paired table above for incremental strict-device cost.', '',
        '| Historical reference | Concurrency | Events/request | Phase 3 events/sec | Final strict events/sec | EPS ranges overlap? | Phase 3 p50 / p95 ms | Final strict p50 / p95 ms |',
        '| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |']
    cases = [('Phase 3A',c,1,historical_a[str(c)]['revision']) for c in (1,5,10,20)]
    cases += [('Phase 3B',10,b,historical_b['10'][mode]) for b,mode in ((1,'single'),(10,'batch10'))]
    historical = []
    for reference,c,b,old in cases:
        new = data[f'b{b}-c{c}']['strict']
        historical.append(dict(reference=reference,concurrency=c,batch_size=b,old=old,
            final=new,assessment={name:('within observed noise (ranges overlap)' if overlap(old[name],new[name]) else 'outside observed ranges; historical comparison only') for name in ('events_per_second','p50_ms','p95_ms')}))
        lines.append(f"| {reference} | {c} | {b} | {cell(old['events_per_second'])} | {cell(new['events_per_second'])} | {'Yes' if overlap(old['events_per_second'],new['events_per_second']) else 'No'} | {old['p50_ms']['median']:.2f} / {old['p95_ms']['median']:.2f} | {new['p50_ms']['median']:.2f} / {new['p95_ms']['median']:.2f} |")
    summary['historical_comparisons'] = historical
    (DIRECTORY/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    lines += ['', '## Strict-mode batching benefit', '',
        '| Concurrency | Single events/sec | Batch events/sec | Throughput change | Observed range assessment |',
        '| ---: | ---: | ---: | ---: | --- |']
    for c in (1,5,10,20):
        a,b = (data[f'b{batch}-c{c}']['strict']['events_per_second'] for batch in (1,10))
        lines.append(f"| {c} | {cell(a)} | {cell(b)} | {(b['median']/a['median']-1)*100:+.1f}% | {'within observed noise (ranges overlap)' if overlap(a,b) else 'outside observed run ranges'} |")
    lines += ['', '## Reproduce', '', '```powershell',
        'python operations/run_final_ingestion.py', 'python operations/summarize_final_ingestion.py', '```', '',
        'Uses disposable loopback PostgreSQL databases and generated process-only credentials; existing API accounts/passwords and hosted configuration are untouched. See [raw runs and summary](final-ingestion/summary.json). Results include no real sensor logs, secure-element signing, WAN/TLS cost, production load or cloud capacity claim.', '']
    (ROOT/'docs/benchmarks/final-ingestion.md').write_text('\n'.join(lines),encoding='utf-8')

if __name__ == '__main__':
    main()
