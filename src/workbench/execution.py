"""Trusted local adapter to native Humanize Flow; it does not implement a Coding Harness."""
import base64
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import sys
import threading
import time

from .memory import ROOT,canonical,local,now,safe_text,sha,uid
from .gitops import git,GitOps

sys.path.insert(0,str(ROOT/'scripts'))
from wsl_project import run as wsl
from p2_contract import validate_contract

DEFAULTS={'n':3,'concurrency':3,'judge':'J3','candidate_seconds':600,'candidate_requests':12,'candidate_cash_usd':.5,
          'api_cash_usd':5,'ds_requests':160,'codex_turns':16,
          'experiment_seconds':1200,'builder_direction':'Review the architecture independently; improve iterator safety and error clarity, with visible tests.',
          'pause_after':''}


def settings(value):
    if not isinstance(value,dict) or set(value)-set(DEFAULTS):raise ValueError('Unknown settings')
    value=DEFAULTS|value
    if type(value['n']) is not int or value['n'] not in (1,3,4,5):raise ValueError('N must be 1,3,4,5')
    for field,maximum in (('concurrency',5),('candidate_seconds',600),('candidate_requests',12),('experiment_seconds',1200)):
        if type(value[field]) is not int or not 1<=value[field]<=maximum:raise ValueError('Invalid '+field)
    if value['judge'] not in ('J0','J1','J3'):raise ValueError('Jev is region-blocked; choose an explicit available judge')
    for field,maximum in (('ds_requests',160),('codex_turns',16)):
        if type(value[field]) is not int or not 1<=value[field]<=maximum:raise ValueError('Invalid '+field)
    if type(value['api_cash_usd']) not in (int,float) or not .32<=value['api_cash_usd']<=5:raise ValueError('API cash phase cap must be between .32 and 5 USD')
    if type(value['candidate_cash_usd']) not in (int,float) or not .32<=value['candidate_cash_usd']<=.5:raise ValueError('Candidate cash must cover one worst-case reservation, up to USD .5')
    if value['pause_after'] not in ('','candidates','verifier_input','reviewer','verify_m','verifier_m','builder'):raise ValueError('Unknown pause boundary')
    if not isinstance(value['builder_direction'],str) or not 1<=len(value['builder_direction'])<=10000:raise ValueError('Builder direction required')
    safe_text(value['builder_direction']);return value


class Execution:
    def __init__(self,memory):
        self.memory=memory;self.mutex=threading.Lock();self.running=None;self.deployed=False
        self.limits=json.loads((ROOT/'configs/budget-p5.json').read_text(encoding='utf-8'))
        self.frozen_sources={};self.imported={};self.pending={};self.timing={}
        # A server restart does not silently replay paid inference.
        for saved in memory.list('run'):
            if saved.get('phase')=='P5' and saved['status'] in ('RUNNING','PAUSE_REQUESTED','STOP_REQUESTED'):
                memory.record('run',saved['id'],saved|{'status':'INTERRUPTED','reason':'Controller restarted; preserve and inspect native checkpoint before explicit recovery'})
            if saved.get('phase')=='P5':
                try:
                    node=memory.get('attempt',saved['id']+'/task');status=memory.get('run',saved['id'])['status']
                    if node['status']!=status:memory.record('attempt',node['id'],node|{'status':status})
                except KeyError:pass

    def deploy(self):
        if self.deployed:return
        from run_p3_experiment import deploy,source_map
        deploy()
        paths=['scripts/p5_runtime_linux.py','scripts/p5_controller_linux.py','scripts/p5_harvest_linux.py',
               '.hmz/flows/workbench_loop/__init__.py']
        code='from pathlib import Path;import sys;p=Path(sys.argv[1]);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(sys.stdin.buffer.read())'
        for path in paths:
            target='/opt/workbench/source/'+Path(path).name if path.startswith('scripts') else '/opt/workbench/source/flows/workbench_loop/__init__.py'
            result=wsl(['python','-c',code,target],input_bytes=(ROOT/path).read_bytes())
            if result.returncode:raise RuntimeError('Runtime deployment failed')
        self.frozen_sources=source_map()|{path:sha((ROOT/path).read_bytes()) for path in paths};self.deployed=True

    def default_contract(self):
        from p1_fixture import TASK,TESTS
        from p2_candidates import EXTRA
        env=sha((ROOT/'configs/requirements-p1-linux.lock').read_bytes())
        return {'task_id':'workbench-weighted-mean','prompt':TASK,'base_repository':'/opt/workbench/source/p1-frozen-fixture',
                'base_commit':'561bd401a218246f5a823e8e3e0f0eea374163aa','env_hash':env,'source_file':'weighted_stats.py',
                'visible_test_program':TESTS+'\nunittest.main(verbosity=2)\n',
                'acceptance_test_program':TESTS+EXTRA+'\nunittest.main(verbosity=2)\n','protected_files':{'test_weighted_stats.py':sha(TESTS.encode())}}

    def start(self,options,contract=None,parent=None,reuse_pool=None):
        options=settings(options)
        accepted=json.loads((ROOT/'.local-workbench/audits/p4-functional.json').read_text())
        if accepted['functional_gate']!='PASS':raise PermissionError('P4 functional gate missing')
        contract=contract or self.default_contract();validate_contract(contract,sha((ROOT/'configs/requirements-p1-linux.lock').read_bytes()))
        safe_text(canonical(contract).decode())
        with self.mutex:
            if self.running:raise ValueError('One active native Flow at a time; pause/stop it before starting another')
            run_id='p5-'+datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')+'-'+uid('r')[-8:]
            task_id=run_id+'/task';contract_ref=self.memory.artifact(canonical(contract),'frozen-full-contract','human')
            self.memory.record('task',task_id,{'name':contract['task_id'],'contract':{'prompt':contract['prompt'],'base_sha':contract['base_commit'],
                      'env_hash':contract['env_hash']},'full_contract_artifact':contract_ref,'status':'RUNNING','parent_node':parent})
            self.memory.record('run',run_id,{'phase':'P5','task_id':task_id,'flow':'workbench_loop','status':'RUNNING','settings':options,
                  'limits':self.limits|{'api_cash_usd':options['api_cash_usd'],'deepseek_inference_requests':options['ds_requests'],
                                      'codex_subscription_turns':options['codex_turns']},
                  'contract_artifact':contract_ref,'created_at':now(),'parent_node':parent,'reuse_pool_path':reuse_pool,'elapsed_seconds':0})
            self.running=run_id
            threading.Thread(target=self._execute,args=(run_id,'start',contract),daemon=True).start()
        return self.memory.get('run',run_id)

    def retry_pool(self,run_id,options=None):
        value=self.memory.get('run',run_id)
        if value.get('phase')!='P5' or value['status'] not in ('INFRA_FAIL','TIMEOUT','CANCELLED','INTERRUPTED'):raise ValueError('Only preserved failed/interrupted P5 runs may explicitly retry their frozen pool')
        pool=value.get('reuse_pool_path') or '/opt/workbench/runs/'+run_id+'-pool/frozen-pool.json'
        result=wsl(['cat',pool])
        if result.returncode:raise ValueError('No complete frozen pool to reuse; continue from a saved commit instead')
        from p2_candidates import validate_pool
        frozen=validate_pool(json.loads(result.stdout))
        contract=json.loads(self.memory.read_artifact(value['contract_artifact']))
        if frozen.get('contract_manifest')!=contract:raise ValueError('Frozen pool contract differs; no task substitution')
        direction=settings(options or value['settings'])
        if direction['n']!=len(frozen['candidates']):raise ValueError('Reusing a pool keeps its original N; generating a different N requires a new task')
        return self.start(direction,contract,parent=run_id+'/verifier_input',reuse_pool=pool)

    def request(self,run_id,action):
        if not re.fullmatch('p5-[a-z0-9-]+',run_id) or action not in ('pause','stop','resume'):raise ValueError('Invalid execution action')
        value=self.memory.get('run',run_id)
        if action=='stop' and value['status']=='PAUSED':
            self.memory.record('run',run_id,value|{'status':'CANCELLED','reason':'Human cancelled a durable paused checkpoint; no active inference process'})
            task=self.memory.get('task',value['task_id']);self.memory.record('task',task['id'],task|{'status':'CANCELLED'})
            self._finish_nodes(run_id,'CANCELLED')
            self.memory.record('action',uid('stop'),{'task_id':value['task_id'],'run_id':run_id,'kind':'stop','status':'APPLIED'},'human_owner')
            return self.memory.get('run',run_id)
        if action=='resume':
            with self.mutex:
                if self.running or value['status']!='PAUSED':raise ValueError('Only an inactive durably paused Flow can resume')
                self.running=run_id;self.memory.record('run',run_id,value|{'status':'RUNNING'})
                threading.Thread(target=self._execute,args=(run_id,'resume',None),daemon=True).start()
        else:
            if self.running!=run_id or value['status'] not in ('RUNNING','PAUSE_REQUESTED','STOP_REQUESTED'):raise ValueError('Run is not active')
            self.pending[run_id]=action
            self._pending(run_id)
            self.memory.record('run',run_id,value|{'status':'PAUSE_REQUESTED' if action=='pause' else 'STOP_REQUESTED'})
        self.memory.record('action',uid(action),{'task_id':value['task_id'],'run_id':run_id,'kind':action,'status':'REQUESTED'},'human_owner')
        return self.memory.get('run',run_id)

    def continue_from(self,node_id,options,contract=None):
        node=self.memory.get('attempt',node_id);task=self.memory.get('task',node['task_id'])
        decisions=[a for a in self.memory.list('action',node['task_id']) if a.get('attempt_id')==node_id and a.get('kind') in ('reject','route')]
        if decisions and decisions[-1]['kind']=='reject':raise PermissionError('This route was rejected; record a new human direction before continuing')
        if self.running:raise ValueError('Pause/stop active execution before a new fork')
        head=node.get('recovery_sha',node.get('head_sha'))
        if not isinstance(head,str) or not re.fullmatch('[a-f0-9]{40}',head):raise ValueError('Saved recoverable commit required')
        if contract is None:
            if task.get('full_contract_artifact'):contract=json.loads(self.memory.read_artifact(task['full_contract_artifact']))
            else:
                origin=node
                if not origin.get('run_id') and origin.get('parent_node'):origin=self.memory.get('attempt',origin['parent_node'])
                historical_run=origin.get('run_id') or ''
                if not historical_run.startswith('p3-'):raise ValueError('Full saved contract or explicit new contract required')
                # Read the historical frozen controller contract, never reconstruct hidden tests from chats.
                code="import json,sys;from pathlib import Path;r=Path('/opt/workbench/runs')/sys.argv[1];p=r/'frozen-pool.json';c=r/'control/run-contract.json';p=Path(json.loads(c.read_text())['pool_path']) if c.exists() else p;print(json.dumps(json.loads(p.read_text()).get('contract_manifest')))"
                result=wsl(['python','-c',code,historical_run])
                if result.returncode:raise ValueError('Historical full contract unavailable; supply an explicit frozen task contract')
                contract=json.loads(result.stdout) or self.default_contract()
        contract=dict(contract);identity=uid('continue');ref='refs/heads/workbench/'+identity
        git(ROOT,'update-ref',ref,head)
        folder=self.memory.root/'git-bundles';folder.mkdir(exist_ok=True);bundle=folder/(identity+'.bundle')
        git(ROOT,'bundle','create',str(bundle),ref)
        prepared='/opt/workbench/source/p5-'+identity
        code='''import base64,json,subprocess,sys
from pathlib import Path
v=json.load(sys.stdin);p=Path(v['prepared']);b=p.with_suffix('.bundle');b.write_bytes(base64.b64decode(v['bundle']))
def git(*a):subprocess.run(['git','-c','core.hooksPath=/dev/null',*a],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
git('clone','--no-local',str(b),str(p));git('-C',str(p),'checkout','--detach',v['head']);git('-C',str(p),'remote','remove','origin')
print('prepared')
'''
        result=wsl(['python','-c',code],input_bytes=canonical({'prepared':prepared,'head':head,'bundle':base64.b64encode(bundle.read_bytes()).decode()}))
        if result.returncode:raise RuntimeError('Historical fork transfer failed; original retained')
        contract.update(base_repository=prepared,base_commit=head,task_id=contract['task_id']+'-fork')
        return self.start(options,contract,parent=node_id)

    def _pending(self,run_id):
        if run_id not in self.pending:return
        action=self.pending[run_id]
        code="from pathlib import Path;import sys;p=Path('/opt/workbench/runs')/sys.argv[1]/'control';ready=(p/'run-contract.json').exists();(p/(sys.argv[2]+'.requested')).write_text('Human owner requested '+sys.argv[2]) if ready else None;sys.exit(0 if ready else 2)"
        result=wsl(['python','-c',code,run_id,action])
        if result.returncode==0:self.pending.pop(run_id,None)

    def _execute(self,run_id,mode,contract):
        tick=time.perf_counter()
        self.timing[run_id]=(tick,self.memory.get('run',run_id).get('elapsed_seconds',0))
        try:
            self.deploy();value=self.memory.get('run',run_id)
            import yaml
            key=yaml.safe_load((Path(os.environ['USERPROFILE'])/'.dsh/.credentials.yaml').read_text(encoding='utf-8'))['refs']['DEEPSEEK_API_KEY']
            payload={'phase':'P5','p4_gate':'PASS','mode':mode,'run_id':run_id,'limits':value['limits'],'settings':value['settings'],
                     'task_contract':contract,'runtime_lock_sha256':sha((ROOT/'configs/requirements-p1-linux.lock').read_bytes()),
                     'source_sha256':self.frozen_sources,'parent_node':value.get('parent_node'),'reuse_pool_path':value.get('reuse_pool_path'),'key':key}
            raw=canonical(payload);payload['key']='';key=''
            outcome=[]
            def launch():
                outcome.append(wsl(['timeout','--signal=TERM','--kill-after=5s','1245s','python','/opt/workbench/source/p5_controller_linux.py'],input_bytes=raw,timeout=1280))
            worker=threading.Thread(target=launch,daemon=True);worker.start()
            while worker.is_alive():
                self._pending(run_id)
                try:self.harvest(run_id)
                except (RuntimeError,ValueError,FileNotFoundError):pass  # incomplete stage remains unavailable; final import must succeed
                worker.join(5)
            raw=b''
            if not outcome:raise RuntimeError('Execution transport failed; preserved Linux run')
            result=outcome[0];log=safe_text((result.stdout+b'\n'+result.stderr).decode('utf-8',errors='replace'),redact=True)
            ref=self.memory.artifact(log,'controller-full-log','human')
            self.harvest(run_id)
            native={}
            for line in result.stdout.decode(errors='replace').splitlines():
                if line.startswith('{'):
                    try:native=json.loads(line)
                    except ValueError:pass
            current=self.memory.get('run',run_id)
            self.memory.record('run',run_id,current|{'status':native.get('status','INFRA_FAIL'),'native':native,'log_artifact':ref,
                    'elapsed_seconds':native.get('active_elapsed_seconds',time.perf_counter()-tick),'transport_exit':result.returncode})
            task=self.memory.get('task',current['task_id'])
            self.memory.record('task',current['task_id'],task|{'status':native.get('task_verdict',native.get('status','INFRA_FAIL'))})
            self._finish_nodes(run_id,native.get('status','INFRA_FAIL'))
        except BaseException as error:
            value=self.memory.get('run',run_id)
            self.memory.record('run',run_id,value|{'status':'INFRA_FAIL','error_type':type(error).__name__,
                'error':safe_text(str(error)[:700],redact=True),'elapsed_seconds':time.perf_counter()-tick,'usage':'unavailable'})
            task=self.memory.get('task',value['task_id']);self.memory.record('task',value['task_id'],task|{'status':'INFRA_FAIL'})
            self._finish_nodes(run_id,'INFRA_FAIL')
        finally:
            self.timing.pop(run_id,None)
            with self.mutex:self.running=None

    def visible_runs(self):
        result=self.memory.list('run')
        for value in result:
            if value['id'] in self.timing:
                tick,previous=self.timing[value['id']]
                value['live_transport_elapsed_seconds']=previous+time.perf_counter()-tick
        return result

    def _finish_nodes(self,run_id,status):
        try:
            root=self.memory.get('attempt',run_id+'/task');self.memory.record('attempt',root['id'],root|{'status':status})
        except KeyError:return
        if status not in ('CANCELLED','INFRA_FAIL','TIMEOUT'):return
        ops=GitOps(self.memory)
        for node in self.memory.list('attempt',root['task_id']):
            if node.get('role') not in ('candidate','builder','reviewer') or node['status']=='PASS':continue
            try:manifest=json.loads(self.memory.read_artifact(node['artifacts']['manifest']))
            except (KeyError,ValueError):continue
            if manifest.get('partial_files'):
                ops.preserve_partial(node['id'],manifest['partial_files'])

    def harvest(self,run_id):
        result=wsl(['python','/opt/workbench/source/p5_harvest_linux.py',run_id],timeout=90)
        if result.returncode:raise RuntimeError('Evidence harvest incomplete')
        data=json.loads(result.stdout)
        if not data:return
        fingerprint=sha(data)
        if self.imported.get(run_id)==fingerprint:return
        saved=self.memory.get('run',run_id);task=saved['task_id'];pool=data.get('pool');parents=[]
        full=json.loads(self.memory.read_artifact(saved['contract_artifact']))
        basic=self.memory.get('task',task)['contract']
        root_id=run_id+'/task'
        self.memory.record('attempt',root_id,{'task_id':task,'run_id':run_id,'role':'task','label':full['task_id'],'parents':[saved['parent_node']] if saved.get('parent_node') else [],
                    'status':saved['status'],'head_sha':full['base_commit'],'base_sha':full['base_commit'],'contract':basic,'artifacts':{},'model_id':'not_applicable'})
        bundles=self.memory.root/'git-bundles';bundles.mkdir(exist_ok=True)
        for row in data['bundles']:
            identity=row.get('candidate',row.get('role'));blob=base64.b64decode(row['data']);file=bundles/(run_id+'-'+identity+'-'+sha(blob)[:12]+'.bundle')
            if not file.exists():file.write_bytes(blob)
            git(ROOT,'bundle','verify',str(file))
            # Local synthetic/private refs only; publishing is a separate human privacy decision.
            git(ROOT,'fetch',str(file),'refs/heads/*:refs/heads/workbench/'+run_id+'/'+identity+'/*')
        def add(identity,label,role,value,edges,linux=None):
            refs={'manifest':self.memory.artifact(canonical(value),'stage-manifest','human')}
            for name in ('source','patch'):
                if value.get(name):
                    content=value[name].encode();digest=sha(content)
                    try:old=self.memory.get('artifact',digest)
                    except KeyError:old=None
                    refs[name]=old['id'] if old and old['access']=='human' else self.memory.artifact(content,name,'agent')
            head=value.get('head_commit',full['base_commit'])
            node={'task_id':task,'run_id':run_id,'label':label,'role':role,'parents':edges,
                  'base_sha':value.get('base_commit',full['base_commit']),'head_sha':head,'status':value.get('verdict',value.get('status','unavailable')),
                  'artifacts':refs,'contract':basic,'linux_worktree':linux,'model_id':value.get('model_id','not_applicable' if role=='task' else 'unavailable'),
                  'session_id':value.get('session_id','unavailable'),'usage':value.get('usage',value.get('tokens','unavailable')),
                  'elapsed_seconds':value.get('elapsed_stage_seconds',value.get('elapsed_seconds',value.get('timeline',{}).get('candidate_wall_seconds','unavailable'))),
                  'timeline':value.get('timeline',{}),'api_cash_upper_bound_usd':value.get('api_peak_upper_bound_usd','unavailable')}
            try:node['trace_artifacts']=self.memory.get('attempt',identity).get('trace_artifacts',[])
            except KeyError:pass
            try:
                old=self.memory.get('attempt',identity)
                for field in ('recovery_sha','partial_tree_hash','recovery_kind','recovery_node'):
                    if field in old:node[field]=old[field]
            except KeyError:pass
            self.memory.record('attempt',identity,node)
            if value.get('test_report'):
                ref=self.memory.artifact(canonical(value['test_report']),'hard-test-result','human')
                self.memory.record('test_result',identity+'/test',{'task_id':task,'attempt_id':identity,'artifact':ref,**{k:v for k,v in value['test_report'].items() if k!='log'}})
        if pool:
            for candidate in pool['candidates']:
                from pathlib import PurePosixPath
                identity=run_id+'/'+candidate['id'];edges=[root_id]
                if saved.get('reuse_pool_path'):
                    original=PurePosixPath(data['pool_path']).parent.name.removesuffix('-pool')+'/'+candidate['id']
                    edges.append(original);candidate=candidate|{'kind':'REUSED_FROZEN_CANDIDATE','original_generation_node':original,
                        'new_model_requests':0,'elapsed_stage_seconds':0,'usage_provenance':'Original generation usage; no new candidate inference in this run'}
                add(identity,candidate['id'],'candidate',candidate,edges,str(PurePosixPath(data['pool_path']).parent/candidate['id']/'worktree'));parents.append(identity)
        stages=data['stages'];roles=data['roles']
        for name,value in stages.items():
            if name=='candidates':continue
            identity=run_id+'/'+name;role='verifier' if name.startswith('verifier') else ('reviewer' if name in ('reviewer','verify_m') else 'builder')
            if name=='verifier_input':edges=parents
            elif name=='reviewer':edges=[*parents,run_id+'/verifier_input']
            elif name=='verify_m':edges=[run_id+'/reviewer']
            elif name=='verifier_m':edges=[*parents,run_id+'/verify_m']
            elif name=='builder':edges=[run_id+'/verifier_m',run_id+'/verify_m']
            else:edges=[run_id+'/builder']
            worker=roles.get(name,{})
            add(identity,{'reviewer':'Reviewer','verify_m':'候选 M','builder':'Sol Builder'}.get(name,value.get('judge','J3')+' '+name),role,
                worker|value,edges,'/opt/workbench/runs/'+run_id+'/roles/'+('reviewer' if name=='verify_m' else name)+'/worktree' if role!='verifier' else None)
            if name.startswith('verifier'):self.memory.record('judgment',identity,{'task_id':task,'attempt_id':identity,**value})
        for row in data['traces']:
            identity=run_id+'/'+row.get('candidate',row.get('role'))
            try:node=self.memory.get('attempt',identity)
            except KeyError:continue
            raw=base64.b64decode(row['data']);text=safe_text(raw.decode('utf-8',errors='replace'),redact=True)
            ref=self.memory.artifact(text,'full-trace','human',{'path':row['path'],'original_sha256':sha(raw)})
            if ref not in node.get('trace_artifacts',[]):
                node['trace_artifacts']=node.get('trace_artifacts',[])+[ref];self.memory.record('attempt',identity,node)
        if data.get('ledger'):
            ledger=data['ledger'];self.memory.record('project_contract','p5-ledger',{'phase':'P5','requests':len(ledger['requests']),
                  'codex_turns':len(ledger['codex_turns']),'cash_upper_bound_usd':ledger['cash_bound_nano']/1e9,
                  'ledger_hash':sha(ledger),'usage':[r.get('usage','unavailable') for r in ledger['requests']],
                  'api_bill_usd':'unavailable','subscription_cost_usd':'unavailable','subscription_api_cash_usd':0})
        saved=self.memory.get('run',run_id)
        self.memory.record('run',run_id,saved|{'completed_stages':list(stages),'native_checkpoint':data.get('resume'),
                    'elapsed_seconds':data.get('resume',{}).get('active_elapsed_seconds',saved['elapsed_seconds'])})
        self.imported[run_id]=fingerprint
