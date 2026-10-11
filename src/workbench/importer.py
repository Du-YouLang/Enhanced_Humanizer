"""Import immutable P3 facts and full local trace derivatives, including failed partial work."""

import base64
import json
from pathlib import Path,PurePosixPath
import sys

from .memory import ROOT,canonical,safe_text,sha,uid


def import_p3(memory,traces=True):
    raw=(ROOT/'docs/audits/P3-evidence-2026-10-10.json').read_bytes();evidence=json.loads(raw)
    import_id='p3-v2-'+sha(raw)[:16]
    try:
        previous=memory.get('project_contract',import_id)
        if previous.get('completed'):return previous
    except KeyError:pass
    memory.record('project_contract',import_id,{'name':'Enhanced_Humanizer','version':'PRD-v0.4','input_sha256':sha(raw),
                   'immutable_rules':['official Harnesses only','hidden answers withheld','human review for every product PR'],
                   'source':'docs/audits/P3-evidence-2026-10-10.json'})
    partials={row['original_pool_hash']:row for row in evidence.get('partial_archives',[])}
    trace_spec=[];node_count=0
    bundle_refs={row['head_commit']:row['remote_archive_ref'] for row in evidence['bundles']}
    def artifact(value,kind,access='human'):
        data=value.encode() if isinstance(value,str) else canonical(value)
        try:
            old=memory.get('artifact',sha(data))
            if access=='agent' and old['access']=='human':return old['id']  # retain the stricter access on identical bytes
        except KeyError:pass
        return memory.artifact(data,kind,access)
    def add(task,run,identifier,role,head,base,status,parents=(),manifest=None,linux=None,contract=None,**extra):
        nonlocal node_count
        manifest=manifest or {};artifacts={}
        for key in ('source','patch'):
            if isinstance(manifest.get(key),str):artifacts[key]=artifact(manifest[key],key,'agent')
        if manifest.get('test_report'):artifacts['hard_tests']=artifact(manifest['test_report'],'hard-test-result')
        if manifest.get('visible_tests'):artifacts['visible_tests']=artifact(manifest['visible_tests'],'visible-test-result','agent')
        artifacts['manifest']=artifact(manifest,'controller-manifest')
        kind=manifest.get('kind','REAL_MODEL_EXPERIMENT')
        controlled=kind.startswith('CONTROLLED')
        value={'task_id':task,'run_id':run,'role':role,'label':extra.pop('label',identifier.rsplit('/',1)[-1]),
               'base_sha':base,'head_sha':head,'status':status,'parents':list(parents),'artifacts':artifacts,
               'kind':kind,'model_id':'not_applicable' if controlled else manifest.get('model_id','unavailable'),
               'session_id':manifest.get('session_id','unavailable'),'harness':manifest.get('harness','unavailable'),
               'tool_versions':{'Humanize':'0.1.0b2','DSH':'0.1.5rc1','Codex':'0.162.0-alpha.2'},
               'usage':manifest.get('usage',manifest.get('tokens','unavailable')),
               'elapsed_seconds':manifest.get('timeline',{}).get('candidate_wall_seconds',manifest.get('elapsed_seconds',manifest.get('verification_seconds','unavailable'))),
               'api_bill_usd':'unavailable','archive_ref':bundle_refs.get(head),'linux_worktree':linux,
               'contract':contract or memory.get('task',task)['contract'],**extra}
        memory.record('attempt',identifier,value);node_count+=1
        if manifest.get('test_report'):
            report=manifest['test_report']
            memory.record('test_result',identifier+'/test',{'task_id':task,'attempt_id':identifier,'verdict':report['verdict'],
                 'suite_sha256':report['suite_sha256'],'artifact':artifacts['hard_tests'],'hidden_test_artifact':artifacts['hard_tests'],
                 'exit_code':report.get('exit_code','unavailable')})
        return identifier
    # Original pools are already publicly reviewed controlled synthetic fixtures.
    sys.path.insert(0,str(ROOT/'scripts'))
    from wsl_project import run as wsl
    for record in evidence['runs']:
        run_id=record['run_id'];case=record['case'];task='p3-'+case
        pool_source='/opt/workbench/runs/'+run_id+'/control/run-contract.json'
        p=wsl(['cat',pool_source]);contract_record=json.loads(p.stdout)
        p=wsl(['cat',contract_record['pool_path']]);pool=json.loads(p.stdout)
        contract={'prompt':pool['task_contract'],'base_sha':pool['base_commit'],'env_hash':pool['env_hash'],'task_hash':pool['task_hash']}
        memory.record('task',task,{'name':{'mixed':'混合候选与完整接力','all-failed':'全失败池恢复','impossible':'矛盾任务与拒绝'}[case],
               'contract':contract,'issue_url':evidence['issue'],'pr_url':'https://github.com/Du-YouLang/Enhanced_Humanizer/pull/10',
               'status':record['task_status'],'source_run':run_id})
        memory.record('run',run_id,{'task_id':task,'flow':'synthesis_loop','n_candidates':3,'status':'COMPLETED',
               'elapsed_seconds':record['active_elapsed_seconds'],'contract':contract,'budget':evidence['budget'],
               'segments':record['segments'],'source_hashes':record['controller_source_sha256']})
        root=add(task,run_id,run_id+'/task','task',pool['base_commit'],pool['base_commit'],record['task_status'],label='任务合同')
        candidates=[]
        for c in pool['candidates']:
            node=add(task,run_id,run_id+'/'+c['id'],'candidate',c['head_commit'],c['base_commit'],c['verdict'],[root],c,
                     linux=str(PurePosixPath(contract_record['pool_path']).parent/c['id']/'worktree'),label=c['id'])
            candidates.append(node)
        stages=record['stages'];roles={r['name']:r for r in record['roles']}
        first=stages['verifier_input']
        first_id=add(task,run_id,run_id+'/judge-input','verifier',pool['base_commit'],pool['base_commit'],first['status'],candidates,
                     roles.get('verifier_input',{})|{'judgment':first},label=first.get('judge','J0')+' 初筛')
        memory.record('judgment',first_id,{'task_id':task,'attempt_id':first_id,**first})
        merged=stages['verify_m'];node=run_id+'/M'
        add(task,run_id,node,'reviewer',merged['head_commit'],merged['base_commit'],merged['verdict'],[*candidates,first_id],
            merged|roles['reviewer'],linux='/opt/workbench/runs/'+run_id+'/roles/reviewer/worktree',label='Reviewer → M')
        trace_spec.append({'node_id':node,'run_id':run_id,'role':'reviewer'})
        if 'verifier_input' in roles:trace_spec.append({'node_id':first_id,'run_id':run_id,'role':'verifier_input'})
        second=stages['verifier_m'];selected=record['comparison']['selected_candidate']
        selected_node=node if selected=='M' else (run_id+'/'+selected if selected else root)
        selected_sha=memory.get('attempt',selected_node)['head_sha']
        judge_id=add(task,run_id,run_id+'/judge-M','verifier',selected_sha,pool['base_commit'],second['status'],[*candidates,node],
                     roles['verifier_m']|{'judgment':second},label='J3 比较 A…M')
        trace_spec.append({'node_id':judge_id,'run_id':run_id,'role':'verifier_m'})
        memory.record('judgment',judge_id,{'task_id':task,'attempt_id':judge_id,**second})
        memory.record('decision',run_id+'/selection',{'task_id':task,'alternatives':[*candidates,node],'selected':selected_node if selected else None,
                      'reason':second.get('rationale','Frozen hard acceptance and independent J3'),'evidence_refs':[judge_id],
                      'human_approval':False,'M_wins_automatically':False,'comparison':record['comparison']})
        builder=stages['builder']
        if builder.get('verdict')=='PASS':
            builder_id=add(task,run_id,run_id+'/Sol','builder',builder['head_commit'],builder['base_commit'],'PASS',[selected_node,judge_id],
                           builder|roles['builder'],linux='/opt/workbench/runs/'+run_id+'/roles/builder/worktree',label='Sol 重设计')
            trace_spec.append({'node_id':builder_id,'run_id':run_id,'role':'builder'})
            returned=next(p for p in evidence['DS_return_pools'] if p['base_commit']==builder['head_commit'])
            ret_id=PurePosixPath(stages['ds_return']['pool_path']).parent.name
            ret_contract={'prompt':returned['task_contract'],'base_sha':returned['base_commit'],'env_hash':returned['env_hash'],'task_hash':returned['task_hash']}
            memory.record('run',ret_id,{'task_id':task,'flow':'ds_candidates','contract':ret_contract,'n_candidates':3,'status':returned['failure_report']['status']})
            ret_nodes=[]
            for c in returned['candidates']:
                recovery=partials.get(returned['pool_hash']) if c['verdict']!='PASS' else None
                node_id=ret_id+'/'+c['id']
                add(task,ret_id,node_id,'candidate',c['head_commit'],c['base_commit'],c['verdict'],[builder_id],c,
                    linux='/opt/workbench/runs/'+ret_id+'/'+c['id']+'/worktree',contract=ret_contract,
                    label='DS 回接 '+c['id'],recovery_sha=recovery['head_commit'] if recovery else c['head_commit'],
                    partial_snapshot_kind=recovery['kind'] if recovery else None)
                trace_spec.append({'node_id':node_id,'run_id':ret_id,'candidate':c['id']});ret_nodes.append(node_id)
            last=stages['verifier_return'];last_id=add(task,run_id,run_id+'/judge-return','verifier',builder['head_commit'],builder['head_commit'],last['status'],ret_nodes,
                    roles['verifier_return']|{'judgment':last},label='J3 回接复核')
            trace_spec.append({'node_id':last_id,'run_id':run_id,'role':'verifier_return'})
            memory.record('judgment',last_id,{'task_id':task,'attempt_id':last_id,**last})
            add(task,run_id,run_id+'/PR','development-pr','8d9b11de9ccbe13f12fb8a9b32a89fb19991404b',builder['head_commit'],'MERGED',[last_id],
                label='开发 PR #10',pr_url='https://github.com/Du-YouLang/Enhanced_Humanizer/pull/10',human_product_approval=False)
        fact=uid('fact');ref=memory.get('attempt',node)['artifacts']['manifest']
        memory.record('knowledge',fact,{'task_id':task,'state':'fact','text':'冻结硬验收：M '+merged['verdict']+'；不由语言评分覆盖失败。','evidence_refs':[ref]})
        memory.record('knowledge',uid('hypothesis'),{'task_id':task,'state':'hypothesis','text':'这种接力是否提升真实科研任务成功率仍待 P6 对照。','evidence_refs':[]})
        memory.record('knowledge',uid('unresolved'),{'task_id':task,'state':'unresolved','text':'Jev 地区限制；未运行，不把 Sol 结果称为 Jev。','evidence_refs':[]})
        if case=='impossible':memory.record('knowledge',uid('rejected'),{'task_id':task,'state':'rejected','text':'同时满足相互矛盾的 float 要求被 Reviewer 拒绝。','evidence_refs':[ref]})
    for old in evidence.get('retained_attempts_and_pauses',[]):
        identifier=old['run_id']+'/segment-'+str(old['segment'])
        task='p3-'+('mixed' if 'mixed' in old['run_id'] else 'all-failed')
        ref=artifact(old,'preserved-pause-or-failed-startup')
        memory.record('action',identifier,{'task_id':task,'kind':'PRESERVED_EXECUTION_HISTORY','record':old,'artifact':ref})
        if old.get('final_disposition'):
            memory.record('attempt',old['run_id']+'/startup',{'task_id':task,'run_id':old['run_id'],'role':'infrastructure','status':'INFRA_FAIL',
                'parents':[],'label':'保留的 Sol 启动失败','head_sha':memory.get('task',task)['contract']['base_sha'],
                'base_sha':memory.get('task',task)['contract']['base_sha'],'model_id':'unavailable','usage':'unavailable',
                'elapsed_seconds':old['active_elapsed_seconds'],'artifacts':{'manifest':ref},'kind':'REAL_FAILED_STARTUP','contract':memory.get('task',task)['contract']})
            node_count+=1
    p2=json.loads((ROOT/'docs/audits/P2-evidence-2026-10-10.json').read_text(encoding='utf-8'))
    for attempt in p2['judge_attempts']:
        for judgment in attempt['judges']:
            memory.record('judgment',attempt['run_id']+'/'+judgment['judge'],{'task_id':'p3-mixed','historical_phase':'P2',**judgment})
    if traces:
        script=ROOT/'scripts/export_memory_traces_linux.py'
        p=wsl(['python','-c',"from pathlib import Path;import sys;Path('/opt/workbench/source/export_memory_traces_linux.py').write_bytes(sys.stdin.buffer.read())"],input_bytes=script.read_bytes())
        if p.returncode:raise ValueError('Trace exporter deployment failed')
        p=wsl(['python','/opt/workbench/source/export_memory_traces_linux.py'],input_bytes=canonical(trace_spec))
        if p.returncode:raise ValueError('Private trace import failed')
        trace_rows=json.loads(p.stdout)
        for row in trace_rows:
            original=base64.b64decode(row['data']);text=original.decode('utf-8',errors='replace');safe=safe_text(text,redact=True)
            identifier=memory.artifact(safe,'full-trace','human',{'path':row['source'],'original_sha256':sha(original),'redacted':safe!=text})
            node=memory.get('attempt',row['node_id']);node.setdefault('trace_artifacts',[]).append(identifier)
            memory.record('attempt',row['node_id'],node)
    result={'id':import_id,'imported_nodes':node_count,'full_traces':sum(len(a.get('trace_artifacts',[])) for a in memory.list('attempt')),
            'actual_new_model_requests':0,'source_hash':sha(raw),'completed':True}
    memory.record('project_contract',import_id,memory.get('project_contract',import_id)|result)
    return result
