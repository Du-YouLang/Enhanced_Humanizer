"""Workbench stages reuse Humanize + the accepted DSH/Codex execution boundaries."""
import json
from pathlib import Path
import time

from p2_candidates import BASE,digest,exclusive_json
from p2_experiment_linux import pool_run
from p2_judges import J0
from p3_contracts import read_json,judge_pool,with_initial_judgment,validate_candidate_coverage,validate_handoff,compare
import p3_runtime_linux as runtime

STAGES=('candidates','verifier_input','reviewer','verify_m','verifier_m','builder','verifier_builder')
CONTEXT={}


def load(root,name):return runtime.load_stage(root,name)


def frozen_handoff(root,pool_path):
    """Freeze visible reports once; re-running timed tests changes their digest."""
    path=Path(root)/'inputs/candidate-handoff.json'
    if path.exists():package=validate_handoff(read_json(path))
    else:
        package=runtime.build_handoff(pool_path);validate_handoff(package);exclusive_json(path,package)
    if package['pool_hash']!=read_json(pool_path)['pool_hash']:raise ValueError('Frozen handoff pool changed')
    return package


def judge(root,name,pool,mode):
    if mode=='J0':return J0().judge(pool)
    if mode=='J3':return runtime.judge(root,name,pool)
    if mode=='J1':
        from p2_judges import J1,LavTransport
        import os,sys
        sys.path.insert(0,'/opt/workbench/upstreams/lav')
        import llm_verifier.fine_grained_reward as lav
        os.environ['DEEPSEEK_EFFORT']='off';os.environ['DEEPSEEK_MAX_TOKENS']='4096'
        client=LavTransport(CONTEXT['key'],CONTEXT['ledger'],Path(root).name+'/'+name,CONTEXT['deadline'],lav,Path(root)/'results'/(name+'-probabilities'))
        try:return J1(client,'/opt/workbench/upstreams/lav',BASE/'state/p5-judge-cache').judge(pool)
        finally:client.key=''
    raise ValueError('Jev is blocked; no silent substitute')


def stage(root,name):
    root=Path(root);path=root/'results'/(name+'.json')
    if path.exists():return load(root,name)
    contract=read_json(root/'control/run-contract.json');task=contract['task_contract'];settings=contract['settings']
    tick=time.perf_counter()
    if name=='candidates':
        value=pool_run({'run_id':root.name+'-pool','n':settings['n'],'concurrency':settings['concurrency'],
              'task_contract':task,'runtime_lock_sha256':task['env_hash'],
              'candidate_seconds':settings['candidate_seconds'],'candidate_request_cap':settings['candidate_requests'],
              'candidate_cash_cap_usd':settings['candidate_cash_usd'],'cancel_event':runtime.STOP},CONTEXT['key'],CONTEXT['ledger'],CONTEXT['deadline'])
        value['status']='COMPLETED' if value.get('pool_path') else value['verdict']
    else:
        pool_path=load(root,'candidates')['pool_path'];pool=read_json(pool_path)
        runtime.CONTEXT.update(pool_path=pool_path)
        if name=='verifier_input':value=judge(root,name,judge_pool(frozen_handoff(root,pool_path)),settings['judge'])
        elif name=='reviewer':
            package=with_initial_judgment(frozen_handoff(root,pool_path),load(root,'verifier_input'));validate_handoff(package)
            prompt='Fresh independent Reviewer. Read ALL successful and failed input candidates and all visible evidence. Freely design and IMPLEMENT candidate M, including rewriting when justified. Preserve frozen protected files/dependencies, test and create a clean real commit. Refuse contradictory requirements with evidence. Never claim failed work passed. No subagents/network/installs/prior chat. Report each input candidate ID exactly once in considered_candidates; M is your output, not an input. Hidden answers withheld.\n'+json.dumps(package,sort_keys=True)
            value=runtime.role_run(root,name,'reviewer',package,prompt,source=task['base_repository'])
            if value['status']=='COMPLETED':
                try:value['coverage']=validate_candidate_coverage([c['id'] for c in pool['candidates']],value.get('answer',{}).get('decision',{}).get('considered_candidates'))
                except ValueError:value=dict(value,status='INFRA_FAIL',error_type='IncompleteCandidateCoverage')
        elif name=='verify_m':value=runtime.verify_role(root,'reviewer','M',pool['base_commit'],pool,load(root,'reviewer'))
        elif name=='verifier_m':
            value=judge(root,name,judge_pool(frozen_handoff(root,pool_path),load(root,'verify_m')),settings['judge'])
            value['comparison']=compare(pool,load(root,'verify_m'),value)
        elif name=='builder':
            selected=load(root,'verifier_m')['comparison']['selected_candidate']
            if selected is None:value={'status':'NOT_RUN','verdict':'FAIL','reason':'No hard-eligible implementation'}
            else:
                source=root/'roles/reviewer/worktree' if selected=='M' else runtime.candidate_work(pool_path,selected)
                parent=load(root,'verify_m') if selected=='M' else next(c for c in pool['candidates'] if c['id']==selected)
                view={'selected_id':selected,'parent_commit':parent['head_commit'],'task_contract':pool['task_contract'],
                      'source_files':runtime.all_files(source),'visible_tests':runtime.run_tests(source,contract=pool.get('contract_manifest')),
                      'next_direction':settings['builder_direction'],'no_prior_chats_or_hidden_answers':True}
                prompt='Fresh independent Sol Builder. Directly redesign/implement this project, not merely score it. Meet the original task contract and the human direction; you may replace the design entirely. Preserve frozen protected files and dependencies. Add meaningful visible tests, run them and make a clean new Git commit. If no safe valid improvement can be committed, say so; no false success. No subagents/network/installs/prior chats.\n'+json.dumps(view,sort_keys=True)
                worker=runtime.role_run(root,name,'builder',view,prompt,source=source)
                value=runtime.verify_role(root,name,'S',parent['head_commit'],pool,worker);value['selected_parent']=selected
        elif name=='verifier_builder':
            builder=load(root,'builder')
            if builder.get('verdict')!='PASS':value={'status':'NOT_RUN','reason':'Builder not hard accepted'}
            else:
                from p2_candidates import failure_report
                row={k:builder.get(k,'unavailable') for k in ('id','kind','base_commit','head_commit','verdict','patch','source')}
                row.update(env_hash=pool['env_hash'],prompt_hash=pool['task_hash'],test_report=builder['visible_tests'])
                graded={k:pool[k] for k in ('task_contract','task_hash','env_hash','rubric','rubric_hash')}
                graded.update(base_commit=builder['base_commit'],candidates=[row],failure_report=failure_report([row]))
                graded['pool_hash']=digest(graded)
                value=judge(root,name,graded,settings['judge'])
        else:raise ValueError('Unknown stage')
    value=dict(value,stage=name,elapsed_stage_seconds=time.perf_counter()-tick)
    value['record_sha256']=digest(value);exclusive_json(path,value)
    return value
