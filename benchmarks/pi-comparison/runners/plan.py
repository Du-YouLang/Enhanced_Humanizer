"""Validate independent comparator rows; never edit or invoke the active main runner."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
PROFILES=('P0','P1','P2','P3')
sys.path.insert(0,str(ROOT/'src'))
from workbench.benchmark import check_manifest


def contracts(manifest):
    value=json.loads(Path(manifest).read_text(encoding='utf8'))
    check_manifest(value)
    if value.get('protocol_version') not in (11,12) or len(value['tasks'])!=16:
        raise ValueError('Frozen v11/v12 tasks required, without replacement science tasks')
    rows=[]
    for task in value['tasks']:
        scientific=task['family']=='scientific'
        rows.append({'task_id':task['task_id'],'family':task['family'],
                     'base_commit':task.get('base_commit'),
                     'material_sha256':task.get('public_material_sha256',task.get('material_sha256')),
                     'preparation_status':task['preparation_status'],
                     'environment_sha256':task.get('environment_sha256'),
                     'private_acceptance_binding':'Use exact main preparation; no private paths or gold values in this view',
                     'public_contract_status':'BIND_EXISTING_PREPARATION_BEFORE_LIVE',
                     'grader_authority':'Existing private P6 evaluator, never passed to Pi',
                     'task_role_seconds':1200 if scientific else 900,
                     'per_request_seconds':value['request_time_cap_seconds'],'max_output_tokens':256000,
                     'role_request_cap':value['per_role_api_requests'],
                     'compute_policy':'LOCAL_ONLY_CPU_PROTOCOLS_PRESERVED_GPU_TASKS_SINGLE_LOCAL_GPU',
                     'independent_acceptance':'NOT_RUN'})
    return rows


def plan(manifest):
    tasks=contracts(manifest)
    # Prespecified smoke only. Full repeated 256-run proposal is not an implicit run order.
    chosen=('BIP-black-2','SCI-GRANGER-GPU')
    rows=[{'task_id':task,'profile':profile,'provider':provider,
           'model_id_requested':'deepseek-flash' if provider=='deepseek' else 'gpt-6.1-sol',
           'status':'NOT_RUN_RUNTIME_GATES_PENDING',
           'auth_route':'OFFICIAL_API' if provider=='deepseek' else 'INDEPENDENT_PI_CHATGPT_SUBSCRIPTION_OAUTH',
           'repetition':0,'automatic_retry':False}
          for task in chosen for provider in ('deepseek','openai') for profile in PROFILES]
    return {'schema_version':1,'protocol_id':'PI_COMPARISON_PREPARATION_V1',
            'upstream_main_manifest_sha256':json.loads(Path(manifest).read_text())['manifest_sha256'],
            'main_protocol_unmodified':True,'model_execution_enabled':False,
            'bulk_256_attempts_enabled':False,'task_contracts':tasks,'smoke_rows':rows,
            'requirements_before_live':['Real OS/peer/network controls','Metering wire/usage/cumulative cap controls',
                                        'Public/private positive and negative replay','Explicit same-model/reasoning checks',
                                        'No competition with active main batch'],
            'cash_aggregation':'Same existing 10000-request/USD100 ceiling, not a second allowance',
            'external_release_authorized':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',type=Path,default=ROOT/'configs/benchmark-p6-v12-final2.json')
    args=parser.parse_args();print(json.dumps(plan(args.manifest),ensure_ascii=False,indent=2))
