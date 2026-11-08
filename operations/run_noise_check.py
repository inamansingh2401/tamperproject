"""Interleave five or more Phase 0/1 runs, each in a new local cluster."""
import argparse
import json
from pathlib import Path
import statistics
import subprocess
import sys
from seed_benchmark import ROOT


def summarize(paths):
    runs = [json.loads(path.read_text()) for path in paths]
    result = {}
    for endpoint in runs[0]['endpoints']:
        name = endpoint['path']
        entries = [next(row for row in run['endpoints'] if row['path'] == name) for run in runs]
        result[name] = {}
        for metric in ('p50_ms', 'p95_ms'):
            values = [row[metric] for row in entries]
            result[name][metric] = dict(median=statistics.median(values),minimum=min(values),
                                        maximum=max(values),spread=max(values)-min(values),runs=values)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-root',type=Path,required=True)
    parser.add_argument('--runs',type=int,default=5)
    args = parser.parse_args()
    if args.runs < 5:
        parser.error('At least five runs are required')
    directory = ROOT/'docs/benchmarks/noise'
    directory.mkdir(parents=True,exist_ok=True)
    logs = ROOT/'.codex-tools/noise'
    logs.mkdir(parents=True,exist_ok=True)
    artifacts = {'phase0':[], 'phase1':[]}
    for number in range(1,args.runs+1):
        for label, source in [('phase0',args.baseline_root.resolve()),('phase1',ROOT)]:
            output = directory/f'{label}-{number}.md'
            with (logs/f'{label}-{number}.log').open('w') as log:
                subprocess.run([sys.executable,'operations/run_benchmark.py','--events','100000',
                    '--devices','100','--samples','30','--output',str(output)],cwd=source,
                    stdout=log,stderr=subprocess.STDOUT,check=True)
            artifacts[label].append(output.with_suffix('.json'))
            print(f'Completed {label} run {number}/{args.runs}',flush=True)
    summary = {label:summarize(paths) for label, paths in artifacts.items()}
    (directory/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print('Saved all raw samples and min/max spreads',flush=True)


if __name__ == '__main__':
    main()
