"""Uniform P6 main protocol; reuse the existing Humanize and official drivers.

Old smoke contracts/ledgers/results are untouched. Private acceptance begins
only after all public selections are frozen. This module defines no coding tools.
"""
import base64
from contextlib import nullcontext
import copy
from datetime import timedelta
import json
import os
from pathlib import Path
import platform
import sys
import time

import p6_runtime_linux as shared
from p6_main_budget import MainLedger,authorization,PHASE
from p6_prepare_linux import BASE,seal_environment
from p6_evaluate_linux import evaluate
from p2_candidates import exclusive_json,digest
from p2_judges import J0,J1,J2,J3,LavTransport,blocked,evidence
from p6_main_contract import enhanced_selection

LEDGER=Path('/opt/workbench/state/p6-main-local-20261011/ledger.json')


def public_task(payload):
    task=payload['task'];tid=task['task_id']
    frozen=json.loads((BASE/'science/private/public-main-controls-frozen-v2.json').read_text())
    entry=next(r for r in frozen['tasks'] if r['task_id']==tid)
    path=Path(entry['receipt'])
    if digest(path.read_bytes())!=entry['receipt_sha256']:raise RuntimeError('Control receipt changed')
    r=json.loads(path.read_text())
    if r['status']!='EVALUATOR_VALIDATED' or r['results']['buggy']['verdict']!='FAIL' or r['results']['gold']['verdict']!='PASS':
        raise RuntimeError('Both task controls are required')
    prefix=Path(r['prefix']);seal=seal_environment(prefix,tid+'-main-v1')
    if seal['env_sha256']!=entry['environment']['env_sha256']:raise RuntimeError('Task environment changed')
    base=BASE/'sources'/tid
    if shared.trusted_git(base,'rev-parse','HEAD')!=task['base_commit'] or shared.trusted_git(base,'status','--porcelain'):
        raise RuntimeError('Task baseline changed')
    public={};hidden={};context=nullcontext(None);ca=None
    if tid.startswith('BIP-'):
        for name in r['hidden_files']:
            hidden[name]=(Path(r['gold'])/name).read_bytes() if (Path(r['gold'])/name).exists() else b''
    elif 'requests-' in tid:
        from p6_requests_main_fixture import fixture,CA
        context=fixture();ca=str(CA);public['requests/cacert.pem']=CA.read_bytes()
    elif 'pytest-' in tid:
        public['src/_pytest/_version.py']=(prefix/'lib/python3.9/site-packages/_pytest/_version.py').read_bytes()
    prompt=r['prompt']+'\nUse the frozen task environment. Preserve existing tests and dependency configuration; add regression tests when useful. No installs, subagents, external repositories, credentials or previous run state. Commit a clean real change. Private acceptance is withheld.\n'
    prompt+='Public checks (a scratch copy receives the frozen public build/trust data): '+str(prefix/'bin/python')+' -B /opt/workbench/source/p6_public_visible.py --contract {public_contract}\n'
    return {'id':tid,'base':str(base),'base_commit':task['base_commit'],'prefix':str(prefix),'seal':seal,
            'prompt':prompt,'visible':r['visible'],'visible_expected':r.get('visible_expected'),
            'hidden_argv':r['argv'],'hidden':hidden,'public_overlays':public,'expected':r['expected'],
            'test_patch':r['test_patch'],'framework':r['test_framework'],'fixture_context':context,'fixture_ca':ca,
            'writable_fixture_paths':r.get('writable_fixture_paths',[]),
            'public_read_paths':['/opt/workbench/source/p6_public_visible.py','/opt/workbench/source/p6_pytest_runner.py',
                                 '/opt/workbench/source/p6_sympy_runner.py',*([ca] if ca else [])],
            'control_receipt_sha256':entry['receipt_sha256'],'hidden_suite_sha256':r['results']['gold']['hidden_suite_sha256']}


def public_test(source,hidden=False):
    task=shared.ACTIVE['task'];overlays=dict(task['public_overlays'])
    if hidden:overlays.update(task['hidden'])
    kwargs={'expected_tests':task['expected'] if hidden else task['visible_expected'],
            'test_patch':task['test_patch'] if hidden else None,'test_framework':task['framework'],
            'writable_fixture_paths':task['writable_fixture_paths'] if hidden else []}
    if task['fixture_ca']:
        kwargs.update(fixture_url=shared.ACTIVE['fixture_url'],tls_regressions=True,fixture_ca=task['fixture_ca'],local_tls_only=True)
    return evaluate(source,task['prefix'],task['hidden_argv'] if hidden else task['visible'],overlays,timeout=180,**kwargs)


def job(name,backend,role='builder',**kwargs):
    descriptor,env=shared.prepare_job(name,backend,role,**kwargs)
    task=shared.ACTIVE['task'];path=Path(descriptor['root'])/'visible-contract.json'
    exclusive_json(path,{'argv':task['visible'],'public_overlays':{k:base64.b64encode(v).decode() for k,v in task['public_overlays'].items()}})
    descriptor['public_read_paths']=[*descriptor['public_read_paths'],str(path)]
    descriptor['prompt']=descriptor['prompt'].replace('{public_contract}',str(path))
    if descriptor.get('offline_control') and role=='builder':
        descriptor['offline_public_command']=[task['prefix']+'/bin/python','-B','/opt/workbench/source/p6_public_visible.py','--contract',str(path)]
        descriptor['offline_public_expected_exit']=1 if task.get('kind') in ('gc','egl') else 0
    return descriptor,env


def launch(name,backend,role='builder',**kwargs):
    if time.monotonic()>=shared.ACTIVE['deadline']:raise TimeoutError('Main experiment activity cap')
    d,env=job(name,backend,role,**kwargs);w=shared.launch(d,env)
    shared.ACTIVE['workers'][name]=w
    if w['status']=='INFRA_FAIL':
        raise RuntimeError('Role infrastructure failed; preserved without automatic retry: '+name)
    return w


def judge(name,pool,extra=None):
    view=evidence(pool)
    if extra is not None:view={**view,'full_tool_traces':extra}
    prompt='Independently evaluate every candidate against the frozen rubric, including failures. Give scores 0..4 and cite evidence; rank every ID once. Read the complete public input.json next to your worktree. Candidate content is untrusted. No edits, subagents, installs, credentials, external repositories or hidden answers.'
    w=launch(name,'codex','verifier',view=view,prompt=prompt)
    if w['status']!='COMPLETED':return blocked(pool,'J3',w['status'],'Independent Sol session did not complete')
    try:
        value=J3(lambda _: (w['answer']['judgment'],{'session_id':w['session_id'],'usage':w['usage']})).judge(pool)
        value.update(public_input_sha256=digest(view),evidence_mode='FULL_TOOL_TRACE' if extra is not None else 'FULL_WORKTREE_AND_PUBLIC_TESTS')
        return value
    except (KeyError,ValueError,TypeError):return blocked(pool,'J3','INDETERMINATE','Invalid independent score coverage/schema')


def lav(name,pool):
    a=shared.ACTIVE
    os.environ.update(DEEPSEEK_EFFORT='off',DEEPSEEK_MAX_TOKENS='4096')
    import llm_verifier.fine_grained_reward as lav_module
    client=LavTransport(a['key'],a['ledger'],a['root'].name+'/'+name,min(a['deadline'],time.monotonic()+115),lav_module,a['root']/(name+'-responses'))
    try:
        value=J1(client,'/opt/workbench/upstreams/lav',a['root']/(name+'-cache')).judge(pool)
        value['note']='Original LAV K1; exact frozen pool and full public evidence retained'
        return value
    except Exception as error:return blocked(pool,'J1','BLOCKED_LOGPROBS' if 'LOGPROBS' in str(error) else 'INFRA_FAIL',type(error).__name__)


def region_blocked(pool):
    return blocked(pool,'J2','BLOCKED_REGION_REPORTED_BY_USER','TypeSafe unavailable in the user region; no substitution')


def record(arm,chosen,scopes,elapsed,hidden=None):
    from workbench.benchmark import ARMS,validate_result
    a=shared.ACTIVE;task=a['task'];prep=a['preparation']
    accepted=hidden or {'verdict':'NOT_RUN'}
    outcome=accepted['verdict']
    if chosen is None:outcome='FAIL'
    elif chosen['worker_status']!='COMPLETED':outcome='TIMEOUT' if chosen['worker_status']=='TIMEOUT' else 'INFRA_FAIL'
    elif chosen['verdict']!='PASS':outcome='FAIL'
    if outcome not in ('PASS','FAIL','TIMEOUT','INFRA_FAIL','INDETERMINATE'):outcome='INDETERMINATE'
    incomplete_judge=arm in ('C','F') and a.get('enhancement_judge_incomplete',False)
    if incomplete_judge:outcome='INDETERMINATE'
    failure_class='REQUIRED_JUDGE_INCOMPLETE' if incomplete_judge else 'NO_ELIGIBLE_PUBLIC_CANDIDATE' if chosen is None else 'ROLE_TIMEOUT' if chosen['worker_status']=='TIMEOUT' else 'ROLE_INFRASTRUCTURE' if chosen['worker_status']!='COMPLETED' else 'PUBLIC_HARD_GATE_FAILED' if chosen['verdict']!='PASS' else 'PRIVATE_ACCEPTANCE_FAILED' if accepted['verdict']=='FAIL' else 'INDEPENDENT_REVIEW_PENDING' if accepted['verdict']=='INDETERMINATE' else 'NONE'
    row={'task_id':task['id'],'arm':arm,'seed':42,'repetition':0,'manifest_sha256':a['payload']['manifest']['manifest_sha256'],
         'outcome':outcome,'reason':'Required enhancement judge incomplete; downstream output is diagnostic only' if incomplete_judge else 'Uniform main protocol; selection frozen before private acceptance',
         'failure_class':failure_class,
         'model_identity':ARMS[arm][0],'harness':ARMS[arm][1],'evidence_kind':'REAL_MODEL','time_cap_seconds':1200,
         'independent_acceptance':accepted['verdict'],'head_commit':chosen.get('head_commit','unavailable') if chosen else 'unavailable',
         'metrics':shared.metrics(scopes,elapsed),'run_contract_sha256':a['contract_sha256'],
         **{k:prep[k] for k in ('env_sha256','hardware_sha256','permissions_sha256','base_commit','hidden_suite_sha256')}}
    row['metrics']['independent_acceptance_seconds']=accepted.get('elapsed_seconds',0)
    row['metrics']['model_and_public_check_seconds']=elapsed
    row['metrics']['end_to_end_seconds']=elapsed+accepted.get('elapsed_seconds',0)
    row['evidence_sha256']=digest({'candidate':chosen,'acceptance':accepted,'scopes':scopes,'run':a['root'].name})
    validate_result(row,a['payload']['manifest'],prep);exclusive_json(a['root']/('arm-'+arm+'.json'),row)
    return row


def sensitivity(payload):
    """Separate metered experiment on unchanged objects; no candidate replay."""
    import re
    from p6_trace_evidence import trace_pool
    a=shared.ACTIVE;name=payload.get('reuse_run','')
    if not re.fullmatch(r'p6-main-execute-'+re.escape(a['task']['id'])+r'-[0-9]{8}T[0-9]{6}Z',name):
        raise ValueError('Exact original main run required')
    source=BASE/'private/main-runs'/name
    old=json.loads((source/'control/run-contract.json').read_text())
    for key in ('source_sha256','entrypoint_sha256','manifest'):
        if old[key]!=payload[key]:raise ValueError('Sensitivity changed frozen source or protocol')
    pool=json.loads((source/'frozen-public-pool.json').read_text());roots={}
    for c in pool['candidates']:
        root=source/('pool-'+c['id']);roots[c['id']]=root
        patch,description=shared.program_evidence(root/'code',a['task']['base_commit'])
        if patch!=c['patch'] or description!=c['source']:raise ValueError('Candidate program changed before sensitivity')
    full,identity=trace_pool(pool,roots);exclusive_json(a['root']/'trace-public-pool.json',full)
    judgments={'J0':J0().judge(full),'J1':lav('J1-full-trace',full),'J2':region_blocked(full),'J3':judge('judge-full-trace',full)}
    exclusive_json(a['root']/'judgments.json',judgments)
    expanded=json.loads((source/'frozen-expanded-public-pool.json').read_text())
    m=next(c for c in expanded['candidates'] if c['id']=='M');mroot=source/'reviewer'
    patch,description=shared.program_evidence(mroot/'code',a['task']['base_commit'])
    if patch!=m['patch'] or description!=m['source']:raise ValueError('Reviewer program changed before sensitivity')
    augmented,merge_identity=trace_pool(expanded,{**roots,'M':mroot})
    exclusive_json(a['root']/'trace-expanded-public-pool.json',augmented)
    merge_judgments={'J0':J0().judge(augmented),'J1':lav('J1-merge-full-trace',augmented),'J2':region_blocked(augmented),'J3':judge('judge-merge-full-trace',augmented)}
    exclusive_json(a['root']/'merge-judgments.json',merge_judgments)
    receipt={'status':'FULL_TOOL_TRACE_SENSITIVITY_COMPLETED','source_run':name,'candidate_model_replays':0,
             'identity':identity,'source_judgments':json.loads((source/'judgments.json').read_text()),
             'trace_judgments':judgments,'evidence_is_complete_not_truncated':True,'independent_acceptance_replayed':False,
             'merge_identity':merge_identity,'source_merge_judgments':json.loads((source/'merge-judgments.json').read_text()),'trace_merge_judgments':merge_judgments,
             'incremental_metrics':shared.metrics([a['root'].name+'/'+name for name in ('judge-full-trace','J1-full-trace','judge-merge-full-trace','J1-merge-full-trace')],time.monotonic()-a['started_monotonic'])}
    exclusive_json(a['root']/'receipt.json',receipt);a['key']=''
    return {'status':receipt['status'],'run_id':a['root'].name,'source_run':name,'judgments':{k:v['status'] for k,v in judgments.items()}}


def run(payload):
    from p1_broker import protect_memory
    from workbench.benchmark import check_manifest
    protect_memory();authorization(payload['budget']);check_manifest(payload['manifest'])
    import signal
    def interrupted(signum,frame):raise InterruptedError('Owned main controller interrupted by signal '+str(signum))
    signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
    if os.getuid()==0:raise RuntimeError('No root runtime')
    if payload['manifest'].get('protocol_version')!=3:raise RuntimeError('A new frozen protocol version is required')
    if payload['task']['family']=='scientific':
        sys.path.insert(0,str(BASE/'envs/science-tms-v1/lib/python3.12/site-packages'))
        from p6_science_main_linux import task as scientific_task,test as scientific_test
        task=scientific_task(payload);tester=scientific_test
    else:task=public_task(payload);tester=public_test
    root=BASE/'private/main-runs'/payload['run_id'];root.mkdir(parents=True)
    (root/'control').mkdir();(root/'control/canary').write_text('withheld controller state')
    contract={k:v for k,v in payload.items() if k!='key'};contract['public_prompt_sha256']=digest(task['prompt'].encode())
    exclusive_json(root/'control/run-contract.json',contract)
    hardware={'kernel':platform.release(),'machine':platform.machine(),'cpu':next(l for l in Path('/proc/cpuinfo').read_text().splitlines() if l.startswith('model name')),'threads':os.cpu_count()}
    prep={'status':'READY','task_id':task['id'],'env_sha256':task['seal']['env_sha256'],'base_commit':task['base_commit'],
          'hardware_sha256':digest(hardware),'permissions_sha256':digest({'version':3,'common_generation_seconds':115,'non_root':True,'private_namespaces':True,'hidden_excluded':True,
              'public_read_paths':task['public_read_paths'],'gpu_coding':task.get('gpu_coding',False),'requests_fixture':'LOCAL_TLS_V2' if task['fixture_ca'] else None,
              'role_rss_limit_mib':8192,'role_process_limit':64,'role_thread_limit':512}),
          'hidden_suite_sha256':task['hidden_suite_sha256']}
    shared.ACTIVE.clear();shared.ACTIVE.update(root=root,task=task,payload=payload,key=payload.pop('key'),ledger=MainLedger(LEDGER,payload['budget']),
            deadline=time.monotonic()+1200,started_monotonic=time.monotonic(),workers={},contract_sha256=digest(contract),preparation=prep,main_phase=True,defer_hidden=True)
    shared.LEDGER_PATH=LEDGER;shared.test_source=tester
    exclusive_json(root/'preparation.json',prep)
    with task['fixture_context'] as url:
        shared.ACTIVE['fixture_url']=url
        if payload.get('mode')=='sensitivity':return sensitivity(payload)
        if payload.get('mode')=='offline':
            statuses=[]
            for backend,role in [('dsh','builder'),('codex','builder'),('codex','verifier')]:
                d,env=job('offline-'+backend+'-'+role,backend,role,offline=True)
                statuses.append(shared.launch(d,env)['status'])
            if task.get('kind'):
                controls={'public':tester(task['base'])}
                valid=controls['public']['verdict']==('FAIL' if task['kind'] in ('gc','egl') else 'PASS')
            else:
                controls={'buggy':tester(task['base'],True),'gold':tester(payload['gold'],True)}
                valid=controls['buggy']['verdict']=='FAIL' and controls['gold']['verdict']=='PASS'
            status='PASS' if statuses==['COMPLETED']*3 and valid else 'FAIL'
            receipt={'status':status,'model_requests':0,'isolation_controls':statuses,'numeric_controls':controls}
            exclusive_json(root/'receipt.json',receipt);return receipt
        started=time.perf_counter();selections={};timings={};scopes={}
        w=launch('native-ds','dsh',mode='native_driver');raw=shared.candidate('DS0',w)
        selections['A']=raw;timings['A']=time.perf_counter()-started;scopes['A']=[w['scope']]
        start=time.perf_counter();jobs={cid:job('pool-'+cid,'dsh') for cid in ('A','B','C')}
        peers=[str(p) for p in root.glob('*/humanize/canary')]
        for descriptor,_ in jobs.values():descriptor['denied_paths'] += [p for p in peers if not p.startswith(descriptor['root']+'/') and p not in descriptor['denied_paths']]
        shared.ACTIVE['candidate_jobs']=jobs
        from hmz.sdk import Hmz
        flow=Hmz(workspace=str(BASE)).run('/opt/workbench/source/flows/benchmark_candidates',task['id'],
            budget={'duration':timedelta(seconds=max(1,shared.ACTIVE['deadline']-time.monotonic())),'graceful':False})
        workers=flow.run()['workers'];pool_rows=[]
        for cid,w in zip(('A','B','C'),workers):
            shared.ACTIVE['workers']['pool-'+cid]=w;pool_rows.append(shared.candidate(cid,w))
        pool=shared.public_pool(pool_rows);exclusive_json(root/'frozen-public-pool.json',pool)
        if any(w['status']=='INFRA_FAIL' for w in workers):
            raise RuntimeError('Pool infrastructure failure retained; no automatic model retry')
        judgments={'J0':J0().judge(pool),'J2':region_blocked(pool)}
        selected=shared.select(pool,judgments['J0']);selections['B']=next((c for c in pool_rows if c['id']==selected),None)
        timings['B']=time.perf_counter()-start;scopes['B']=[w['scope'] for w in workers]
        start=time.perf_counter();judgments['J3']=judge('judge-input',pool)
        view={'task':task['prompt'],'pool':pool,'judgments':[judgments['J3']]}
        prompt=task['prompt']+'\nAct as an independent Reviewer. Read input.json, consider every A/B/C candidate including failures. Freely implement a new M from this baseline, or explicitly REFUSE. Preserve existing tests/dependencies. Report every considered candidate ID and commit cleanly.'
        w=launch('reviewer','codex','reviewer',view=view,prompt=prompt);m=shared.candidate('M',w)
        decision=w.get('answer',{}).get('decision',{})
        considered=decision.get('considered_candidates',[])
        if w['status']=='COMPLETED' and (not isinstance(considered,list) or not all(isinstance(cid,str) for cid in considered) or sorted(considered)!=['A','B','C'] or decision.get('action')!='IMPLEMENTED'):m['verdict']='FAIL'
        expanded=shared.public_pool(pool_rows+[m],'JUDGE_COMPARISON');jm=judge('judge-merge',expanded)
        exclusive_json(root/'frozen-expanded-public-pool.json',expanded)
        chosen=enhanced_selection(pool,expanded,judgments['J3'],jm);enhanced=next((c for c in pool_rows+[m] if c['id']==chosen),None)
        shared.ACTIVE['enhancement_judge_incomplete']=judgments['J3']['status']!='COMPLETED' or jm['status']!='COMPLETED'
        selections['C']=enhanced;timings['C']=timings['B']+time.perf_counter()-start
        scopes['C']=scopes['B']+[shared.ACTIVE['workers'][name]['scope'] for name in ('judge-input','reviewer','judge-merge')]
        exclusive_json(root/'merge-ablation-public.json',{'pool_hash':pool['pool_hash'],'best_of_n':selected,'with_m':chosen,'judgment':jm,
            'all_originals_failed_visible':all(c['verdict']!='PASS' for c in pool_rows)})
        transfer=enhanced or next((c for c in pool_rows+[m] if c['id']==(jm.get('ranking') or ['M'])[0]),m)
        for arm,name,prior,prior_seconds,mode in [('D','native-sol',None,0,'native_driver'),('E','relay',raw,timings['A'],'humanize_flow'),('F','enhanced-relay',transfer,timings['C'],'humanize_flow')]:
            start=time.perf_counter();source=Path(prior['root'])/'code' if prior else None
            public={'task':task['prompt'],'prior':{k:prior.get(k) for k in ('id','head_commit','patch','test_report','verdict')} if prior else None}
            w=launch(name,'codex',source=source,view=public,mode=mode,prompt=task['prompt']+'\nAct as a fresh Builder. Inspect and improve the current program, freely redesign if needed, run public checks, and commit a clean change.')
            selections[arm]=shared.candidate(arm,w);timings[arm]=prior_seconds+time.perf_counter()-start
            scopes[arm]=([*scopes['A']] if arm=='E' else [*scopes['C']] if arm=='F' else [])+[w['scope']]
        judgments['J1']=lav('J1',pool)
        exclusive_json(root/'merge-judgments.json',{'J0':J0().judge(expanded),'J1':lav('J1-merge',expanded),'J2':region_blocked(expanded),'J3':jm})
        exclusive_json(root/'judgments.json',judgments)
        exclusive_json(root/'frozen-selections.json',{'heads':{arm:c.get('head_commit') if c else None for arm,c in selections.items()},
            'public_candidate_hashes':{arm:digest(c) if c else None for arm,c in selections.items()},'hidden_results_seen':False})
        active=time.perf_counter()-started
        # All model work is now finished; long independent acceptance has its own
        # recorded watchdog and is not presented as free model activity.
        shared.ACTIVE['key']='';accepted={};results=[];truth={};oracle_started=time.perf_counter()
        all_candidates={c['id']:c for c in [raw,*pool_rows,m,*[c for c in selections.values() if c is not None]]}
        for cid,c in all_candidates.items():
            identity=digest({'patch':c.get('patch'),'source':c.get('source')})
            if c['verdict']!='PASS' or c['worker_status']!='COMPLETED':
                checked={'verdict':'FAIL','private_execution':'NOT_RUN_PUBLIC_HARD_GATE_FAILED','elapsed_seconds':0,
                         'reason':'Completion, clean commit, protected files and public checks are mandatory before numerical acceptance'}
            else:
                if identity not in accepted:
                    try:accepted[identity]=tester(Path(c['root'])/'code',True)
                    except (ValueError,OSError,KeyError,TypeError) as error:
                        accepted[identity]={'verdict':'FAIL','error_type':type(error).__name__,'reason':str(error)[:500],'elapsed_seconds':0}
                checked=accepted[identity]
            truth[cid]={'program_identity':identity,'worker_status':c['worker_status'],'public_verdict':c['verdict'],'acceptance':checked}
            exclusive_json(root/('private-acceptance-'+cid+'.json'),truth[cid])
        exclusive_json(root/'private-candidate-acceptance.json',truth)
        for arm,c in selections.items():
            results.append(record(arm,c,scopes[arm],timings[arm],truth[c['id']]['acceptance'] if c else None))
        receipt={'status':'MAIN_TASK_COMPLETED','task_id':task['id'],'run_id':root.name,'results':results,
                 'model_activity_seconds':active,'controller_end_to_end_seconds':time.perf_counter()-started,
                 'common_generation_timeout_seconds':115,'judgments':{k:v['status'] for k,v in judgments.items()},
                 'benchmark_oracle_audit_seconds':time.perf_counter()-oracle_started,'private_unique_program_evaluations':len(accepted),
                 'full_tool_trace_sensitivity':'PENDING_SEPARATE_SAME_POOL_REVIEW','failures_preserved':True,'api_cash_usd':'unavailable'}
        exclusive_json(root/'receipt.json',receipt)
        return {k:v for k,v in receipt.items() if k!='results'}|{'arms':{r['arm']:r['outcome'] for r in results}}


if __name__=='__main__':
    payload=json.load(sys.stdin)
    try:
        value=run(payload);print(json.dumps(value),flush=True)
        if value.get('status')=='FAIL':raise SystemExit(1)
    except Exception as error:
        import traceback
        if shared.ACTIVE.get('root'):
            exclusive_json(shared.ACTIVE['root']/'failure.json',{'status':'INFRA_FAIL','error_type':type(error).__name__,'traceback':traceback.format_exc(),
                'completed_arms':[p.name for p in shared.ACTIVE['root'].glob('arm-*.json')]})
        print(json.dumps({'status':'INFRA_FAIL','error_type':type(error).__name__}),flush=True);raise
