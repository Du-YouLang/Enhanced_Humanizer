"""Prepare, validate and launch the explicitly authorized PC acceptance recovery."""
import argparse,hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path[:0]=[str(ROOT/'scripts'),str(Path(__file__).parent)]
from wsl_project import run
from pi_full_protocol import digest
from pi_checkpoint_policy import AUTHORIZATION

INTAKE=ROOT/'.local-workbench/pi-comparison/intake'
PLAN=INTAKE/'pc-acceptance-recovery-20261015.private.json'

def native(code,value,timeout=120):
    r=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',code],input_bytes=json.dumps(value).encode(),timeout=timeout)
    if r.returncode:raise RuntimeError(r.stderr.decode(errors='replace')[-2500:])
    return json.loads(r.stdout)


def deploy():
    texts={n:Path(__file__).with_name(n).read_text(encoding='utf8') for n in ('pi_checkpoint_linux.py','pi_checkpoint_policy.py')}
    hashes={n:hashlib.sha256(v.encode()).hexdigest() for n,v in texts.items()}
    folder='/opt/workbench/pi-comparison/checkpoint-'+digest(hashes)[:16]
    native('''import json,sys;from pathlib import Path
d=json.load(sys.stdin);root=Path(d['folder']);root.mkdir(exist_ok=True)
for n,s in d['texts'].items():
 p=root/n
 if p.exists() and p.read_bytes()!=s.encode():raise ValueError('Frozen recovery controller changed')
 if not p.exists():p.write_bytes(s.encode())
print(json.dumps({'status':'DEPLOYED_ZERO_MODEL'}))
''',{'folder':folder,'texts':texts})
    return folder,{folder+'/'+n:h for n,h in hashes.items()}


def prepare(folder,sources):
    previous=json.loads((INTAKE/'full-unstarted-continuation-v4.private.json').read_bytes())
    code='''import csv,hashlib,json,sys,time;from pathlib import Path
d=json.load(sys.stdin);prior=d['prior'];sys.path[:0]=[str(Path(next(iter(prior['original_payload']['source_sha256']))).parent),'/opt/workbench/source',d['folder']]
from pi_full_protocol import digest,exclusive
from pi_checkpoint_policy import checkpoint_cells,retained_value
from p6_pc_validation import run_artifacts
from p6_science_contracts import source_identity
root=Path('/opt/workbench/benchmark/private/pi-comparison/formal-full-compare-20261015T063346Z')
name='SCI-PC-ALM-P0-deepseek';target=root/name;source=target/'code'
cache_root=Path('/opt/workbench/benchmark/science/private/evaluations/5f81bae6b3a7441a8c70902eb3b1cc0d')
if source_identity(source)!=source_identity(cache_root/'code'):raise ValueError('Cached training source differs from frozen candidate')
rows=[];files=[*sorted((root/'control/stages').glob('*.json')),root/'continuation-plan.json',root/'plan.json']
for cell in prior['remaining_cells'][:61]:
 n=cell['task_id']+'-'+cell['profile']+'-'+cell['provider'];rows.append(retained_value(root/'control/stages'/(n+'-cell.completed.json'),n+'-cell'))
 files.extend(root/n/k for k in ('result.json','candidate-private.json','controller-outcome.json','frozen-program.json','events.private.jsonl'))
for k in ('candidate-private.json','controller-outcome.json','frozen-program.json','events.private.jsonl'):files.append(target/k)
todo=checkpoint_cells(prior,rows,prior['remaining_cells'][61])
files.extend(p for p in cache_root.rglob('*') if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts)
with (source/'configs/eta_best_by_cell.csv').open() as f:
 eta={(int(r['N']),int(r['L'])):float(r['eta_best_1_over_lambda_median']) for r in csv.DictReader(f) if r['dataset']=='fashion_mnist' and r['activation']=='relu'}
calibration=json.loads(Path('/opt/workbench/benchmark/science/private/pc-calibration-20261012-v1/status.json').read_bytes())
input_root=cache_root/'inputs'
actual={str(p.relative_to(input_root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in input_root.rglob('*.gz')}
if actual!=calibration['data_fingerprint']:raise ValueError('Cached input data differs')
cache={};skipped=[]
for directory in [cache_root/'output/result/smoke',*sorted((cache_root/'output/result/anchor').glob('*')),*sorted((cache_root/'output/result/grid').glob('*'))]:
 if not directory.is_dir():continue
 names=('config.json','summary.json','metrics.csv')
 if not all((directory/n).is_file() and not (directory/n).is_symlink() for n in names):skipped.append(str(directory));continue
 row=json.loads((directory/'summary.json').read_bytes());relative=directory.relative_to(cache_root/'output/result').as_posix()
 if relative=='smoke':
  import yaml,math
  cfg=json.loads((directory/'config.json').read_bytes());expected=yaml.safe_load((source/'configs/smoke.yaml').read_text())
  expected['output_dir']=str(directory)
  def subset(a,b):
   return all(k in b and (subset(v,b[k]) if isinstance(v,dict) else v==b[k]) for k,v in a.items())
  if not subset(expected,cfg) or not isinstance(row.get('steps'),int) or row['steps']<1 or not math.isfinite(row['final_test_acc']):raise ValueError('Incomplete cached smoke')
  config_name='smoke.yaml';overrides={}
 else:
  run_artifacts(directory,row,eta)
  config_name='headline_fashion.yaml';w,l,m=row['width'],row['depth'],row['method']
  overrides={k:str(v) for k,v in {'dataset':'fashion_mnist','method':m,'width':w,'depth':l,'activation':'relu','seed':0,'state_lr':eta[w,l],'budget':0 if m=='bp' else 2*l}.items()}
 cache[relative]={'config_name':config_name,'overrides':overrides,'files':{n:(directory/n).read_text() for n in names}}
if len(cache)!=48 or len([k for k in cache if k.startswith('grid/')])!=44:raise ValueError('Exact observed48 complete trainings required')
base=Path('/opt/workbench/pi-comparison');cache_file=base/'pc-acceptance-cache-20261015.private.json'
if cache_file.exists() and json.loads(cache_file.read_bytes())!=cache:raise ValueError('Cache immutable')
if not cache_file.exists():exclusive(cache_file,cache)
archive=base/'pc-acceptance-ledger-before-20261015.private.json';ledger=Path('/opt/workbench/state/p6-main-local-20261011/ledger.json')
if not archive.exists():
 with archive.open('xb') as f:f.write(ledger.read_bytes())
files.extend([archive,cache_file]);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan={'authorization':d['authorization'],'root':str(root),'original_wrapper':'/opt/workbench/pi-comparison/continue-unstarted-bed8f772553885ee',
 'continuation_plan':prior,'sources':d['sources'],'recovery_root':str(root/'acceptance-recovery-20261015'),
 'completed_results_sha256':digest(rows),'cell':prior['remaining_cells'][61],'unstarted_cells':todo,
 'cache_file':str(cache_file),'cache_evaluation':str(cache_root),'reused_training_records':len(cache),'partial_trainings_preserved':skipped,
 'prior_acceptance_debit_seconds':1900,'prior_time_evidence':{'acceptance_started_utc':'2026-10-15T09:46:25.633939Z','first_post_interruption_EventLog6005_utc':'2026-10-15T10:17:32.035324Z','policy':'Round1866.402s observed wall-span upward to1900s; includes shutdown downtime, not claimed exact CPU time'},
 'evidence_sha256':{str(p):sha(p) for p in files},'ledger_archive':str(archive),'automatic_model_replay':False,
 'controller':d['folder'],'external_release_authorized':False}
plan['recovery_sha256']=digest(plan);print(json.dumps(plan))
'''
    plan=native(code,{'prior':previous,'folder':folder,'sources':sources,'authorization':AUTHORIZATION},timeout=180)
    if PLAN.exists() and json.loads(PLAN.read_bytes())!=plan:raise ValueError('Recovery plan immutable')
    if not PLAN.exists():
        with PLAN.open('x',encoding='utf8') as f:json.dump(plan,f,indent=2)
    return {'status':'PREPARED_PC_ACCEPTANCE_AND23_UNSTARTED','completed_reused':61,'cached_trainings':48,'new_model_calls':0,'recovery_sha256':plan['recovery_sha256']}


def main():
    global PLAN
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('prepare','controls','execute'));a=p.parse_args()
    folder,sources=deploy()
    PLAN=PLAN.with_name('pc-acceptance-recovery-20261015-'+folder.rsplit('-',1)[1]+'.private.json')
    if a.mode=='prepare':print(json.dumps(prepare(folder,sources)));return
    plan=json.loads(PLAN.read_bytes())
    if plan['sources']!=sources:raise ValueError('Commit and freeze exact recovery source')
    payload={'mode':a.mode,'plan':plan}
    if a.mode=='controls':
        r=run(['/opt/workbench/.venv-linux/bin/python','-B',folder+'/pi_checkpoint_linux.py'],input_bytes=json.dumps(payload).encode(),timeout=180)
        if r.returncode:raise RuntimeError(r.stderr.decode(errors='replace')[-2500:])
        value=json.loads(r.stdout);gate=PLAN.with_name(PLAN.stem+'-controls.private.json')
        if not gate.exists():gate.write_text(json.dumps(value,indent=2))
        print(json.dumps(value));return
    if subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=ROOT).strip():raise ValueError('Commit exact controller before launch')
    gate=json.loads(PLAN.with_name(PLAN.stem+'-controls.private.json').read_bytes())
    if gate['status']!='PASS_CHECKPOINT_RECOVERY_BINDINGS':raise ValueError('Actual recovery controls required')
    import yaml
    payload['key']=yaml.safe_load((Path(os.environ['USERPROFILE'])/'.dsh/.credentials.yaml').read_text())['refs']['DEEPSEEK_API_KEY']
    launcher='''import hashlib,json,sys,subprocess,time;from pathlib import Path
d=json.load(sys.stdin);p=d['payload'];plan=p['plan'];boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
base=Path('/opt/workbench/pi-comparison/formal-launches');run_id=Path(plan['root']).name
for f in base.glob('*.json'):
 r=json.loads(f.read_bytes());proc=Path('/proc')/str(r['pid'])
 if r['boot_id']==boot and (proc/'stat').exists():
  s=(proc/'stat').read_text().rsplit(')',1)[1].split()
  if s[0]!='Z' and s[19]==r['process_start_ticks']:raise ValueError('Existing exact Pi owner active')
name=run_id+'-'+str(time.time_ns());log=base/(name+'.private.log')
with log.open('xb') as out:
 child=subprocess.Popen(['/opt/workbench/.venv-linux/bin/python','-B',d['folder']+'/pi_checkpoint_linux.py'],stdin=subprocess.PIPE,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
 child.stdin.write(json.dumps(p).encode());child.stdin.close()
proc=Path('/proc')/str(child.pid)
value={'run_id':run_id,'pid':child.pid,'boot_id':boot,'process_start_ticks':(proc/'stat').read_text().rsplit(')',1)[1].split()[19],
 'command_sha256':hashlib.sha256((proc/'cmdline').read_bytes()).hexdigest(),'log':str(log),'started_unix':time.time(),
 'recovery_sha256':plan['recovery_sha256'],'automatic_replay':False}
with (base/(name+'.json')).open('x') as f:json.dump(value,f,indent=2)
print(json.dumps(value))
'''
    print(json.dumps(native(launcher,{'folder':folder,'payload':payload})))


if __name__=='__main__':
    original=subprocess.run
    def hidden(*a,**kw):
        if os.name=='nt':kw['creationflags']=subprocess.CREATE_NO_WINDOW
        return original(*a,**kw)
    subprocess.run=hidden;main()
