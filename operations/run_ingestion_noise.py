"""Five interleaved ingestion comparisons, isolated clusters and caching always off."""
import argparse
from pathlib import Path
import subprocess
import sys
from seed_benchmark import ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch-comparison',action='store_true')
    parser.add_argument('--concurrencies',type=int,nargs='+',choices=[1,5,10,20])
    args = parser.parse_args()
    directory = ROOT/'docs/benchmarks/ingestion'
    directory.mkdir(parents=True,exist_ok=True)
    logs = ROOT/'.codex-tools/ingestion'
    logs.mkdir(parents=True,exist_ok=True)
    for run in range(1,6):
        for concurrency in (args.concurrencies or ([10] if args.batch_comparison else [1,5,10,20])):
            modes = ('single','batch10') if args.batch_comparison else ('revision','bypass')
            for mode in modes:
                output = directory/f'{mode}-c{concurrency}-r{run}.json'
                command = [sys.executable,'operations/run_benchmark.py','--ingest-concurrency',str(concurrency),
                           '--output',str(output)]
                if mode=='bypass':
                    command.append('--without-revision')
                if mode=='batch10':
                    command.extend(['--batch-size','10'])
                with (logs/(output.stem+'.log')).open('w') as log:
                    subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
                print(f'Completed {mode} concurrency {concurrency} run {run}/5',flush=True)


if __name__=='__main__':
    main()
