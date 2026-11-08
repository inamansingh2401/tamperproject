"""Freeze the installed application's dependency closure for pip-audit --no-deps.

Includes requirement extras/markers, excludes unrelated packages in a shared lab.
Run with the application interpreter; audit the output using an isolated tool venv.
"""
import argparse
from importlib.metadata import distribution
from pathlib import Path
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    pending = [Requirement(line) for file in ('Tamper_admin/backend/requirements.txt','gateway/requirements.txt')
               for line in (ROOT/file).read_text().splitlines() if line and not line.startswith('#')]
    seen,versions = set(),{}
    while pending:
        req = pending.pop()
        key = (req.name.lower().replace('_','-'),tuple(sorted(req.extras)))
        if key in seen:
            continue
        seen.add(key)
        dist = distribution(req.name)
        if not req.specifier.contains(dist.version):
            raise RuntimeError(f'Installed {req.name} does not satisfy application requirements')
        versions[dist.metadata['Name']] = dist.version
        for raw in dist.requires or []:
            child = Requirement(raw)
            if child.marker is None or any(child.marker.evaluate({'extra':extra}) for extra in ('',*req.extras)):
                pending.append(child)
    args.output.write_text(''.join(f'{name}=={version}\n' for name,version in sorted(versions.items())),encoding='utf-8')

if __name__ == '__main__':
    main()
