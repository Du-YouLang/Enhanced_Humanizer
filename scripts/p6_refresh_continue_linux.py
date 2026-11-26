"""User-resumed shutdown: one official judge thread, then only unpaid stages."""
import json,hashlib,time,os,shutil,math,fcntl,sys,traceback
from pathlib import Path
OLD='/opt/workbench/guidance/executor-fbf96ba9cf225ed7f235'
NEW=str(Path(__file__).parent)
sys.path[:0]=[OLD,OLD+'/src'];sys.path.append(NEW)
import p6_refresh_linux as fixed
from pi_full_protocol import Journal,digest,exclusive
from p6_refresh_session_resume import SESSION,ORIGINAL,relocate
BASE=Path('/opt/workbench/benchmark/private/model-refresh')
ROOT=BASE/'refresh-20261126T060538Z'

def read(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def prepare(v):
    root=BASE/v['continuation_id'];root.mkdir(exist_ok=False)
    partial=ROOT/'BIP-black-5/GPT61-Sol';setup=read(partial/'control/stages/judge-input-setup.completed.json')['value']
    stores=list((partial/'judge-input/humanize/epics').glob('*/*/sessions/codex'))
    if len(stores)!=1:raise ValueError('One original session store required')
    store=stores[0];traces=list(store.glob('sessions/*/*/*/rollout-*.jsonl'))
    if len(traces)!=1 or SESSION not in traces[0].name:raise ValueError('Original thread absent')
    usage=None
    for line in traces[0].read_text().splitlines():
        r=json.loads(line);d=r.get('payload',{})
        if d.get('type')=='task_complete':raise ValueError('Completed original judge must not resume')
        if d.get('type')=='token_count' and d.get('info'):usage=d['info']['total_token_usage']
    if not usage or any(type(usage.get(k))is not int or usage[k]<0 for k in ('input_tokens','cached_input_tokens','output_tokens','total_tokens')):raise ValueError('Original usage unavailable')
    completed=[]
    for p in (ROOT/'stages').glob('*.completed.json'):
        d=read(p)
        if d['value_sha256']!=digest(d['value']):raise ValueError('Group hash changed')
        for row in d['value']['rows']:
            if row.get('candidate'):fixed.old.verify(row['candidate'],row['frozen'])
        completed.append(str(p))
    if len(completed)!=14:raise ValueError('Exactly42 closed cells required')
    for role in ('pool-A','pool-B','pool-C'):
        c=read(partial/'control/stages'/(role+'-public.completed.json'))['value'];f=read(partial/'control/stages'/(role+'-freeze.completed.json'))['value'];fixed.old.verify(c,f)
    if (partial/'control/stages/judge-input-model.completed.json').exists():raise ValueError('Judge already closed')
    stop=read(ROOT/'user-shutdown-request-1795685306006111908.json')
    started=stop['heartbeat_before']['roles'][ORIGINAL]['checked_unix']
    end=read(ROOT/'user-shutdown-result-1795685309550995985.json')['checked_unix']
    debit=math.ceil(end-started)
    if not 0<debit<900:raise ValueError('No remaining time')
    ledger=Path(fixed.LEDGER).read_bytes()
    if hashlib.sha256(ledger).hexdigest()!='f7dcc00c19a09ccd830315a5c04322546d13124c8c4e10521e7c7f05f425dc7f':raise ValueError('Ledger changed')
    (root/'ledger-before.json').write_bytes(ledger)
    pins={str(p):sha(p) for p in (ROOT/'stages').glob('*.completed.json')}
    pins.update({str(p):sha(p) for p in (partial/'control/stages').glob('*.json')})
    pins.update({str(p):sha(p) for p in store.rglob('*') if p.is_file() and not p.is_symlink() and p.name!='auth.json' and not p.name.endswith('-shm')})
    details={'continuation_id':v['continuation_id'],'source_commit':v['source_commit'],'original_payload':v['original_payload'],'session_store':str(store),'session_id':SESSION,'prior_usage':usage,'prior_seconds':debit,'remaining_role_seconds':900-debit,'setup':setup,'retained_pins':pins,'ledger_sha256':hashlib.sha256(ledger).hexdigest()}
    exclusive(root/'continuation.json',details)
    return {'root':str(root),'prior_seconds':debit,'remaining_seconds':900-debit,'retained_cells':42,'status':'PREPARED_ZERO_INFERENCE'}

def resume_spec(d,offline):
    root=BASE/d['continuation_id'];dest=root/(('probe-'+str(time.time_ns())) if offline else 'BIP-black-5/GPT61-Sol/judge-input');dest.mkdir(parents=True,exist_ok=False)
    old=d['setup'];job=dict(old['descriptor']);env=dict(old['env']);env.update(fixed.shared.candidate_env(dest))
    env['PATH']=old['env']['PATH'];env['CODEX_HOME']=str(dest/'resume-sessions/codex')
    keeps=Path(env['CODEX_HOME']);shutil.copytree(d['session_store'],keeps,ignore=shutil.ignore_patterns('auth.json','*-shm','*.lock'))
    relocate(keeps);(keeps/'auth.json').symlink_to('/opt/workbench/state/codex/auth.json')
    scope=ORIGINAL.replace('refresh-20261126T060538Z',d['continuation_id'])
    job.update(root=str(dest),scope=scope,role_seconds=d['remaining_role_seconds'],offline_control=offline,parent_namespace=os.readlink('/proc/self/ns/pid'),refresh_judge_resume={k:d[k] for k in ('session_id','prior_usage','prior_seconds')})
    job['refresh_judge_resume'].update(original_scope=ORIGINAL,keeps=str(keeps.parent))
    from p6_io_accounting import group_path
    job['authority_write_denied_paths']=[str(group_path('refresh-20261126T060538Z')/'cgroup.procs')]
    return {'descriptor':job,'env':env}

def execute_resume(spec):
    # Preserve the original runtime launch/fence and substitute only the new
    # worker implementing official thread attachment. Never alter old files.
    old=fixed.shared.namespace_command
    def command(argv):return old([str(NEW+'/p6_worker_linux.py') if a==OLD+'/p6_worker_linux.py' else a for a in argv])
    fixed.shared.namespace_command=command
    try:return fixed.execute(spec)
    finally:fixed.shared.namespace_command=old

def controls(d):
    before=sha(fixed.LEDGER);p=d['original_payload'];tp,task,tester=fixed.old.make_task(p,'BIP-black-5')
    with task['fixture_context'] as url:
        fixed.old.activate(ROOT/'BIP-black-5/GPT61-Sol',p,tp,task,tester,url,offline=True)
        w=execute_resume(resume_spec(d,True))
    if w['status']!='COMPLETED' or w.get('session_resume_probe',{}).get('status')!='PASS_OFFICIAL_THREAD_RESUME_ZERO_INFERENCE':raise ValueError('Read-only official resume probe failed')
    if sha(fixed.LEDGER)!=before:raise ValueError('Probe spent real budget')
    value={'status':'PASS_OFFICIAL_RESUME_ZERO_INFERENCE','worker':w,'ledger_sha256':before,'new_models':0,'source_files_sha256':{n:sha(Path(NEW)/n)for n in ('p6_refresh_continue_linux.py','p6_refresh_continue_root.py','p6_refresh_session_resume.py','p6_worker_linux.py')}}
    exclusive(BASE/d['continuation_id']/'controls.json',value);return {'status':value['status'],'ledger_unchanged':True}

def continue_run(d,key):
    from p6_refresh_observer import Observer
    from p6_io_accounting import require_group
    from p6_main_budget import MainLedger
    root=BASE/d['continuation_id'];p=d['original_payload'];p['key']=key
    control=read(root/'controls.json')
    if control['status']!='PASS_OFFICIAL_RESUME_ZERO_INFERENCE':raise ValueError('Actual resume controls missing')
    if any(sha(Path(NEW)/n)!=h for n,h in control['source_files_sha256'].items()):raise ValueError('Resume source differs from actual controls')
    if sha(fixed.LEDGER)!=d['ledger_sha256']:raise ValueError('Ledger changed before resume')
    for path,value in d['retained_pins'].items():
        if sha(path)!=value:raise ValueError('Retained stage changed')
    fixed.verify_plan(p)
    require_group(p['run_id'])
    class ContinuationObserver(Observer):
        @property
        def closed(self):return self._closed
        @closed.setter
        def closed(self,v):self._closed=max(42,v)
    observer=ContinuationObserver(root,{**p['plan'],'plan_sha256':digest(d)},fixed.LEDGER)
    fixed.OBSERVER=observer;observer.start()
    try:
        tp,task,tester=fixed.old.make_task(p,'BIP-black-5')
        with task['fixture_context'] as url:
            fixed.old.activate(ROOT/'BIP-black-5/GPT61-Sol',p,tp,task,tester,url)
            spec=Journal(root/'resume-stages').run('judge-setup',lambda:resume_spec(d,False))
            w=Journal(root/'resume-stages').run('judge-model',lambda:execute_resume(spec))
        if w['status']!='COMPLETED' or w.get('session_id')!=SESSION:raise ValueError('Original judge did not complete; preserve partial state')
        original_scope=w['scope'];w=dict(w,scope=ORIGINAL,additional_accounting_scopes=[original_scope],shutdown_continuation=d['continuation_id'])
        # No old completion is overwritten. Only the interrupted role closes now.
        target=ROOT/'BIP-black-5/GPT61-Sol/control/stages/judge-input-model.completed.json'
        if target.exists():raise ValueError('Original judge already closed')
        fixed.complete_group(target,'judge-input-model',w)
        import p6_refresh_accounting as accounting
        original_summary=accounting.summarize
        def summary(ledger,workers,prefix):
            extra={s for v in workers.values() if v['scope'].startswith(prefix+'/') for s in v.get('additional_accounting_scopes',[])}
            if not extra:return original_summary(ledger,workers,prefix)
            copied=dict(ledger)
            copied['codex_turns']=[dict(v,experiment=prefix+'/linked-resume') if v['experiment']in extra and not v['experiment'].startswith(prefix+'/') else v for v in ledger['codex_turns']]
            return original_summary(copied,workers,prefix)
        accounting.summarize=summary
        original_task=fixed.run_model_task
        def task_run(*a,**kw):
            result=original_task(*a,**kw)
            if result['task_id']=='BIP-black-5' and result['model']=='GPT61-Sol':
                for row in result['rows']:
                    if row['method']=='Enhanced':
                        row['method_timing'].update(elapsed_seconds='unavailable_user_shutdown_split_method',recovery_window_only=True)
                        row['shutdown_continuation']=d['continuation_id']
            return result
        fixed.run_model_task=task_run
        exclusive(ROOT/('shutdown-continuation-'+d['continuation_id']+'.json'),{'continuation_id':d['continuation_id'],'source_commit':d['source_commit'],'original_thread':SESSION,'prior_seconds':d['prior_seconds']})
        result=fixed.compare(p);observer.close(result['status']);return result
    except BaseException as error:
        exclusive(root/('stopped-'+str(time.time_ns())+'.json'),{'status':'STOPPED_PRESERVED','reason':str(error)[:1000],'traceback':traceback.format_exc()[-4000:]})
        observer.close('STOPPED_PRESERVED');raise

def entry(v):
    d=read(BASE/v['continuation_id']/'continuation.json')
    with Path('/opt/workbench/pi-comparison/full-main-owner.lock').open('a')as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return continue_run(d,v['key'])

if __name__=='__main__':
    from p1_broker import protect_memory
    protect_memory()
    v=json.load(sys.stdin)
    if v['action']=='prepare':result=prepare(v)
    elif v['action']=='controls':result=controls(read(BASE/v['continuation_id']/'continuation.json'))
    else:result=entry(v)
    print(json.dumps(result))
