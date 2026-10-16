"""Fresh paired guidance study over the sixteen frozen tasks.

The official Humanize/DSH/Codex drivers retain all model/tool execution. This
controller only binds checkpoints, read-only guidance, accounting and oracles.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback

sys.path[:0] = [str(Path(__file__).parent), str(Path(__file__).parent/'src'),
    '/opt/workbench/benchmark/envs/science-tms-v1/lib/python3.12/site-packages']
import p6_main_runtime_linux as main
from p6_main_budget import MainLedger, task_limits, BudgetDenied
from p6_guidance_protocol import (TASKS, BRANCHES, DS_ROLES, SOL_ROLES, digest,
    branch_order, mentor_view, validate_guidance, validate_plan)
from p6_network_policy import RETRY10_POLICY
from p6_trace_evidence import tool_trace
from pi_full_protocol import Journal, UncertainStage, exclusive

shared = main.shared
BASE = Path('/opt/workbench/benchmark/private/guidance')
LEDGER = Path('/opt/workbench/state/p6-main-local-20261011/ledger.json')


def read(path):return json.loads(Path(path).read_bytes())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_task(payload, tid):
    row = next(t for t in payload['plan']['manifest']['tasks'] if t['task_id'] == tid)
    tp = {'task': row, 'manifest': payload['plan']['manifest'], 'budget': payload['budget']}
    if row['family'] == 'scientific':
        import p6_science_main_linux as science
        task = science.task(tp)
        task['prompt'] += '\n'+Path(__file__).with_name('science-clarifications-v1.md').read_text()
        def tester(source, hidden=False):
            if hidden and task['kind'] == 'tms':
                from p6_tms_grader import grade
                tick = time.perf_counter()
                r = grade(source, science.SCIENCE/'intake/tms', task['prefix'],
                          per_call_timeout=180, rss_limit_mib=4096)
                return {'verdict':'INDETERMINATE' if r['verdict']=='PASS' else r['verdict'],
                    'numeric_verdict': 'PASS_NUMERIC_REVIEW_PENDING' if r['verdict']=='PASS' else r['verdict'],
                    'detail':r, 'elapsed_seconds':time.perf_counter()-tick}
            return science.test(source, hidden)
    else:
        task = main.public_task(tp); tester = main.public_test
        if tid == 'SWEL-pytest-dev__pytest-11148':
            name = 'testing/test_pathlib.py'; raw = (Path(task['base'])/name).read_bytes()
            anchor = b"        # mode='importlib' fails if no spec is found to load the module\n"
            if raw.count(anchor) != 1:raise ValueError('Pinned public cache-test context differs')
            task['public_overlays'][name] = raw.replace(anchor,b'        del sys.modules[module.__name__]\n\n'+anchor)
            def tester(source, hidden=False):
                if not hidden:return main.public_test(source, False)
                overlays = task['public_overlays']; task['public_overlays'] = {k:v for k,v in overlays.items() if k!=name}
                try:return main.public_test(source, True)
                finally:task['public_overlays'] = overlays
    from p6_gate_policy import GENERATION_RULES
    task['prompt'] += '\n'+GENERATION_RULES
    return tp, task, tester


def activate(root, payload, tp, task, tester, fixture_url, *, offline=False):
    limits = task_limits(payload['budget'], tp['task'])
    shared.ACTIVE.clear(); shared.ACTIVE.update(root=root, task=task, payload=tp,
        ledger=MainLedger(LEDGER,payload['budget']), key=payload.get('key',''),
        deadline=time.monotonic()+limits['active_seconds'], generation_seconds=limits['role_seconds'],
        active_seconds=limits['active_seconds'], workers={}, main_phase=True, defer_hidden=True,
        fixture_url=fixture_url)
    shared.LEDGER_PATH = LEDGER; shared.test_source = tester


def bind(payload, *, ledger=True):
    plan = validate_plan(payload['plan'])
    for path, expected in {**plan['source_sha256'], **plan['retained_sha256']}.items():
        if sha(path) != expected:raise ValueError('Frozen source or retained evidence changed: '+path)
    if payload['budget'] != plan['budget']:raise ValueError('Authorization differs from plan')
    if ledger:
        MainLedger(LEDGER, payload['budget']).validate(read(LEDGER))
        prior = read(plan['ledger_archive']); current = read(LEDGER)
        if (current['requests'][:len(prior['requests'])] != prior['requests'] or
            current['codex_turns'][:len(prior['codex_turns'])] != prior['codex_turns']):
            raise ValueError('Historical ledger prefix changed')
    return plan


def setup(root, payload, name, backend, role='builder', source=None, view=None, prompt=None, offline=False):
    descriptor, env = main.job(name, backend, role, source=source, view=view, prompt=prompt,
                               mode='humanize_flow' if role=='verifier' else 'native_driver', offline=offline,handoff_bytes=8_000_000)
    descriptor['scope'] = 'GUIDANCE/'+payload['run_id']+'/'+shared.ACTIVE['task']['id']+'/'+name
    if role == 'verifier':descriptor['guidance_mentor'] = True
    else:descriptor['deepseek_transport_policy'] = RETRY10_POLICY
    # Probe both the ordinary denied canaries and the exact trace/control files.
    for peer in root.glob('*/input.json'):
        if str(peer) != descriptor['input_file']:descriptor['denied_paths'].append(str(peer))
    withheld=root/'control/withheld-trace.json'
    if withheld.exists():descriptor['denied_paths'].append(str(withheld))
    return {'descriptor':descriptor, 'env':env}


def execute(spec):
    descriptor=spec['descriptor']
    if not descriptor.get('offline_control'):
        ledger=shared.ACTIVE['ledger'];value=read(LEDGER);ledger.validate(value)
        if descriptor['backend']=='dsh' and (len(value['requests'])>=ledger.requests or
            value['cash_bound_nano']+ledger.request_reserve>ledger.cash_nano):
            raise BudgetDenied('Cumulative budget exhausted before a new role; preserve all substeps')
    worker=shared.launch(descriptor,spec['env'])
    shared.ACTIVE['workers'][Path(descriptor['root']).name]=worker
    return worker


def freeze(candidate):
    return {'candidate_sha256':digest(candidate), 'head_commit':candidate.get('head_commit'),
        'program_sha256':digest({'patch':candidate.get('patch'), 'source':candidate.get('source')}),
        'private_results_seen':False}


def verify(candidate, frozen):
    patch,source=shared.program_evidence(Path(candidate['root'])/'code',candidate['base_commit'])
    if (digest(candidate)!=frozen['candidate_sha256'] or
        digest({'patch':patch,'source':source})!=frozen['program_sha256']):
        raise ValueError('Frozen candidate program changed')


def task_run(root, payload, tid):
    dest=root/tid; dest.mkdir(exist_ok=True); (dest/'control').mkdir(exist_ok=True)
    canary=dest/'control/canary'
    if not canary.exists():canary.write_text('Private controller state; no candidate access')
    withheld=dest/'control/withheld-trace.json'
    if not withheld.exists():exclusive(withheld,{'private_control_trace':'never readable by any role'})
    journal=Journal(dest/'control/stages'); tp,task,tester=make_task(payload,tid)
    with task['fixture_context'] as url:
        activate(dest,payload,tp,task,tester,url)
        spec=journal.run('initial-setup',lambda:setup(dest,payload,'initial-ds','dsh'))
        initial_worker=journal.run('initial-model',lambda:execute(spec))
        shared.ACTIVE['workers']['initial-ds']=initial_worker
        initial=journal.run('initial-public',lambda:shared.candidate('initial-ds',initial_worker))
        initial_frozen=journal.run('initial-freeze',lambda:freeze(initial))
        if not all(k in initial for k in ('patch','source','head_commit')):
            return {'task_id':tid,'status':'INITIAL_EVIDENCE_UNAVAILABLE','initial_worker':initial_worker,'initial':initial}
        trace=journal.run('initial-trace',lambda:tool_trace(dest/'initial-ds',max_bytes=7_000_000))
        mentors={}; branches={}; initial_work=Path(initial['root'])/'code'
        for branch in branch_order(tid):
            name=branch+'-mentor'; view=mentor_view(initial,task['prompt'],trace if branch.endswith('-trace') else None)
            prompt=('Read the complete input.json next to your worktree and inspect this initial DS program. '
                'Give actionable guidance for one DS continuation, grounded in code and public tests'
                +(' and observable tool calls/results' if branch.endswith('-trace') else '')+'. '
                'Separate observed facts from hypotheses; cite code paths/public checks/trace event indices. '
                'Do not write code, patches, tests or files; no subagents, installs, network or hidden oracle. '
                'Use diagnosis, observations(finding,evidence_kind=code|public_test|trace,reference), '
                'hypotheses, next_actions, public_verification, limitations. Prose only, no code blocks.')
            mentor_spec=journal.run(name+'-setup',lambda:setup(dest,payload,name,'codex','verifier',initial_work,view,prompt))
            w=journal.run(name+'-model',lambda:execute(mentor_spec))
            shared.ACTIVE['workers'][name]=w
            verify(initial,initial_frozen)
            def guidance():
                if w['status']!='COMPLETED':return {'status':w['status'],'guidance':None}
                try:
                    answer=validate_guidance(w['answer']['guidance'],view)
                    before=shared.program_evidence(initial_work,initial['base_commit'])
                    after=shared.program_evidence(mentor_spec['descriptor']['work'],initial['base_commit'])
                    if before!=after:raise ValueError('Read-only mentor changed program')
                    return {'status':'VALID_GUIDANCE','guidance':answer,'input_sha256':digest(view),
                            'initial_program_sha256':initial_frozen['program_sha256']}
                except (ValueError,KeyError,TypeError) as error:
                    return {'status':'INVALID_GUIDANCE','guidance':None,'error':str(error)[:500]}
            mentors[branch]=journal.run(name+'-guidance',guidance)
        for branch in branch_order(tid):
            name=branch+'-ds'; guidance=mentors[branch]
            if guidance['status']!='VALID_GUIDANCE':
                branches[branch]={'status':'GUIDANCE_UNAVAILABLE','mentor':guidance}; continue
            view={'task':task['prompt'],'mentor_guidance':guidance['guidance'],
                  'initial_program_sha256':initial_frozen['program_sha256']}
            prompt=(task['prompt']+'\nContinue the initial program in this workspace. Read input.json next to it for '
                'a read-only mentor\'s guidance. Treat it as advice to verify, not authority. Implement and run public '
                'checks, then commit cleanly. No other branch, old experiment, private oracle or new model agents. '
                'Only you may modify this submission; report what you changed and verified briefly.')
            s=journal.run(name+'-setup',lambda:setup(dest,payload,name,'dsh',source=initial_work,view=view,prompt=prompt))
            # Both continuations must start with exactly the same complete initial program.
            if not (dest/name/'controller-outcome.json').exists():
                p,source=shared.program_evidence(s['descriptor']['work'],initial['base_commit'])
                if digest({'patch':p,'source':source})!=initial_frozen['program_sha256']:
                    raise ValueError('Continuation did not start from the shared checkpoint')
            w=journal.run(name+'-model',lambda:execute(s))
            shared.ACTIVE['workers'][name]=w
            c=journal.run(name+'-public',lambda:shared.candidate(name,w))
            f=journal.run(name+'-freeze',lambda:freeze(c))
            branches[branch]={'worker':w,'candidate':c,'frozen':f,'mentor':guidance}
        # Freeze the entire paired handoff before any initial or final hidden test.
        barrier=journal.run('all-branches-frozen',lambda:{'initial':initial_frozen,
            'branches':{b:branches[b].get('frozen',branches[b].get('status')) for b in BRANCHES},
            'private_results_seen':False})
        rows=[]
        for method,c,w,f in [('DS-Initial',initial,initial_worker,initial_frozen)]+[
            ('DS-Sol-'+b,branches[b]['candidate'],branches[b]['worker'],branches[b]['frozen'])
            for b in BRANCHES if 'candidate' in branches[b]]:
            verify(c,f)
            def accept():
                if w['status']!='COMPLETED' or c['verdict']!='PASS':
                    return {'verdict':'NOT_RUN','reason':'Completed clean public candidate required','elapsed_seconds':0}
                try:return tester(Path(c['root'])/'code',True)
                except (OSError,ImportError,KeyError,TypeError,ValueError) as error:
                    return {'verdict':'INFRA_FAIL','error_type':type(error).__name__,'reason':str(error)[:700],'elapsed_seconds':0}
            acceptance=journal.run(method.replace('DS-Sol-','').replace('DS-Initial','initial')+'-acceptance',accept)
            verify(c,f)
            outcome=acceptance['verdict'] if w['status']=='COMPLETED' and c['verdict']=='PASS' else 'FAIL' if w['status']=='COMPLETED' else w['status']
            rows.append({'method':method,'task_id':tid,'outcome':outcome,'worker':w,'candidate':c,
                'acceptance':acceptance,'frozen':f,'barrier_sha256':digest(barrier),
                'scientific_review':'PENDING_SOL_SOURCE_REPORT_FIGURE' if outcome=='INDETERMINATE' else 'NOT_APPLICABLE_OR_NOT_NUMERIC_PASS'})
        measured=sum(w['wall_seconds'] for w in shared.ACTIVE['workers'].values())+sum(
            c.get('test_report',{}).get('elapsed_seconds',0) for c in [initial]+[
            branches[b]['candidate'] for b in BRANCHES if 'candidate' in branches[b]])
        return {'task_id':tid,'status':'TASK_EXECUTION_COMPLETED','rows':rows,'branches':branches,
            'initial':initial,'initial_worker':initial_worker,'branch_order':list(branch_order(tid)),
            'barrier_sha256':digest(barrier),'model_and_public_seconds':measured,
            'metrics':shared.metrics([w['scope'] for w in shared.ACTIVE['workers'].values()],measured)}


def controls(payload):
    bind(payload,ledger=False); before=sha(LEDGER)
    root=BASE/(payload['run_id']+'-controls');root.mkdir(parents=True)
    # Exercise the official Flow/schema machinery with its upstream fake driver;
    # the OS-fenced controls below independently check the real permissions.
    import asyncio
    from hmz.flows import load
    from hmz.sdk import fakes
    guidance={'diagnosis':'Boundary omitted','observations':[{'finding':'Boundary omitted','evidence_kind':'code','reference':'solver.py:10'}],
        'hypotheses':['Potential index error'],'next_actions':['Check boundary'],
        'public_verification':['Run public boundary test'],'limitations':['No hidden oracle']}
    async def flow_control():
        driver=fakes.FakeAgentDriver(harness='codex',reply=json.dumps(guidance),cost=0.0)
        answer=await fakes.run_fake(load(str(Path(__file__).parent/'flows/sol_guidance')),
            'Return supplied guidance',agents={'verifier':driver})
        validate_guidance(answer['guidance'],{})
        if len(driver.prompts)!=1:raise ValueError('Exactly one official fake mentor turn required')
        return {'status':'PASS_OFFICIAL_HUMANIZE_FLOW_FAKE','model_calls':0}
    flow_receipt=asyncio.run(flow_control());rows=[]
    for tid in TASKS:
        dest=root/tid;dest.mkdir();(dest/'control').mkdir();(dest/'control/canary').write_text('private')
        exclusive(dest/'control/withheld-trace.json',{'private_control_trace':'must be denied'})
        tp,task,tester=make_task(payload,tid)
        with task['fixture_context'] as url:
            activate(dest,payload,tp,task,tester,url,offline=True)
            for name,backend,role in [('initial-ds','dsh','builder'),('code-tests-mentor','codex','verifier')]:
                s=setup(dest,payload,name,backend,role,offline=True)
                if role=='builder' and task.get('kind') not in ('gc','egl'):
                    # Baseline public checks are not expected to solve the task.
                    s['descriptor'].pop('offline_public_command',None)
                w=execute(s)
                rows.append({'task_id':tid,'role':role,'status':w['status'],
                    'isolation':read(Path(w['root'])/'isolation.json')})
    okay=len(rows)==32 and all(r['status']=='COMPLETED' and r['isolation']['verdict']=='PASS' for r in rows) and sha(LEDGER)==before
    r={'status':'PASS_GUIDANCE_ZERO_MODEL_CONTROLS' if okay else 'CONTROLS_FAILED',
        'rows':rows,'official_flow_control':flow_receipt,'source_sha256':payload['plan']['source_sha256'],'plan_sha256':payload['plan']['plan_sha256'],
        'ledger_sha256_before':before,'ledger_sha256_after':sha(LEDGER),'model_calls':0}
    exclusive(root/'receipt.json',r);return {'status':r['status'],'receipt':str(root/'receipt.json')}


def compare(payload):
    plan=bind(payload); root=BASE/payload['run_id']; root.mkdir(parents=True,exist_ok=True)
    controls_receipt=read(plan['controls_receipt'])
    if (controls_receipt['status']!='PASS_GUIDANCE_ZERO_MODEL_CONTROLS' or
        controls_receipt['source_sha256']!=plan['source_sha256'] or controls_receipt['plan_sha256']!=plan['plan_sha256']):
        raise ValueError('Actual exact-source zero-model controls required')
    journal=Journal(root/'stages'); results=[]; status='GUIDANCE_EXECUTION_COMPLETED'
    if not (root/'plan.json').exists():exclusive(root/'plan.json',plan)
    elif read(root/'plan.json')!=plan:raise ValueError('Existing plan differs; no replay')
    try:
        for tid in TASKS:
            if not (root/'stages'/(tid+'.completed.json')).exists():
                v=read(LEDGER);ledger=MainLedger(LEDGER,payload['budget'])
                if len(v['requests'])>=ledger.requests or v['cash_bound_nano']+ledger.request_reserve>ledger.cash_nano:
                    status='CUMULATIVE_BUDGET_STOP';break
            # Task is deliberately not marked started: its completed substeps are reusable.
            final=root/'stages'/(tid+'.completed.json')
            if final.exists():result=journal.run(tid,lambda:None)
            else:
                result=task_run(root,payload,tid)
                exclusive(final,{'stage':tid,'value':result,'value_sha256':digest(result)})
            results.append(result)
            (root/'progress.json').write_text(json.dumps({'status':'RUNNING','completed_tasks':len(results),'total_tasks':16,
                'last_task':tid,'ledger_requests':len(read(LEDGER)['requests']),'checked_unix':time.time()},indent=2))
    except BaseException as error:
        status='UNCERTAIN_STAGE_REQUIRES_RECONCILIATION' if isinstance(error,UncertainStage) else 'STOPPED_PRESERVED'
        exclusive(root/('error-'+str(time.time_ns())+'.json'),{'error_type':type(error).__name__,
            'message':str(error)[:1000],'traceback':traceback.format_exc()[-6000:]})
    r={'status':status,'completed_tasks':len(results),'total_tasks':16,'results':results,
        'plan_sha256':plan['plan_sha256'],'ledger_sha256':sha(LEDGER),'finished_unix':time.time(),
        'actual_cash':'unavailable','scientific_review':'SEPARATE_SOL_REVIEW_REQUIRED','old_experiment_replays':0}
    exclusive(root/('receipt-'+str(time.time_ns())+'.json'),r)
    (root/'progress.json').write_text(json.dumps({k:v for k,v in r.items() if k!='results'},indent=2))
    return {'status':status,'completed_tasks':len(results),'root':str(root)}


def entry(payload):
    from p1_broker import protect_memory
    protect_memory()
    if os.getuid()==0:raise ValueError('Non-root controller required')
    BASE.mkdir(parents=True,exist_ok=True)
    # The same global lock excludes older Pi executors and scientific recoveries.
    with Path('/opt/workbench/pi-comparison/full-main-owner.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return controls(payload) if payload['mode']=='controls' else compare(payload)


if __name__=='__main__':print(json.dumps(entry(json.load(sys.stdin))))
