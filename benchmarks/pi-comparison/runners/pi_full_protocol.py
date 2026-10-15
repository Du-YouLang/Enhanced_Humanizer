"""Prospective missing-task scope and durable no-replay journal; no model tools."""
import hashlib
import json
import os
from pathlib import Path

PROTOCOL='PI_FULL_MAIN_MISSING_20261014_V1'
PROFILES=('P0','P1','P2','P3')
PROVIDERS=('deepseek','subscription')
RETAINED_TASKS=('BIP-black-2','SCI-GRANGER-GPU')
TASKS=('BIP-black-1','BIP-black-2','BIP-black-3','BIP-black-4','BIP-black-5','BIP-black-6',
       'SWEL-psf__requests-1963','SWEL-psf__requests-2148','SWEL-pytest-dev__pytest-11143',
       'SWEL-pytest-dev__pytest-11148','SWEL-sympy__sympy-11400','SWEL-sympy__sympy-11870',
       'SCI-PC-ALM','SCI-STROKE','SCI-EGL','SCI-GRANGER-GPU')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def cells(tasks):
    return [{'task_id':tid,'profile':profile,'provider':provider,'repetition':0}
            for tid in tasks for provider in PROVIDERS for profile in PROFILES]


def validate_plan(value):
    if 'deepseek_transport_policy' in value:
        from p6_network_policy import retry10_transport
        retry10_transport(value['deepseek_transport_policy'])
    body=dict(value);expected=body.pop('plan_sha256',None)
    wanted=cells(t for t in TASKS if t not in RETAINED_TASKS)
    if (body.get('protocol')!=PROTOCOL or digest(body)!=expected or body.get('cells')!=wanted
            or body.get('retained_cells')!=cells(RETAINED_TASKS)
            or body.get('bulk_256_enabled') is not False or body.get('external_release_authorized') is not False
            or set(t['task_id'] for t in body['main_manifest']['tasks'])!=set(TASKS)):
        raise ValueError('Exact 112 missing cells plus 16 retained cells required; no replay/release')
    if body.get('cumulative_caps')!={'deepseek_requests':10000,'api_cash_usd':200}:
        raise ValueError('Existing cumulative budget required')
    return value


def exclusive(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())


class UncertainStage(RuntimeError):pass


class Journal:
    """Completed steps are reused exactly. A started uncertain step is blocked."""
    def __init__(self,root):self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
    def run(self,name,action):
        if not name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in name):
            raise ValueError('Safe journal stage name required')
        start=self.root/(name+'.started.json');done=self.root/(name+'.completed.json')
        if done.exists():
            row=json.loads(done.read_bytes())
            if row['stage']!=name or row['value_sha256']!=digest(row['value']):raise ValueError('Journal receipt changed')
            return row['value']
        if start.exists():raise UncertainStage('Retained uncertain stage requires reconciliation: '+name)
        exclusive(start,{'stage':name,'automatic_model_replay':False})
        value=action();exclusive(done,{'stage':name,'value':value,'value_sha256':digest(value)})
        return value


def budget_available(ledger):
    return len(ledger['requests'])<10000 and ledger['cash_bound_nano']<200_000_000_000
