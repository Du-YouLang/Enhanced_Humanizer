"""Independent zero-model recovery of actual accepted history, without executing code on Windows."""
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'src'))
from workbench.memory import Memory,canonical,sha,uid
from workbench.gitops import GitOps,git,restore
from wsl_project import run


def main():
    tick=time.perf_counter();memory=Memory(ROOT/'.local-workbench/workbench');ops=GitOps(memory)
    original=git(ROOT,'rev-parse','HEAD');nodes=[a for a in memory.list('attempt') if a.get('run_id','').startswith('p3-')]
    recovered=[]
    for node in nodes:
        fork=ops.fork(node['id'],'P4 independent legal historical node recovery','controller')
        expected=node.get('recovery_sha',node['head_sha'])
        assert git(Path(fork['worktree']),'rev-parse','HEAD')==expected
        recovered.append({'node':node['id'],'status':node['status'],'commit':expected,'branch':fork['branch']})
    assert git(ROOT,'rev-parse','HEAD')==original
    tests=[]
    for node in nodes:
        if not node.get('linux_worktree') or not (node['status'] in ('FAIL','BUDGET_EXHAUSTED') or node['role']=='reviewer'):continue
        if 'ds-return' in node['run_id']:
            code="import json;from pathlib import Path;print(json.dumps(json.loads(Path('/opt/workbench/runs/"+node['run_id']+"/frozen-pool.json').read_text())['contract_manifest']['acceptance_test_program']))"
        else:
            code="import json;from pathlib import Path;c=json.loads(Path('/opt/workbench/runs/"+node['run_id']+"/control/run-contract.json').read_text());p=json.loads(Path(c['pool_path']).read_text());print(json.dumps(p.get('contract_manifest',{}).get('acceptance_test_program')))"
        p=run(['python','-c',code]);program=json.loads(p.stdout)
        if program is None:
            from p1_fixture import TESTS
            program=TESTS+'\nunittest.main(verbosity=2)\n'
        value=ops.verify(node['id'],program)
        expected='FAIL' if node['status'] in ('FAIL','REFUSED') else 'PASS'
        assert value['verdict']==expected,(node['id'],value['verdict'],expected)
        tests.append({'node':node['id'],'execution_status':node['status'],'frozen_verdict':value['verdict']})
    partial=next(n for n in nodes if n['status']=='BUDGET_EXHAUSTED')
    package=memory.handoff(partial['id'],'builder','Resume preserved partial snapshot without claiming model success')
    assert package['current_commit']==partial['recovery_sha'] and not package['raw_chats_included']
    for state in ('fact','hypothesis','rejected','superseded','unresolved'):
        memory.record('knowledge','p4-state-'+state,{'task_id':partial['task_id'],'state':state,'text':'Explicit '+state+' memory state demonstration','evidence_refs':[]})
    before=memory.verify();backup=ops.export();target=memory.root/'restores'/uid('restore');target.parent.mkdir(exist_ok=True)
    other,repo=restore(backup['path'],target);other.rebuild();after=other.verify()
    assert before==after
    assert set(git(ROOT,'for-each-ref','--format=%(objectname) %(refname)','refs/heads').splitlines())==set(git(repo,'for-each-ref','--format=%(objectname) %(refname)','refs/heads').splitlines())
    assert GitOps(other,repo).fork(partial['id'],'Fork failed partial after fresh backup restore')['head_sha']==partial['recovery_sha']
    report={'phase':'P4','functional_gate':'PASS','kind':'ACTUAL_HISTORY_ZERO_MODEL_RECOVERY','legal_nodes_recovered':len(recovered),
            'recovered':recovered,'frozen_failure_and_reviewer_replays':tests,'backup':backup,'restored_state':str(target),
            'audit':before,'main_unchanged':True,'model_requests_added':0,'api_cash_usd':0,'subscription_turns_added':0,
            'elapsed_seconds':time.perf_counter()-tick,'limitations':['Backup covers events/artifacts/Git refs, not WSL OS or credentials','Synthetic history is not scientific efficacy evidence']}
    (ROOT/'.local-workbench/audits/p4-functional.json').write_bytes(canonical(report))
    public={k:v for k,v in report.items() if k not in ('backup','restored_state')}
    public['backup_sha256']=backup['sha256'];public['private_details']='.local-workbench/audits/p4-functional.json'
    (ROOT/'docs/audits/P4-evidence-2026-10-10.json').write_text(json.dumps(public,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('recovered','frozen_failure_and_reviewer_replays')},ensure_ascii=False))


if __name__=='__main__':main()
