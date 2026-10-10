"""Acquire pinned official benchmark materials privately, without GitHub auth or remote writes."""
import hashlib
import json
from pathlib import Path
import urllib.request

from p6_freeze import ROOT, BUGSINPY_REVISION, SWE_REVISION, SWE_PARQUET_SHA256, SWE_IDS


def fetch(url, target, expected=None):
    target = Path(target)
    if not target.resolve().is_relative_to((ROOT/'.local-workbench/benchmark').resolve()):
        raise ValueError('Acquisition target must be private and project local')
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(url, headers={'User-Agent': 'Enhanced-Humanizer-P6-pinned-read-only'})
        with urllib.request.urlopen(request, timeout=60) as source:
            data = source.read(32*1024*1024+1)
        if len(data) > 32*1024*1024:
            raise ValueError('Unexpected benchmark artifact size')
        if expected and hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('Source bytes do not match the frozen digest')
        target.write_bytes(data)
    data = target.read_bytes()
    if expected and hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('Existing source hash changed')
    return data


def acquire():
    import pyarrow.parquet as pq
    directory = ROOT/'.local-workbench/benchmark/sources'
    fetch(f'https://api.github.com/repos/soarsmu/BugsInPy/commits/{BUGSINPY_REVISION}', directory/'bugsinpy-metadata.json')
    fetch(f'https://huggingface.co/api/datasets/princeton-nlp/SWE-bench_Lite/revision/{SWE_REVISION}', directory/'swe-lite-metadata.json')
    for number in range(1, 7):
        for name in ('bug.info', 'requirements.txt', 'run_test.sh', 'setup.sh'):
            fetch(f'https://raw.githubusercontent.com/soarsmu/BugsInPy/{BUGSINPY_REVISION}/projects/black/bugs/{number}/{name}',
                  directory/'bugsinpy'/f'black-{number}'/name)
    file = directory/'swe-test.parquet'
    fetch(f'https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite/resolve/{SWE_REVISION}/data/test-00000-of-00001.parquet',
          file, SWE_PARQUET_SHA256)
    rows = pq.read_table(file).to_pylist()
    chosen = [next(row for row in rows if row['instance_id'] == identity) for identity in SWE_IDS]
    output = directory/'swe-selected.private.json'
    if output.exists() and json.loads(output.read_text()) != chosen:
        raise ValueError('Existing selected gold material changed')
    output.write_text(json.dumps(chosen, indent=2)+'\n')
    return dict(status='PINNED_SOURCES_ACQUIRED', public_tasks=12, model_requests=0, remote_mutations=0)


if __name__ == '__main__':
    print(json.dumps(acquire()))
