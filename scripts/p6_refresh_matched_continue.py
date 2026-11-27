"""Same-thread recovery of one matched slot, then original unpaid suffix."""
import sys,json,hashlib,shutil,time,math,fcntl,traceback,os
from pathlib import Path
OLD='/opt/workbench/guidance/executor-fbf96ba9cf225ed7f235'
sys.path[:0]=[OLD,OLD+'/src'];sys.path.append(str(Path(__file__).parent))
import p6_refresh_linux as fixed
from pi_full_protocol import Journal,exclusive,digest
from p6_refresh_matched_resume import SESSION,ORIGINAL,relocate
BASE=Path('/opt/workbench/benchmark/private/model-refresh');ROOT=BASE/'refresh-20261126T060538Z';CELL=ROOT/'SCI-GRANGER-GPU/GPT61-Sol';NEW=Path(__file__).parent
NAMES=('p6_refresh_matched_continue.py','p6_refresh_matched_root.py','p6_refresh_matched_resume.py','p6_worker_linux.py')
def read(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def inventory(root):return {str(p):sha(p)for p in Path(root).rglob('*')if p.is_file()and not p.is_symlink()and p.name!='auth.json'and not p.name.endswith('-shm')}
def stage(name):
 d=read(CELL/'control/stages'/(name+'.completed.json'))
 if d['value_sha256']!=digest(d['value']):raise ValueError('Stage changed')
 return d['value']

def prepare(v):
 root=BASE/v['continuation_id'];root.mkdir(exist_ok=False)
 if len(list((ROOT/'stages').glob('*.completed.json')))!=45:raise ValueError('Exactly135 retained cells required')
 pins=dict(v['retained_group_hashes'])
 if len(pins)!=45 or any(sha(p)!=h for p,h in pins.items()):raise ValueError('Retained135 differ from shutdown export')
 for p in pins:
  d=read(p)
  if d['value_sha256']!=digest(d['value']):raise ValueError('Group digest changed')
 setup=stage('matched-setup');oldroot=Path(setup['descriptor']['root']);store=oldroot/'home/.codex';traces=list(store.glob('sessions/*/*/*/rollout-*.jsonl'))
 if len(traces)!=1 or SESSION not in traces[0].name:raise ValueError('Original matched session missing')
 usage=None;events=[]
 for line in traces[0].read_text().splitlines():
  row=json.loads(line);data=row.get('payload')or{}
  if data.get('type')=='token_count'and data.get('info'):usage=data['info']['total_token_usage']
  if data.get('type')in('task_started','task_complete'):events.append({'at':row['timestamp'],'type':data['type']})
 if [e['type']for e in events]!=['task_started','task_complete','task_started']:raise ValueError('One complete and one partial turn required')
 slot=read(oldroot/'controller-slot.json')
 if slot['index']!=2 or slot['scope']!=ORIGINAL.rsplit('/',1)[0]+'/matched-2':raise ValueError('Original slot boundary differs')
 shutdown=read(BASE/'refresh-20261127T013935Z/user-deadline-request.json');debit=math.ceil(shutdown['at_unix']-(oldroot/'controller-slot.json').stat().st_mtime)
 if debit!=15:raise ValueError('Expected original15-second debit')
 if not(oldroot/'code/.git').is_dir()or(oldroot/'code/.git').is_symlink()or(oldroot/'code/.git/commondir').exists():raise ValueError('Independent original repository required')
 if (CELL/'control/stages/matched-model.completed.json').exists():raise ValueError('Already completed role')
 for p in ROOT.glob('*/*/control/stages/*-model.started.json'):
  if p!=CELL/'control/stages/matched-model.started.json'and not p.with_name(p.name.replace('.started.json','.completed.json')).exists():raise ValueError('Another unresolved model start')
 pins.update({str(p):sha(p)for p in(CELL/'control/stages').glob('*.json')});pins.update(inventory(store));pins.update(inventory(oldroot/'code'));pins[str(oldroot/'input.json')]=sha(oldroot/'input.json');pins[str(oldroot/'controller-slot.json')]=sha(oldroot/'controller-slot.json')
 ledger=Path(fixed.LEDGER).read_bytes()
 if hashlib.sha256(ledger).hexdigest()!=v['ledger_sha256']:raise ValueError('Ledger differs from shutdown')
 (root/'ledger-before.json').write_bytes(ledger);(root/'authority-canary').write_text('withheld trusted authority')
 from datetime import datetime
 completed_event=(datetime.fromisoformat(events[1]['at'].replace('Z','+00:00'))-datetime.fromisoformat(events[0]['at'].replace('Z','+00:00'))).total_seconds()
 d={'continuation_id':v['continuation_id'],'source_commit':v['source_commit'],'original_payload':read(BASE/'refresh-20261127T013935Z/continuation.json')['original_payload'],'setup':setup,'session_store':str(store),'prior_usage':usage,'prior_seconds':debit,'completed_event_seconds':completed_event,'pins':pins,'source_sha256':{n:sha(NEW/n)for n in NAMES},'ledger_sha256':hashlib.sha256(ledger).hexdigest()}
 exclusive(root/'continuation.json',d);return {'status':'PREPARED_ZERO_INFERENCE','retained_cells':135,'completed_slots':1,'resume_slot':2,'remaining_slot_seconds':1200-debit,'never_started_slots':[3,4,5,6],'plan_sha256':digest(d)}

def bind(d):
 if any(sha(p)!=h for p,h in d['pins'].items()):raise ValueError('Retained evidence changed')
 if any(sha(NEW/n)!=h for n,h in d['source_sha256'].items()):raise ValueError('Resume source changed')
 before=read(BASE/d['continuation_id']/'ledger-before.json');now=read(fixed.LEDGER)
 if any(now[k][:len(before[k])]!=before[k]for k in ('requests','codex_turns')):raise ValueError('Ledger prefix changed')
 fixed.verify_plan(d['original_payload'])

def spec(d,offline):
 root=BASE/d['continuation_id'];dest=root/(('probe-'+str(time.time_ns()))if offline else 'SCI-GRANGER-GPU/GPT61-Sol/matched');dest.mkdir(parents=True,exist_ok=False)
 old=d['setup'];job=dict(old['descriptor']);env=dict(old['env']);env.update(fixed.shared.candidate_env(dest));env['PATH']=old['env']['PATH']
 shutil.copytree(Path(job['work']),dest/'code',symlinks=True);(dest/'input.json').write_bytes(Path(job['input_file']).read_bytes())
 keeps=dest/'resume-sessions/codex';shutil.copytree(d['session_store'],keeps,ignore=shutil.ignore_patterns('auth.json','*-shm','*.lock','thread-writer-locks'));relocate(keeps);(keeps/'auth.json').symlink_to('/opt/workbench/state/codex/auth.json');env['CODEX_HOME']=str(keeps)
 from p6_refresh_protocol import handoff_prompt
 prompt=handoff_prompt(dest/'input.json',(dest/'input.json').read_bytes(),job['prompt'])
 job.update(root=str(dest),work=str(dest/'code'),input_file=str(dest/'input.json'),prompt=prompt,scope=ORIGINAL.replace('refresh-20261126T060538Z',d['continuation_id']),role_seconds=6000-d['prior_seconds'],offline_control=offline,parent_namespace=os.readlink('/proc/self/ns/pid'),refresh_slot_file=str(dest/'controller-slot.json'))
 job['refresh_matched_resume']={'session_id':SESSION,'original_scope':ORIGINAL,'keeps':str(keeps.parent),'completed_slots':1,'resume_slot':2,'prior_seconds':d['prior_seconds'],'prior_usage':d['prior_usage'],'completed_event_seconds':d['completed_event_seconds']}
 job['denied_paths']=[*job['denied_paths'],str(root/'authority-canary')]
 from p6_io_accounting import group_path
 job['authority_write_denied_paths']=[str(group_path('refresh-20261126T060538Z')/'cgroup.procs')]
 return {'descriptor':job,'env':env}

def execute(specification):
 old=fixed.shared.namespace_command
 fixed.shared.namespace_command=lambda argv:old([str(NEW/'p6_worker_linux.py')if a==OLD+'/p6_worker_linux.py'else a for a in argv])
 try:return fixed.execute(specification)
 finally:fixed.shared.namespace_command=old

def controls(d):
 bind(d);before=sha(fixed.LEDGER);tp,task,tester=fixed.old.make_task(d['original_payload'],'SCI-GRANGER-GPU')
 with task['fixture_context']as url:
  fixed.old.activate(CELL,d['original_payload'],tp,task,tester,url,offline=True)
  w=execute(spec(d,True))
 if w['status']!='COMPLETED'or w.get('session_resume_probe',{}).get('status')!='PASS_MATCHED_ORIGINAL_THREAD_ZERO_INFERENCE':raise ValueError('Actual official thread/fence controls failed')
 if sha(fixed.LEDGER)!=before:raise ValueError('Controls spent model budget')
 result={'status':'PASS_MATCHED_THREAD_AND_FENCE_ZERO_INFERENCE','worker':w,'ledger_unchanged':True,'source_sha256':d['source_sha256']};exclusive(BASE/d['continuation_id']/'controls.json',result);return {k:v for k,v in result.items()if k!='worker'}

def entry(v):
 root=BASE/v['continuation_id'];d=read(root/'continuation.json')
 if v['action']=='controls':return controls(d)
 from p6_refresh_observer import Observer
 from p6_io_accounting import require_group
 with Path('/opt/workbench/pi-comparison/full-main-owner.lock').open('a')as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);bind(d)
  if read(root/'controls.json')['status']!='PASS_MATCHED_THREAD_AND_FENCE_ZERO_INFERENCE':raise ValueError('Actual controls required')
  require_group('refresh-20261126T060538Z')
  class Watch(Observer):
   @property
   def closed(self):return self._closed
   @closed.setter
   def closed(self,x):self._closed=max(135,x)
  observer=Watch(root,{**d['original_payload']['plan'],'plan_sha256':digest(d)},fixed.LEDGER);observer.start();fixed.OBSERVER=observer
  try:
   tp,task,tester=fixed.old.make_task(d['original_payload'],'SCI-GRANGER-GPU')
   with task['fixture_context']as url:
    fixed.old.activate(CELL,d['original_payload'],tp,task,tester,url)
    s=Journal(root/'resume-stages').run('matched-setup',lambda:spec(d,False))
    w=Journal(root/'resume-stages').run('matched-model',lambda:execute(s))
   if w['status']!='COMPLETED'or w.get('session_id')!=SESSION or len(w.get('matched_slot_receipts',[]))!=6:raise ValueError('Original matched role did not complete')
   extra=ORIGINAL.replace('refresh-20261126T060538Z',d['continuation_id']).rsplit('/',1)[0]+'/matched-2'
   completed=dict(w,scope=ORIGINAL,additional_accounting_scopes=[extra],shutdown_continuation=d['continuation_id'])
   target=CELL/'control/stages/matched-model.completed.json'
   if target.exists():raise ValueError('Original role already closed')
   fixed.complete_group(target,'matched-model',completed)
   import p6_refresh_accounting as accounting
   real_summary=accounting.summarize
   def summary(ledger,workers,prefix):
    scopes={s for w in workers.values()if w['scope'].startswith(prefix+'/')for s in w.get('additional_accounting_scopes',[])}
    if not scopes:return real_summary(ledger,workers,prefix)
    copy=dict(ledger);copy['codex_turns']=[dict(row,experiment=prefix+'/linked-resume')if row['experiment']in scopes and not row['experiment'].startswith(prefix+'/')else row for row in ledger['codex_turns']];return real_summary(copy,workers,prefix)
   accounting.summarize=summary
   real_task=fixed.run_model_task
   def run_task(*a,**kw):
    result=real_task(*a,**kw)
    if result['task_id']=='SCI-GRANGER-GPU'and result['model']=='GPT61-Sol':
     for row in result['rows']:
      t=row['method_timing']
      if row['method']=='SingleAgent-MatchedBudget':t['elapsed_seconds']='unavailable_user_shutdown_split_method';row['shutdown_continuation']=d['continuation_id']
      else:t['elapsed_seconds']=stage(row['method']+'-io-observation')['raw_elapsed_seconds']
    return result
   fixed.run_model_task=run_task
   payload=dict(d['original_payload'],key=v['key']);result=fixed.compare(payload);observer.close(result['status']);return result
  except BaseException as e:
   exclusive(root/('stopped-'+str(time.time_ns())+'.json'),{'status':'STOPPED_PRESERVED','reason':str(e),'traceback':traceback.format_exc()[-5000:]});observer.close('STOPPED_PRESERVED');raise

if __name__=='__main__':
 from p1_broker import protect_memory
 protect_memory();v=json.load(sys.stdin);print(json.dumps(prepare(v)if v['action']=='prepare'else entry(v)))
