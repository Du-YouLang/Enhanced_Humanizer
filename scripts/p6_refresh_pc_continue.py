"""Append-only PC acceptance recovery, then original unpaid refresh suffix."""
import json,hashlib,time,math,sys,os,fcntl,traceback
from pathlib import Path
from unittest.mock import patch
OLD='/opt/workbench/guidance/executor-fbf96ba9cf225ed7f235'
sys.path[:0]=[OLD,OLD+'/src']
import p6_refresh_linux as fixed
from pi_full_protocol import exclusive,Journal,digest
ROOT=Path('/opt/workbench/benchmark/private/model-refresh/refresh-20261126T060538Z')
CELL=ROOT/'SCI-PC-ALM/GPT62-Sol'
CACHE=Path('/opt/workbench/benchmark/science/private/evaluations/16474c8164bb4aa9994102ec7a942db5')
NEW=Path(__file__).parent

def read(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def files(root):return {str(p.relative_to(root)):sha(p) for p in Path(root).rglob('*') if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts and not p.name.endswith('.pyc')}
def value(name):
 d=read(CELL/'control/stages'/(name+'.completed.json'))
 if digest(d['value'])!=d['value_sha256']:raise ValueError('Stage hash mismatch')
 return d['value']

def prepare(v):
 from p6_pc_validation import run_artifacts
 root=ROOT.parent/v['continuation_id'];root.mkdir(exist_ok=False)
 rows=list((ROOT/'stages').glob('*.completed.json'))
 if len(rows)!=37:raise ValueError('Expected111 closed cells')
 pins={str(p):sha(p) for p in rows}
 for p in rows:
  d=read(p)
  if digest(d['value'])!=d['value_sha256']:raise ValueError('Group hash mismatch')
  for row in d['value']['rows']:
   if row.get('candidate'):fixed.old.verify(row['candidate'],row['frozen'])
 for p in ROOT.glob('*/*/control/stages/*-model.started.json'):
  if not p.with_name(p.name.replace('.started.json','.completed.json')).exists():raise ValueError('Unreconciled model start')
 barrier=value('three-methods-frozen');candidates=[value(n+'-public') for n in ('pool-A','pool-B','pool-C','reviewer')]
 matches=[c for c in candidates if c.get('verdict')=='PASS' and fixed.old.freeze(c)['program_sha256']==barrier['Enhanced']['program_sha256']]
 if not matches:raise ValueError('Frozen selected program absent')
 candidate=matches[0];source=Path(candidate['root'])/'code';fixed.old.verify(candidate,fixed.old.freeze(candidate))
 if files(source)!=files(CACHE/'code'):raise ValueError('Cache source differs')
 if (CELL/'control/stages/Enhanced-acceptance.completed.json').exists():raise ValueError('Acceptance already closed')
 start=(CELL/'control/stages/Enhanced-acceptance.started.json').stat().st_mtime
 debit=math.ceil(v['shutdown_unix']-start)
 from pi_checkpoint_policy import remaining_acceptance_seconds
 remaining=remaining_acceptance_seconds(debit)
 import csv
 with (source/'configs/eta_best_by_cell.csv').open()as f:eta={(int(r['N']),int(r['L'])):float(r['eta_best_1_over_lambda_median']) for r in csv.DictReader(f)if r['dataset']=='fashion_mnist'and r['activation']=='relu'}
 cache={};grid=0
 for folder in sorted((CACHE/'output/result').rglob('*')):
  if not folder.is_dir() or not all((folder/n).is_file() for n in ('summary.json','config.json','metrics.csv')):continue
  rel=str(folder.relative_to(CACHE/'output/result'));s=read(folder/'summary.json')
  overrides={}
  if rel!='smoke':
   run_artifacts(folder,s,eta)
   overrides={k:str(s[k])for k in ('width','depth','method','budget','state_lr','activation','seed')}
  else:
   import csv
   with (folder/'metrics.csv').open()as f:metrics=list(csv.DictReader(f))
   if len(metrics)!=1 or int(metrics[0]['step'])!=s['steps']:raise ValueError('Incomplete smoke')
  data={n:(folder/n).read_text() for n in ('summary.json','config.json','metrics.csv')}
  cache[rel]={'config_name':'smoke.yaml'if rel=='smoke'else'headline_fashion.yaml','overrides':overrides,'files':data}
  pins.update({str(folder/n):sha(folder/n)for n in data});grid+=rel.startswith('grid/')
 if grid!=74 or len(cache)!=78:raise ValueError('Expected74grid+3anchor+smoke')
 for p in (CELL/'control/stages').glob('*.json'):pins[str(p)]=sha(p)
 inputs=files(CACHE/'inputs');raw=Path(fixed.LEDGER).read_bytes()
 if hashlib.sha256(raw).hexdigest()!=v['ledger_sha256']:raise ValueError('Ledger changed')
 (root/'ledger-before.json').write_bytes(raw);exclusive(root/'cache.json',cache)
 d={'continuation_id':v['continuation_id'],'source_commit':v['source_commit'],'original_payload':v['original_payload'],'pins':pins,'candidate':candidate,'frozen':fixed.old.freeze(candidate),'cache_sha256':sha(root/'cache.json'),'cache_inputs':inputs,'prior_debit_seconds':debit,'remaining_seconds':remaining,'prior_closed_cells':111,'shutdown_unix':v['shutdown_unix'],'new_source_sha256':{n:sha(NEW/n)for n in ('p6_refresh_pc_continue.py','p6_refresh_pc_root.py','pi_checkpoint_policy.py')}}
 exclusive(root/'continuation.json',d)
 return {'status':'PREPARED_ZERO_MODEL','root':str(root),'reused_training_records':len(cache),'missing_grid_trainings':1,'prior_debit_seconds':debit,'remaining_seconds':remaining}

def worker():
 return """import json,runpy,subprocess,sys,time
from pathlib import Path
source,inputs,output=map(Path,sys.argv[1:4]);tick=time.perf_counter()
sys.path.insert(0,str(inputs));from pi_checkpoint_policy import cached_training_runner
cache=json.loads((inputs/'recovery-cache.json').read_text());events=[]
subprocess.run=cached_training_runner(subprocess.run,cache,output/'result',events)
sys.path.insert(0,str(source));sys.argv=[str(source/'run_benchmark.py'),'--data-dir',str(inputs),'--output-dir',str(output/'result')]
try:runpy.run_path(str(source/'run_benchmark.py'),run_name='__main__')
except SystemExit as e:
 if e.code not in (0,None):raise
(output/'controller.json').write_text(json.dumps({'wall_seconds':time.perf_counter()-tick,'reused_completed_trainings':events,'recovery':'UNCHANGED_PROGRAM_EXACT_CACHED_TRAININGS'}))
"""

def bind(d):
 root=ROOT.parent/d['continuation_id']
 if any(sha(p)!=h for p,h in d['pins'].items()):raise ValueError('Retained pins changed')
 if sha(root/'cache.json')!=d['cache_sha256']:raise ValueError('Cache changed')
 if any(sha(NEW/n)!=h for n,h in d['new_source_sha256'].items()):raise ValueError('Recovery source changed')
 before=read(root/'ledger-before.json');now=read(fixed.LEDGER)
 if any(now[k][:len(before[k])]!=before[k]for k in ('requests','codex_turns')):raise ValueError('Ledger prefix changed')
 return root

def controls(d):
 root=bind(d)
 from pi_checkpoint_policy import cached_training_runner
 import tempfile,subprocess
 cache=read(root/'cache.json')
 with tempfile.TemporaryDirectory(dir='/opt/workbench/tmp')as tmp:
  folder=Path(tmp);events=[]
  for rel,entry in cache.items():
   argv=['python','train.py','--config',entry['config_name'],'--output-dir',str(folder/rel)]
   for k,val in entry['overrides'].items():argv+=['--'+k.replace('_','-'),val]
   cached_training_runner(lambda *a,**k:(_ for _ in ()).throw(ValueError('Unexpected training')),cache,folder,events)(argv)
  if len(events)!=78:raise ValueError('Cache control incomplete')
  bad=['python','train.py','--config','bad.yaml','--output-dir',str(folder/'smoke')]
  try:cached_training_runner(lambda *a,**k:None,cache,folder,[])(bad)
  except ValueError:pass
  else:raise ValueError('Mismatch accepted')
 exclusive(root/'controls.json',{'status':'PASS78_CACHE_CONTROLS','model_calls':0,'training_calls':0,'ledger_sha256':sha(fixed.LEDGER)})
 return {'status':'PASS78_CACHE_CONTROLS','model_calls':0,'training_calls':0}

def entry(v):
 root=ROOT.parent/v['continuation_id'];d=read(root/'continuation.json')
 if v['action']=='controls':return controls(d)
 from p6_refresh_observer import Observer
 from p6_io_accounting import require_group
 with Path('/opt/workbench/pi-comparison/full-main-owner.lock').open('a')as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);bind(d)
  if read(root/'controls.json')['status']!='PASS78_CACHE_CONTROLS':raise ValueError('Controls required')
  require_group('refresh-20261126T060538Z')
  class Watch(Observer):
   @property
   def closed(self):return self._closed
   @closed.setter
   def closed(self,x):self._closed=max(111,x)
  observer=Watch(root,{**d['original_payload']['plan'],'plan_sha256':digest(d)},fixed.LEDGER);observer.start();fixed.OBSERVER=observer
  try:
   import p6_pc_grader as grader
   real=grader.execute;counter=[0]
   def recover_execute(source,prefix,program,**kwargs):
    counter[0]+=1
    if counter[0]!=1:return real(source,prefix,program,**kwargs)
    inputs=dict(kwargs.get('inputs',{}))
    for name in d['cache_inputs']:
     if inputs.get(name)!=(CACHE/'inputs'/name).read_bytes():raise ValueError('Cache data/provenance mismatch')
    inputs.update({'recovery-cache.json':(root/'cache.json').read_bytes(),'pi_checkpoint_policy.py':(NEW/'pi_checkpoint_policy.py').read_bytes()})
    kwargs['inputs']=inputs
    return real(source,prefix,worker(),**kwargs)
   before=sha(fixed.LEDGER)
   def acceptance():
    tp,task,tester=fixed.old.make_task(d['original_payload'],'SCI-PC-ALM')
    with task['fixture_context']as url:
     fixed.old.activate(CELL,d['original_payload'],tp,task,tester,url)
     with patch.object(grader,'execute',side_effect=recover_execute):
      original=grader.grade
      def grade(*a,**kw):kw['timeout']=d['remaining_seconds'];return original(*a,**kw)
      with patch.object(grader,'grade',side_effect=grade):
       return fixed.measured_test(tester,Path(d['candidate']['root'])/'code',True)
   accepted=Journal(root/'recovery-stages').run('Enhanced-acceptance',acceptance)
   if sha(fixed.LEDGER)!=before:raise ValueError('Acceptance changed model ledger')
   accepted.update(shutdown_recovery=d['continuation_id'],original_full_acceptance_elapsed='unavailable_shutdown_split')
   accepted['trusted_measurement']['monotonic_seconds']='unavailable_shutdown_split'
   fixed.complete_group(CELL/'control/stages/Enhanced-acceptance.completed.json','Enhanced-acceptance',accepted)
   fixed.complete_group(CELL/'control/stages/Enhanced-acceptance-io.completed.json','Enhanced-acceptance-io',{'raw_elapsed_seconds':'unavailable_shutdown_split','reason':'Only remaining acceptance was measured','recovery_receipt':str(root)})
   exclusive(root/'acceptance-receipt.json',{'status':'ORIGINAL_ACCEPTANCE_RECOVERED','verdict':accepted['verdict'],'model_calls':0,'ledger_unchanged':True,'prior_debit_seconds':d['prior_debit_seconds']})
   payload=dict(d['original_payload'],key=v['key']);result=fixed.compare(payload);observer.close(result['status']);return result
  except BaseException as e:
   exclusive(root/('stopped-'+str(time.time_ns())+'.json'),{'status':'STOPPED_PRESERVED','reason':str(e),'traceback':traceback.format_exc()[-5000:]});observer.close('STOPPED_PRESERVED');raise

if __name__=='__main__':
 from p1_broker import protect_memory
 protect_memory();v=json.load(sys.stdin)
 print(json.dumps(prepare(v)if v['action']=='prepare'else entry(v)))
