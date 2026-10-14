"""Fill only the fourteen missing Pi tasks, using official SDK and P6 oracles."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys
import time
import traceback

sys.path[:0]=[str(Path(__file__).parent),'/opt/workbench/source','/opt/workbench/source/src']
import pi_formal_linux as pi
from pi_full_protocol import Journal,UncertainStage,cells,digest,exclusive,validate_plan,budget_available
from p6_checkpoint_recovery import sha
from p6_connection_probe import reconnect_probe
from p6_main_budget import MainLedger,task_limits
from p6_gate_policy import GENERATION_RULES
from p2_candidates import namespace_command


def read(path):return json.loads(Path(path).read_bytes())


def validate_bindings(payload):
    plan=validate_plan(payload['plan'])
    if plan['source_sha256']!=payload['source_sha256']:raise ValueError('Comparator source differs from plan')
    for path,expected in {**plan['main_manifest']['runner_source_sha256'],**payload['source_sha256'],
                          **plan['retained_evidence_sha256']}.items():
        if sha(path)!=expected:raise ValueError('Frozen source/evidence changed: '+path)
    MainLedger(pi.LEDGER,payload['budget']).validate(read(pi.LEDGER))
    legacy=read(plan['legacy_ledger']);current=read(pi.LEDGER)
    if (current['requests'][:len(legacy['requests'])]!=legacy['requests']
            or current['codex_turns'][:len(legacy['codex_turns'])]!=legacy['codex_turns']):
        raise ValueError('Historical cumulative ledger rows changed')
    original=read(plan['retained_original_root']+'/receipt.json')
    if original['completed_cells']!=16 or original['total_cells']!=16:raise ValueError('Original 16 cells must be closed')
    if {digest(r['cell']) for r in original['results']}!={digest(c) for c in plan['retained_cells']}:
        raise ValueError('Original results do not cover exactly the two retained tasks')
    return plan


def make_task(payload,row):
    task_payload={'task':row,'manifest':payload['plan']['main_manifest'],'budget':payload['budget']}
    if row['family']=='scientific':
        sys.path.insert(0,'/opt/workbench/benchmark/envs/science-tms-v1/lib/python3.12/site-packages')
        import p6_science_main_linux as science
        task=science.task(task_payload)
        task['prompt']+='\n'+Path(__file__).with_name('science-clarifications-v1.md').read_text()+'\n'+GENERATION_RULES
        def tester(source,hidden=False):
            if not hidden or task['kind']!='tms':return science.test(source,hidden)
            from p6_tms_grader import grade
            start=time.perf_counter()
            r=grade(source,science.SCIENCE/'intake/tms',Path(task['prefix']),per_call_timeout=180,rss_limit_mib=4096)
            return {'verdict':'INDETERMINATE' if r['verdict']=='PASS' else r['verdict'],
                    'numeric_verdict':'PASS_NUMERIC_REVIEW_PENDING' if r['verdict']=='PASS' else r['verdict'],
                    'reason':'Independent source/report/figure review required' if r['verdict']=='PASS' else 'Original numerical judge rejected output',
                    'detail':r,'elapsed_seconds':time.perf_counter()-start}
    else:
        task=pi.main.public_task(task_payload);tester=pi.main.public_test
        if task['id']=='SWEL-pytest-dev__pytest-11148':
            # The public legacy test assumes a second import is always new;
            # this issue deliberately adds module-cache reuse. Retain every
            # assertion and clear the first import before testing load failure,
            # exactly as the upstream test's own cleanup does. This overlay is
            # only in public scratch copies; the original hidden patch is intact.
            name='testing/test_pathlib.py';raw=(Path(task['base'])/name).read_bytes()
            anchor=b"        # mode='importlib' fails if no spec is found to load the module\n"
            if raw.count(anchor)!=1:raise ValueError('Pinned public cache-test context differs')
            task['public_overlays'][name]=raw.replace(anchor,b'        del sys.modules[module.__name__]\n\n'+anchor)
            task['prompt']+='\nProspective public fixture correction: the scratch-only test_no_meta_path_found clears its first imported module before testing failure without a loader. All assertions and hidden tests remain; do not edit original tests in the coding worktree.\n'
            def tester(source,hidden=False):
                if not hidden:return pi.main.public_test(source,False)
                original=task['public_overlays'];task['public_overlays']={k:v for k,v in original.items() if k!=name}
                try:return pi.main.public_test(source,True)
                finally:task['public_overlays']=original
    return task_payload,task,tester


def activate(root,payload,task_payload,task,tester,role,fixture_url):
    pi.shared.ACTIVE.clear();pi.shared.ACTIVE.update(root=root,task=task,payload=task_payload,
        ledger=MainLedger(pi.LEDGER,payload['budget']),key='',deadline=time.monotonic()+role,
        generation_seconds=role,active_seconds=role,workers={},main_phase=True,defer_hidden=True,fixture_url=fixture_url)
    pi.shared.LEDGER_PATH=pi.LEDGER;pi.shared.test_source=tester


def task_controls(payload):
    """Actual zero-provider SDK/tool checks, plus every new task environment binding."""
    plan=validate_bindings(payload);before=sha(pi.LEDGER)
    sdk_payload={**payload,'run_id':payload['run_id']+'-sdk'}
    sdk=pi.fixture_controls(sdk_payload)
    root=pi.RUNS/payload['run_id'];root.mkdir(parents=True);(root/'control').mkdir()
    (root/'control/canary').write_text('controller only')
    rows=[]
    for tid in dict.fromkeys(c['task_id'] for c in plan['cells']):
        row=next(t for t in plan['main_manifest']['tasks'] if t['task_id']==tid)
        task_payload,task,tester=make_task(payload,row)
        with task['fixture_context'] as url:
            activate(root,payload,task_payload,task,tester,900,url)
            info={'task_id':tid,'base_commit':task['base_commit'],'env_sha256':task['seal']['env_sha256'],
                  'hidden_suite_sha256':task['hidden_suite_sha256'],'status':'BOUND_FROZEN_SCIENCE_CONTROLS' if row['family']=='scientific' else 'BOUND_PUBLIC_POSITIVE_NEGATIVE'}
            if row['family']!='scientific':
                frozen=read(pi.main.BASE/'science/private/public-main-controls-frozen-v2.json')
                entry=next(t for t in frozen['tasks'] if t['task_id']==tid)
                receipt=read(entry['receipt'])
                info['reference_controls']={'path':entry['receipt'],'sha256':entry['receipt_sha256'],
                                            'positive':receipt['results']['gold']['verdict'],'negative':receipt['results']['buggy']['verdict']}
                # Run the exact Pi SDK bash tool under the actual coding fence.
                # Gold is used only in this zero-provider control, never a model task.
                descriptor,_=pi.main.job(tid+'-public-control','pi',source=receipt['gold'])
                dest=Path(descriptor['root']);work=Path(descriptor['work'])
                argv=[task['prefix']+'/bin/python','-B','/opt/workbench/source/p6_public_visible.py','--contract',str(dest/'visible-contract.json')]
                command=shlex.join(argv)
                w=pi.execute(dest,work,'P0','fixture',payload['budget'],'Synthetic public tool control',900,
                    Path(__file__).with_name('pi_session.mjs'),prefix=Path(task['prefix']),public_reads=descriptor['public_read_paths'],
                    denied=descriptor['denied_paths'],fixture_url=url,fixture_ca=task['fixture_ca'],
                    fixture_steps=[('bash',{'command':command})])
                events=list(pi.records((dest/'events.private.jsonl').read_bytes()))
                tool=[e for e in events if e['type']=='tool_execution_end']
                good=w['status']=='COMPLETED' and len(tool)==1 and tool[0].get('isError') is False
                info.update(status='PASS_REAL_FENCED_PUBLIC_TOOL' if good else 'CONTROL_FAILED',worker=w)
            rows.append(info)
            exclusive(root/(tid+'-control.json'),info)
            if info['status']=='CONTROL_FAILED':break
    # Test the actual SDK's retry without any provider, preserving tool outputs.
    retry=[]
    for fault,wanted in (('agent-overload','COMPLETED'),('agent-overload-five','INFRA_RETRY_PENDING'),('agent-quota','INFRA_FAIL')):
        dest=root/fault;dest.mkdir();work=dest/'code';work.mkdir()
        pi.shared.trusted_git(work,'init','-q');pi.shared.trusted_git(work,'config','user.name','Pi zero-model control')
        pi.shared.trusted_git(work,'config','user.email','control@example.invalid')
        w=pi.execute(dest,work,'P0','fixture',payload['budget'],'Synthetic retry control',900,
                     Path(__file__).with_name('pi_session.mjs'),fixture_fault=fault,prospective_retry=True)
        retry.append({'fault':fault,'status':w['status'],'expected':wanted,'worker':w})
    okay=(sdk['status']=='PASS_FORMAL_SDK_CONTROLS' and len(rows)==14
          and all(r['status']!='CONTROL_FAILED' for r in rows) and all(r['status']==r['expected'] for r in retry)
          and sha(pi.LEDGER)==before)
    receipt={'status':'PASS_FULL_MAIN_ZERO_MODEL_CONTROLS' if okay else 'CONTROL_FAILED',
             'model_calls':0,'sdk':sdk,'tasks':rows,'retry_controls':retry,'source_sha256':payload['source_sha256'],
             'ledger_sha256_before':before,'ledger_sha256_after':sha(pi.LEDGER)}
    exclusive(root/'receipt.json',receipt)
    return {'status':receipt['status'],'root':str(root),'tasks':len(rows),'model_calls':0}


def require_controls(payload):
    for path in pi.RUNS.glob('formal-full-controls-*/receipt.json'):
        r=read(path)
        if r['status']=='PASS_FULL_MAIN_ZERO_MODEL_CONTROLS' and r['source_sha256']==payload['source_sha256']:
            return {'path':str(path),'sha256':sha(path)}
    raise RuntimeError('Exact source requires successful full-main zero-model controls')


def verify_frozen(work,candidate,frozen):
    if (pi.shared.fenced_git(work,'rev-parse','HEAD')!=frozen['head_commit']
            or pi.shared.fenced_git(work,'status','--porcelain')
            or frozen['candidate_sha256']!=digest(candidate)):
        raise ValueError('Frozen candidate changed; no hidden acceptance or model replay')
    patch,source=pi.shared.program_evidence(work,candidate['base_commit'])
    if frozen['program_sha256']!=digest({'patch':patch,'source':source}):raise ValueError('Frozen program evidence differs')


def run_cell(root,payload,cell,journal):
    name=cell['task_id']+'-'+cell['profile']+'-'+cell['provider']
    task_row=next(t for t in payload['plan']['main_manifest']['tasks'] if t['task_id']==cell['task_id'])
    task_payload,task,tester=make_task(payload,task_row);role=task_limits(payload['budget'],task_row)['role_seconds']
    with task['fixture_context'] as url:
        activate(root,payload,task_payload,task,tester,role,url)
        descriptor=journal.run(name+'-setup',lambda:pi.main.job(name,'pi')[0])
        dest=Path(descriptor['root']);work=Path(descriptor['work'])
        prompt=descriptor['prompt']+'\nCommit the final implementation cleanly in this original worktree. Bring changes from any research worktrees back here. No model subagents, credentials, installs or original-test edits.'
        def model():
            connectivity=reconnect_probe()
            exclusive(dest/'pre-spend-network.json',connectivity)
            if connectivity['verdict']!='PASS':raise RuntimeError('Pre-spend network unavailable; preserve stage without replay')
            return pi.execute(dest,work,cell['profile'],cell['provider'],payload['budget'],prompt,role,
                Path(__file__).with_name('pi_session.mjs'),key=payload.get('key'),prefix=Path(task['prefix']),
                public_reads=descriptor['public_read_paths'],gpu=task.get('gpu_coding',False),
                denied=descriptor['denied_paths'],prospective_retry=True,fixture_url=url,fixture_ca=task['fixture_ca'])
        worker=journal.run(name+'-model',model)
        pi.shared.ACTIVE['workers'][name]=worker
        candidate=journal.run(name+'-public',lambda:pi.shared.candidate(name,worker))
        def freeze():
            value={'head_commit':candidate.get('head_commit'),'candidate_sha256':digest(candidate),
                   'program_sha256':digest({'patch':candidate.get('patch'),'source':candidate.get('source')}),
                   'private_results_seen':False,'cell':cell,'plan_sha256':payload['plan']['plan_sha256']}
            exclusive(dest/'frozen-program.json',value);return value
        frozen=journal.run(name+'-freeze',freeze)
        if worker['status']=='COMPLETED' and candidate['verdict']=='PASS':
            verify_frozen(work,candidate,frozen)
            def accept():
                try:return tester(work,True)
                except ValueError as error:
                    return {'verdict':'INDETERMINATE' if 'review' in str(error).lower() else 'FAIL','error_type':type(error).__name__,'reason':str(error)[:500],'elapsed_seconds':0}
                except (OSError,ImportError,KeyError,TypeError) as error:
                    return {'verdict':'INFRA_FAIL','error_type':type(error).__name__,'reason':str(error)[:500],'elapsed_seconds':0}
            acceptance=journal.run(name+'-acceptance',accept)
            verify_frozen(work,candidate,frozen)
        else:acceptance={'verdict':'NOT_RUN','reason':'Completion or public gate did not pass','elapsed_seconds':0}
        outcome=acceptance['verdict'] if worker['status']=='COMPLETED' and candidate['verdict']=='PASS' else 'FAIL' if worker['status']=='COMPLETED' else worker['status']
        row={'cell':cell,'plan_sha256':payload['plan']['plan_sha256'],'outcome':outcome,
             'worker_status':worker['status'],'candidate_verdict':candidate['verdict'],'head_commit':candidate.get('head_commit'),
             'acceptance':acceptance,'scope':worker['scope'],'task_environment_sha256':task['seal']['env_sha256'],
             'base_commit':task['base_commit'],'hidden_suite_sha256':task['hidden_suite_sha256'],'role_seconds':role,
             'coding_and_public_seconds':worker['wall_seconds']+candidate.get('test_report',{}).get('elapsed_seconds',0),
             'usage':worker['summary'].get('usage'),'sdk_dispatches':worker['sdk_dispatches'],
             'provider_wire_attempts':worker['wire_count'],'api_cash_actual':worker['api_cash_actual'],
             'evidence_kind':'REAL_MODEL','harness':'official Pi SDK 1.1.0','model_requested':worker['model_identity'],
             'scientific_review':'PENDING_SOL_REVIEW' if outcome=='INDETERMINATE' else 'NOT_APPLICABLE_OR_NUMERIC_FAIL',
             'retained_original_cells_replayed':0}
        if (dest/'result.json').exists():
            if read(dest/'result.json')!=row:raise ValueError('Retained cell result differs')
        else:exclusive(dest/'result.json',row)
        return row


def compare(payload):
    pi.quiet();plan=validate_bindings(payload);control=require_controls(payload)
    root=pi.RUNS/payload['run_id'];root.mkdir(parents=True,exist_ok=True)
    if not (root/'plan.json').exists():exclusive(root/'plan.json',plan)
    elif read(root/'plan.json')!=plan:raise ValueError('Resume plan changed')
    (root/'control').mkdir(exist_ok=True)
    if not (root/'control/canary').exists():(root/'control/canary').write_text('controller only')
    journal=Journal(root/'control/stages');results=[];status='FULL_MAIN_COMPLETED'
    if not (root/'ledger-before.private.json').exists():exclusive(root/'ledger-before.private.json',read(pi.LEDGER))
    for index,cell in enumerate(plan['cells']):
        name=cell['task_id']+'-'+cell['profile']+'-'+cell['provider']
        final=root/'control/stages'/(name+'-cell.completed.json')
        if not final.exists() and not budget_available(read(pi.LEDGER)):
            status='CUMULATIVE_BUDGET_STOP';break
        try:
            # Do not wrap all substeps in a start marker: substep receipts are
            # independently reusable after loss of power, with uncertain steps blocked.
            if final.exists():row=journal.run(name+'-cell',lambda:None)
            else:
                row=run_cell(root,payload,cell,journal)
                exclusive(final,{'stage':name+'-cell','value':row,'value_sha256':digest(row)})
            results.append(row)
            progress=root/('progress-'+str(index+1).zfill(3)+'.json')
            if not progress.exists():exclusive(progress,{'completed_new_cells':len(results),'last':row})
            if row['worker_status'] in ('INFRA_FAIL','INFRA_RETRY_PENDING'):
                status='INFRASTRUCTURE_RECONCILIATION_REQUIRED';break
        except UncertainStage as error:
            status='UNCERTAIN_STAGE_BLOCKED';exclusive(root/('resume-blocked-'+str(time.time_ns())+'.json'),{'reason':str(error),'cell':cell});break
    receipt={'status':status,'results':results,'completed_new_cells':len(results),'total_new_cells':112,
             'retained_cells':16,'total_tasks':16,'source_sha256':payload['source_sha256'],'controls':control,
             'plan_sha256':plan['plan_sha256'],'original_cells_replayed':0,'api_cash_actual':'unavailable',
             'scientific_pass_requires_independent_source_report_figure_review':True,'external_release_authorized':False}
    path=root/('receipt.json' if not (root/'receipt.json').exists() else 'receipt-resume-'+str(time.time_ns())+'.json')
    exclusive(path,receipt);exclusive(root/('ledger-snapshot-'+str(time.time_ns())+'.private.json'),read(pi.LEDGER))
    return {'status':status,'completed_new_cells':len(results),'retained_cells':16,'root':str(root)}


if __name__=='__main__':
    pi.protect_memory()
    if os.getuid()==0:raise RuntimeError('Non-root project WSL only')
    payload=json.load(sys.stdin)
    lock_path=pi.BASE/'full-main-owner.lock'
    with lock_path.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            validate_bindings(payload)
            result=task_controls(payload) if payload['mode']=='controls' else compare(payload)
            print(json.dumps(result),flush=True)
        except Exception as error:
            root=pi.RUNS/payload['run_id'];root.mkdir(parents=True,exist_ok=True)
            exclusive(root/('failure-'+str(time.time_ns())+'.json'),{'status':'INFRA_FAIL','error_type':type(error).__name__,
                     'traceback':traceback.format_exc(),'automatic_model_replay':False})
            raise
