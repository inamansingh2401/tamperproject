"""Five interleaved runs, final compatibility/strict paths, single/batch at each concurrency."""
from pathlib import Path
import argparse
import subprocess
import sys
from seed_benchmark import ROOT

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'docs/benchmarks/final-ingestion')
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if any(output.glob('*-r*.json')):
        raise SystemExit('Existing measurements retained. Select a fresh --output-dir; do not overwrite partial evidence.')
    logs = ROOT/'.codex-tools/final-ingestion'
    output.mkdir(parents=True,exist_ok=True)
    logs.mkdir(parents=True,exist_ok=True)
    for run in range(1,6):
        for concurrency in (1,5,10,20):
            modes = [('legacy',1),('strict',1),('legacy',10),('strict',10)]
            if run % 2 == 0:
                modes.reverse()
            for mode,batch in modes:
                name = f'{mode}-b{batch}-c{concurrency}-r{run}'
                command = [sys.executable,'operations/run_benchmark.py',
                    '--ingest-concurrency',str(concurrency),'--batch-size',str(batch),
                    '--output',str(output/(name+'.json'))]
                if mode == 'strict':
                    command.append('--strict-device')
                with (logs/(name+'.log')).open('w') as log:
                    subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
                print(f'Completed {name}',flush=True)

if __name__ == '__main__':
    main()
