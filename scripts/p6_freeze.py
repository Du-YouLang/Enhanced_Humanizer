"""Freeze metadata from already acquired official public sources, without exporting gold patches."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from workbench.benchmark import digest, freeze_manifest, plan

BUGSINPY_REVISION = '11c5f1eea954a42132cfd06bf257766a7963e0fd'
SWE_REVISION = '6ec7bb89b9342f664a54a6e0a6ea6501d3437cc2'
SWE_PARQUET_SHA256 = '7a21f37b8bc179c7db5beeb14e88ac538ba283455c776e6b2535bbfb6e3551b4'
SWE_IDS = ('psf__requests-1963', 'psf__requests-2148', 'pytest-dev__pytest-11143',
           'pytest-dev__pytest-11148', 'sympy__sympy-11400', 'sympy__sympy-11870')


def make_manifest(source):
    source = Path(source)
    if json.loads((source/'bugsinpy-metadata.json').read_text())['sha'] != BUGSINPY_REVISION:
        raise ValueError('BugsInPy revision changed')
    if json.loads((source/'swe-lite-metadata.json').read_text())['sha'] != SWE_REVISION:
        raise ValueError('SWE dataset revision changed')
    if hashlib.sha256((source/'swe-test.parquet').read_bytes()).hexdigest() != SWE_PARQUET_SHA256:
        raise ValueError('SWE dataset bytes changed')
    tasks = []
    for number in range(1, 7):
        directory = source/'bugsinpy'/f'black-{number}'
        info = dict(line.split('=', 1) for line in (directory/'bug.info').read_text().splitlines())
        info = {k: v.strip('"') for k, v in info.items()}
        hashes = {name: hashlib.sha256((directory/name).read_bytes()).hexdigest()
                  for name in ('bug.info', 'requirements.txt', 'run_test.sh')}
        tasks.append(dict(task_id=f'BIP-black-{number}', family='BugsInPy', upstream_instance=f'black:{number}',
                          repository='psf/black', base_commit=info['buggy_commit_id'], source_revision=BUGSINPY_REVISION,
                          material_sha256=digest(hashes), original_python=info['python_version'],
                          source_url=f'https://github.com/soarsmu/BugsInPy/tree/{BUGSINPY_REVISION}/projects/black/bugs/{number}',
                          preparation_status='MATERIAL_FROZEN_ENV_PENDING',
                          license_status='BugsInPy framework license unresolved; raw materials private; task project MIT'))
    selected = json.loads((source/'swe-selected.private.json').read_text())
    if [row['instance_id'] for row in selected] != list(SWE_IDS):
        raise ValueError('Selection changed after source acquisition')
    for row in selected:
        tasks.append(dict(task_id='SWEL-'+row['instance_id'], family='SWE-bench Lite', upstream_instance=row['instance_id'],
                          repository=row['repo'], base_commit=row['base_commit'], source_revision=SWE_REVISION,
                          material_sha256=digest(row), dataset_sha256=SWE_PARQUET_SHA256,
                          project_version=row['version'], environment_setup_commit=row['environment_setup_commit'],
                          source_url=f'https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite/tree/{SWE_REVISION}',
                          preparation_status='MATERIAL_FROZEN_ENV_PENDING',
                          license_status='Dataset/project notices must be retained in private prepared checkouts; redistribution pending audit'))
    for identity, title, gpu in [('SCI-PC-ALM', 'PC_ALM lightweight reproduction', False),
                                 ('SCI-STROKE', 'User-selected stroke paper tables and figures', False),
                                 ('SCI-EGL', 'Exponential Gradient Learning tables and figures', False),
                                 ('SCI-GRANGER-GPU', 'CPU Granger Causality to CuPy precision and performance', True)]:
        tasks.append(dict(task_id=identity, family='scientific', title=title, requires_gpu=gpu,
                          preparation_status='NOT_RUN_MISSING_MATERIAL', paper=None, data_sha256=None,
                          gold_sha256=None, license=None, tolerances=None, invariants=None,
                          required_materials=['exact paper/reference code', 'input data and license', 'base commit',
                                              'numerical gold', 'tolerances and invariants', 'seed/precision protocol']))
    return dict(schema_version=1, phase='P6', seed=42, repetitions=1, n_candidates=3,
                task_time_cap_seconds=1200, candidate_time_cap_seconds=600, request_time_cap_seconds=120,
                selection_policy='Metadata-only low setup cost: black IDs 1..6; requests first 2, pytest 8.0 first 2, SymPy first 2 in the pinned test split. No model outcomes used. Convenience selection, not representative.',
                smoke_tasks=['BIP-black-2', 'SWEL-psf__requests-1963'],
                baseline_environment_policy='Project-local Conda task environments; one immutable environment/permissions/hardware receipt per task for every arm. Prepare and validate buggy versus gold before any model execution.',
                protocol_version=2,
                model_identity_policy='Keep the previously verified deepseek-flash and gpt-6.1-sol requested identities. Preserve returned model/version metadata per new run. Prior P1/P2 reports describe V4.1 Flash; an alias does not authorize silently changing the underlying model.',
                judges=dict(J0='automatic visible test ordering', J1='original LAV logprobs',
                            J2='BLOCKED_REGION_REPORTED_BY_USER', J3='independent gpt-6.1-sol structured judge'),
                merge_ablation='Same frozen input pool: best-of-N versus best-of-N + Reviewer M, including all-failed pools. Hidden evaluator excluded from public handoffs.',
                tasks=tasks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT/'.local-workbench/benchmark/sources')
    parser.add_argument('--output', type=Path, default=ROOT/'configs/benchmark-p6-v2.json')
    args = parser.parse_args()
    if not args.source.resolve().is_relative_to((ROOT/'.local-workbench').resolve()):
        raise ValueError('Raw benchmark inputs must remain private and project local')
    manifest = freeze_manifest(make_manifest(args.source), args.output)
    output = ROOT/f'.local-workbench/benchmark/plan-v{manifest["protocol_version"]}.json'
    value = dict(manifest_sha256=manifest['manifest_sha256'], results=plan(manifest),
                 model_requests=0, status='PLANNED_NOT_EXECUTED', real_budget_authorization='PENDING')
    if output.exists() and json.loads(output.read_text()) != value:
        raise ValueError('Plan already exists with different contents')
    output.write_text(json.dumps(value, indent=2)+'\n')
    print(json.dumps(dict(status='METADATA_FROZEN_NOT_ENV_OR_PHASE_ACCEPTED',
                         manifest_sha256=manifest['manifest_sha256'], tasks=16, planned_arm_cells=96, model_requests=0)))


if __name__ == '__main__':
    main()
