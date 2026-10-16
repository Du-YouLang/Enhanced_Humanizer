"""Resume one interrupted mentor, reuse eleven tasks, then run four new tasks."""
import fcntl,json,math,os,shutil,subprocess,sys,time,traceback
from pathlib import Path
sys.path[:0]=[str(Path(__file__).parent),str(Path(__file__).parent/'src')]
import p6_guidance_linux as fixed
from p6_guidance_protocol import digest
from p6_guidance_shutdown import SOURCE_RUN,PARTIAL_TASK,MENTOR,SESSION_ID,NEW_TASKS,REMAINING_ROLES,scope,allow_science,remaining_seconds
from pi_full_protocol import Journal,exclusive

def read(path):return json.loads(Path(path).read_bytes())

def snapshot(value):
    """Read the accepted checkpoint and archive the same ledger under the lock."""
    from p6_main_budget import MainLedger
    original=value['original'];oldroot=fixed.BASE/SOURCE_RUN
    shutdown=read('/opt/workbench/guidance/'+SOURCE_RUN+'-shutdown-acceptance-20261016.json')
    if shutdown['status']!='USER_SHUTDOWN_CHECKPOINT_ACCEPTED' or shutdown['completed_model_roles']!=56 or shutdown['completed_tasks']!=11:
        raise ValueError('Exact accepted shutdown checkpoint required')
    with Path('/opt/workbench/pi-comparison/full-main-owner.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        ledger=read(fixed.LEDGER);MainLedger(fixed.LEDGER,value['budget']).validate(ledger)
        if fixed.sha(fixed.LEDGER)!=shutdown['ledger']['sha256']:raise ValueError('Shutdown ledger changed; reconcile')
        pins=shutdown['checkpoint_sha256'].copy()
        for path,expected in {**original['plan']['source_sha256'],**original['plan']['retained_sha256'],**pins}.items():
            if fixed.sha(path)!=expected:raise ValueError('Accepted shutdown evidence changed: '+path)
        stages=oldroot/PARTIAL_TASK/'control/stages';name=MENTOR+'-model'
        if (stages/(name+'.completed.json')).exists():raise ValueError('Interrupted mentor already completed; do not replay')
        setup=read(stages/(MENTOR+'-setup.completed.json'))['value']
        role=Path(setup['descriptor']['root'])
        if (role/'worker.json').exists() or (role/'controller-outcome.json').exists():raise ValueError('Unexpected terminal mentor receipt; reconcile')
        traces=list(role.glob('humanize/epics/*/*/sessions/codex/sessions/*/*/*/rollout-*.jsonl'))
        if len(traces)!=1:raise ValueError('Exactly one original mentor conversation required')
        trace=traces[0];events=[json.loads(line) for line in trace.read_text().splitlines()]
        metas=[e['payload'] for e in events if e.get('type')=='session_meta']
        if len(metas)!=1 or metas[0]['id']!=SESSION_ID:raise ValueError('Original official session identity differs')
        if any(e.get('payload',{}).get('type')=='task_complete' for e in events):raise ValueError('A final answer exists; reconcile instead of resuming')
        usage=[e['payload']['info']['total_token_usage'] for e in events if e.get('type')=='event_msg'
            and e.get('payload',{}).get('type')=='token_count' and e['payload'].get('info')][-1]
        stop=read('/opt/workbench/guidance/'+SOURCE_RUN+'-user-shutdown-20261016.json')
        debit,remaining=remaining_seconds((stages/(name+'.started.json')).stat().st_mtime,stop['finished_unix'],setup['descriptor']['role_seconds'])
        if sum(r['experiment']==scope(MENTOR) for r in ledger['codex_turns'])!=1:raise ValueError('Original mentor reservation must occur exactly once')
        for remaining_role in REMAINING_ROLES:
            if (stages/(remaining_role+'-model.started.json')).exists() or any(r['experiment']==scope(remaining_role) for r in ledger['requests']+ledger['codex_turns']):
                raise ValueError('An expected unpaid partial role already started; reconcile')
        store=next(p for p in trace.parents if p.name=='codex' and p.parent.name=='sessions')
        store_pins={str(p):fixed.sha(p) for p in store.rglob('*') if p.is_file()}
        if any(p.is_symlink() for p in store.rglob('*')):raise ValueError('Unexpected session-store symlink')
        pins.update(store_pins)
        guarded_attempt=fixed.BASE/'guidance-20261016T155049Z'
        if guarded_attempt.exists():
            guarded_receipts=list(guarded_attempt.glob('receipt-*.json'))
            if not guarded_receipts or any(read(p)['status']!='STOPPED_PRESERVED' for p in guarded_receipts):
                raise ValueError('Earlier zero-dispatch budget-guard attempt requires reconciliation')
            for p in [*guarded_receipts,*guarded_attempt.glob('error-*.json'),
                *guarded_attempt.glob('control/stages/*.json'),*guarded_attempt.glob('resumed-mentor/*.json')]:
                pins[str(p)]=fixed.sha(p)
        programs=[];bases={t['task_id']:t['base_commit'] for t in original['plan']['manifest']['tasks']}
        for origin in (fixed.BASE/'guidance-20261016T060944Z',oldroot):
            for path in origin.glob('*/*/controller-outcome.json'):
                w=read(path);tid=path.parents[1].name
                patch,source=fixed.shared.program_evidence(w['work'],bases[tid])
                programs.append({'work':w['work'],'base_commit':bases[tid],'sha256':digest({'patch':patch,'source':source})})
        if len(programs)!=56:raise ValueError('Exactly 56 completed programs must be retained')
        archive=Path('/opt/workbench/guidance')/(value['run_id']+'-ledger-prefix.json')
        with archive.open('xb') as stream:stream.write(fixed.LEDGER.read_bytes())
        pins[str(archive)]=fixed.sha(archive)
        return {'source_run':SOURCE_RUN,'shutdown_receipt':shutdown['terminal_receipt'],
            'checkpoint_sha256':pins,'model_programs':programs,'ledger_archive':str(archive),
            'session_id':SESSION_ID,'session_trace':str(trace),'session_store':str(store),'session_store_sha256':store_pins,
            'prior_usage':usage,'prior_seconds':debit,'remaining_role_seconds':remaining,
            'partial_task':PARTIAL_TASK,'new_tasks':list(NEW_TASKS),'original_payload':original,
            'retained_sha256':{**original['plan']['retained_sha256'],**original['plan']['source_sha256'],**pins},
            'old_ledger_requests':len(ledger['requests']),'old_subscriptions':len(ledger['codex_turns']),
            'old_cash_bound_usd':ledger['cash_bound_nano']/1e9}

def resume_spec(payload,dest,*,offline=False):
    details=payload['plan']['shutdown_continuation'];oldroot=fixed.BASE/SOURCE_RUN
    old=read(oldroot/PARTIAL_TASK/'control/stages'/(MENTOR+'-setup.completed.json'))['value']
    dest=Path(dest);dest.mkdir(parents=True,exist_ok=False)
    env=dict(old['env']);env.update(fixed.shared.candidate_env(dest))
    # Keep exact task runtime/search path and the old immutable input/worktree.
    for key in ('PATH','PYTHONHASHSEED','GIT_CONFIG_GLOBAL','GIT_CONFIG_NOSYSTEM'):
        if key in old['env']:env[key]=old['env'][key]
    codex=Path(env['HOME'])/'.codex';codex.mkdir()
    (codex/'auth.json').symlink_to('/opt/workbench/state/codex/auth.json')
    original_home=Path(old['env']['CODEX_HOME'])
    if (original_home/'config.toml').exists():shutil.copy2(original_home/'config.toml',codex/'config.toml')
    env['CODEX_HOME']=str(codex)
    keeps=dest/'resume-sessions';keeps.mkdir()
    shutil.copytree(details['session_store'],keeps/'codex')
    for name,expected in details['session_store_sha256'].items():
        copied=keeps/'codex'/Path(name).relative_to(details['session_store'])
        if fixed.sha(copied)!=expected or fixed.sha(name)!=expected:raise ValueError('Original session copy differs')
    from p6_guidance_session_resume import relocate
    relocation=relocate(keeps/'codex',details['session_id'])
    # The thread index stores an absolute rollout path. Its isolated copy now
    # points at the identical copied JSONL; no original database/history changes.
    home=keeps/'codex';(home/'auth.json').symlink_to('/opt/workbench/state/codex/auth.json')
    if (codex/'config.toml').exists():shutil.copy2(codex/'config.toml',home/'config.toml')
    env['CODEX_HOME']=str(home)
    exclusive(dest/'session-relocation.json',relocation)
    billing_scope='GUIDANCE/'+payload['run_id']+'/'+PARTIAL_TASK+'/'+MENTOR
    job=dict(old['descriptor']);job.update(root=str(dest),scope=billing_scope,offline_control=offline,
        parent_namespace=os.readlink('/proc/self/ns/pid'),role_seconds=details['remaining_role_seconds'],
        guidance_session_resume={k:details[k] for k in ('session_id','prior_usage','prior_seconds')})
    job['guidance_session_resume']['keeps']=str(keeps)
    job['guidance_session_resume'].update(original_scope=scope(MENTOR),billing_scope=billing_scope)
    job['denied_paths']=list(job['denied_paths'])+[str(dest.parent/'control/canary')]
    return {'descriptor':job,'env':env}

def controls(payload,root):
    tp,task,tester=fixed.make_task(payload,PARTIAL_TASK)
    (root/'control').mkdir(exist_ok=True);(root/'control/canary').write_text('private resume control')
    with task['fixture_context'] as url:
        fixed.activate(root,payload,tp,task,tester,url,offline=True)
        spec=resume_spec(payload,root/'interrupted-mentor-probe',offline=True)
        # Exercise the actual reservation gate on a separate synthetic ledger;
        # never amend or append to the real project ledger during controls.
        from p6_main_budget import MainLedger,BudgetDenied
        accounting=MainLedger(root/'control/resume-accounting-fixture.json',payload['budget'])
        accounting.reserve_codex_turn(scope(MENTOR),'gpt-6.1-sol')
        try:accounting.reserve_codex_turn(scope(MENTOR),'gpt-6.1-sol')
        except BudgetDenied:pass
        else:raise ValueError('Original subscription role replay was not denied')
        accounting.reserve_codex_turn(spec['descriptor']['scope'],'gpt-6.1-sol')
        if len(read(accounting.path)['codex_turns'])!=2:raise ValueError('Both linked activity reservations must remain')
        before=fixed.sha(fixed.LEDGER);worker=fixed.execute(spec)
    result=read(Path(worker['root'])/'worker.json')
    if worker['status']!='COMPLETED' or result.get('session_resume_probe',{}).get('status')!='PASS_OFFICIAL_THREAD_RESUME_ZERO_INFERENCE':
        raise ValueError('Actual read-only official thread-resume control failed')
    if fixed.sha(fixed.LEDGER)!=before:raise ValueError('Zero-inference probe changed the ledger')
    return {'status':'PASS_OFFICIAL_RESUME_FENCE_ZERO_INFERENCE','worker':worker,'model_calls':0,'ledger_unchanged':True,
        'accounting_control':'PASS_LINKED_CONTINUATION_NO_OLD_SCOPE_REPLAY'}

def validate(payload):
    fixed.bind(payload);details=payload['plan']['shutdown_continuation']
    if details['source_run']!=SOURCE_RUN or details['new_tasks']!=list(NEW_TASKS):raise ValueError('Exact shutdown suffix required')
    for row in details['model_programs']:
        patch,source=fixed.shared.program_evidence(row['work'],row['base_commit'])
        if digest({'patch':patch,'source':source})!=row['sha256']:raise ValueError('Retained completed program changed')
    control=read(payload['plan']['controls_receipt'])
    if control['status']!='PASS_GUIDANCE_ZERO_MODEL_CONTROLS' or control.get('resume_control',{}).get('status')!='PASS_OFFICIAL_RESUME_FENCE_ZERO_INFERENCE':
        raise ValueError('Exact actual resume controls required')
    if control['plan_sha256']!=payload['plan']['plan_sha256']:raise ValueError('Control plan differs')

def run(payload):
    from p1_broker import protect_memory
    protect_memory();validate(payload)
    root=fixed.BASE/payload['run_id'];root.mkdir(parents=True,exist_ok=True)
    exclusive(root/'plan.json',payload['plan']);(root/'control').mkdir(exist_ok=True)
    (root/'control/canary').write_text('private continuation controller')
    journal=Journal(root/'control/stages');details=payload['plan']['shutdown_continuation']
    previous=read(details['shutdown_receipt']);results=list(previous['results']);supplements=previous['supplements']
    status='GUIDANCE_SHUTDOWN_CONTINUATION_COMPLETED'
    try:
        tp,task,tester=fixed.make_task(payload,PARTIAL_TASK)
        with task['fixture_context'] as url:
            fixed.activate(root,payload,tp,task,tester,url)
            spec=journal.run('mentor-resume-setup',lambda:resume_spec(payload,root/'resumed-mentor'))
            worker=journal.run('mentor-resume-model',lambda:fixed.execute(spec))
        if worker['status']!='COMPLETED' or worker.get('session_id')!=SESSION_ID:
            raise ValueError('Interrupted session did not complete; preserve for reconciliation')
        dest=root/'partial-result.json'
        def partial():
            command=[sys.executable,'-B',str(Path(__file__).with_name('p6_guidance_shutdown_child_linux.py'))]
            with (root/'partial.private.log').open('xb') as log:
                p=subprocess.run(command,input=json.dumps({'original':details['original_payload'],
                    'folder':payload['folder'],'worker':worker,'result':str(dest),'key':payload['key']}).encode(),
                    stdout=log,stderr=subprocess.STDOUT,timeout=6500)
            if p.returncode:raise RuntimeError('Partial task preserved; inspect its log without replay')
            return read(dest)
        results.append(journal.run('partial-task',partial))
        saved=fixed.shared.launch
        def guarded(job,env):
            if not allow_science(job['scope'],payload['run_id']):raise ValueError('Completed/partial model replay denied')
            return saved(job,env)
        fixed.shared.launch=guarded
        for tid in NEW_TASKS:
            result=fixed.task_run(root,payload,tid);exclusive(root/'control/stages'/(tid+'-task.completed.json'),
                {'stage':tid+'-task','value':result,'value_sha256':digest(result)})
            results.append(result)
            (root/'progress.json').write_text(json.dumps({'status':'RUNNING','completed_tasks':len(results),'total_tasks':16,'last_task':tid}))
    except BaseException as error:
        status='STOPPED_PRESERVED'
        exclusive(root/('error-'+str(time.time_ns())+'.json'),{'type':type(error).__name__,'reason':str(error)[:1500],'traceback':traceback.format_exc()[-6000:]})
    receipt={'status':status,'results':results,'supplements':supplements,'completed_tasks':len(results),'total_tasks':16,
        'plan_sha256':payload['plan']['plan_sha256'],'source_run':SOURCE_RUN,'ledger_sha256':fixed.sha(fixed.LEDGER),
        'scientific_review':'PENDING_SOL_SOURCE_REPORT_FIGURE','finished_unix':time.time(),'old_completed_model_replays':0}
    exclusive(root/('receipt-'+str(time.time_ns())+'.json'),receipt)
    (root/'progress.json').write_text(json.dumps({k:v for k,v in receipt.items() if k not in ('results','supplements')}))
    return {'status':status,'completed_tasks':len(results),'root':str(root)}

def entry(payload):
    with Path('/opt/workbench/pi-comparison/full-main-owner.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return run(payload)

if __name__=='__main__':print(json.dumps(entry(json.load(sys.stdin))))
