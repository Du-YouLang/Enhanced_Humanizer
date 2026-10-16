"""Retain nine tasks, finish one role, repair acceptance, run six new tasks."""
import fcntl,json,os,subprocess,sys,time,traceback
from pathlib import Path

sys.path[:0]=[str(Path(__file__).parent),str(Path(__file__).parent/'src')]
import p6_guidance_linux as fixed
from p6_guidance_protocol import TASKS,digest
from p6_guidance_continuation import ORIGINAL_RUN,PARTIAL_TASK,RETAINED_TASKS,NEW_TASKS,AFFECTED_TASKS,permit_launch
from pi_full_protocol import Journal,exclusive


def read(p):return json.loads(Path(p).read_bytes())


def validate(payload):
    fixed.bind(payload)
    recovery=payload['plan']['recovery']
    if (recovery['original_run']!=ORIGINAL_RUN or recovery['retained_tasks']!=list(RETAINED_TASKS)
        or recovery['new_tasks']!=list(NEW_TASKS) or recovery['partial_task']!=PARTIAL_TASK):
        raise ValueError('Exact retained prefix, partial task and six-task suffix required')
    for path,expected in recovery['checkpoint_sha256'].items():
        if fixed.sha(path)!=expected:raise ValueError('Retained checkpoint changed: '+path)
    for row in recovery['model_programs']:
        patch,source=fixed.shared.program_evidence(row['work'],row['base_commit'])
        if digest({'patch':patch,'source':source})!=row['program_sha256']:
            raise ValueError('A completed model program changed')
    control=read(payload['plan']['controls_receipt'])
    if control['status']!='PASS_GUIDANCE_ZERO_MODEL_CONTROLS' or len(control.get('public_helper_controls',[]))!=12:
        raise ValueError('Actual twelve public-helper positive/negative controls required')
    if control['source_sha256']!=payload['plan']['source_sha256']:raise ValueError('Control source differs')


def supplement(root,payload,task_result):
    tid=task_result['task_id'];tp,task,tester=fixed.make_task(payload,tid);rows=[]
    dest=root/'acceptance-supplements'/tid;dest.mkdir(parents=True,exist_ok=True)
    (dest/'control').mkdir(exist_ok=True)
    canary=dest/'control/canary'
    if not canary.exists():canary.write_text('private acceptance supplement')
    journal=Journal(dest/'control/stages')
    with task['fixture_context'] as url:
        fixed.activate(dest,payload,tp,task,tester,url)
        for oldrow in task_result['rows']:
            c=oldrow['candidate'];f=oldrow['frozen'];work=Path(c['root'])/'code'
            fixed.verify(c,f)
            method=oldrow['method']
            public=journal.run(method+'-public',lambda:tester(work,False))
            valid=(oldrow['worker']['status']=='COMPLETED' and not c.get('working_tree')
                and not c.get('protected_paths_modified') and c.get('head_commit')!=c.get('base_commit') and bool(c.get('patch')))
            private=journal.run(method+'-hidden',lambda:tester(work,True) if valid and public['verdict']=='PASS' else
                {'verdict':'NOT_RUN','reason':'Public or original file-policy gate failed','elapsed_seconds':0})
            fixed.verify(c,f)
            rows.append({'task_id':tid,'method':method,'raw_original_outcome':oldrow['outcome'],
                'supplemental_quality_outcome':private['verdict'] if valid and public['verdict']=='PASS' else public['verdict'] if public['verdict']!='PASS' else 'FAIL',
                'public':public,'acceptance':private,'frozen_program':f,'candidate_changes':0,'model_replays':0,
                'process_comparison_status':'INFRASTRUCTURE_AFFECTED_NOT_EQUIVALENT_GUIDANCE_CONDITIONS',
                'helper_binding':task['helper_binding']})
    return rows


def run(payload):
    from p1_broker import protect_memory
    protect_memory();validate(payload)
    root=fixed.BASE/payload['run_id'];root.mkdir(parents=True,exist_ok=True)
    if not (root/'plan.json').exists():exclusive(root/'plan.json',payload['plan'])
    journal=Journal(root/'control/stages');oldpayload=payload['plan']['recovery']['original_payload']
    oldroot=fixed.BASE/ORIGINAL_RUN
    results=[read(oldroot/'stages'/(tid+'.completed.json'))['value'] for tid in RETAINED_TASKS]
    supplements=[];status='GUIDANCE_RECOVERED_EXECUTION_COMPLETED'
    def partial():
        dest=root/'partial-original-result.json'
        command=[sys.executable,'-B',str(Path(__file__).with_name('p6_guidance_partial_linux.py'))]
        with (root/'partial-original.private.log').open('xb') as log:
            p=subprocess.run(command,input=json.dumps({'original_payload':oldpayload,'key':payload['key'],'result_path':str(dest)}).encode(),
                stdout=log,stderr=subprocess.STDOUT,timeout=1800)
        if p.returncode:raise RuntimeError('Original partial task preserved; inspect its private log before any retry')
        return read(dest)
    try:
        partial_result=journal.run('original-partial-task',partial);results.append(partial_result)
        for tid in AFFECTED_TASKS:
            original=next(t for t in results if t['task_id']==tid)
            supplements.extend(journal.run(tid+'-supplement',lambda:supplement(root,payload,original)))
        saved=fixed.shared.launch
        def guarded(job,env):
            if not permit_launch(job['scope'],payload['run_id'],'new-suffix'):raise ValueError('Retained/completed task model replay denied')
            return saved(job,env)
        fixed.shared.launch=guarded
        for tid in NEW_TASKS:
            final=root/'control/stages'/(tid+'-task.completed.json')
            if final.exists():value=journal.run(tid+'-task',lambda:None)
            else:
                value=fixed.task_run(root,payload,tid)
                exclusive(final,{'stage':tid+'-task','value':value,'value_sha256':digest(value)})
            results.append(value)
            (root/'progress.json').write_text(json.dumps({'status':'RUNNING','completed_tasks':len(results),
                'total_tasks':16,'new_suffix_completed':len(results)-10,'last_task':tid,'checked_unix':time.time()}))
    except BaseException as error:
        status='STOPPED_PRESERVED'
        exclusive(root/('error-'+str(time.time_ns())+'.json'),{'error_type':type(error).__name__,'reason':str(error)[:1500],
            'traceback':traceback.format_exc()[-6000:]})
    receipt={'status':status,'results':results,'supplements':supplements,'completed_tasks':len(results),'total_tasks':16,
        'original_run':ORIGINAL_RUN,'plan_sha256':payload['plan']['plan_sha256'],'ledger_sha256':fixed.sha(fixed.LEDGER),
        'all_original_results_retained':True,'scientific_review':'PENDING_SOL_SOURCE_REPORT_FIGURE',
        'infrastructure_affected_tasks':list(AFFECTED_TASKS),'finished_unix':time.time()}
    exclusive(root/('receipt-'+str(time.time_ns())+'.json'),receipt)
    (root/'progress.json').write_text(json.dumps({k:v for k,v in receipt.items() if k not in ('results','supplements')}))
    return {'status':status,'completed_tasks':len(results),'root':str(root)}


def entry(payload):
    with Path('/opt/workbench/pi-comparison/full-main-owner.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return run(payload)


if __name__=='__main__':print(json.dumps(entry(json.load(sys.stdin))))
