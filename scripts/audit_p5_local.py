"""Preserve local P5 delivery evidence; blocked inference never becomes phase PASS."""
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from workbench.memory import Memory,sha
from workbench.gitops import GitOps,git,restore

def main():
    tick=time.perf_counter();memory=Memory(ROOT/'.local-workbench/workbench');ops=GitOps(memory)
    audit=memory.verify();before=git(ROOT,'rev-parse','HEAD')
    nodes=[n for n in memory.list('attempt') if (n.get('run_id') or '').startswith('p5-') and n.get('role')!='checkpoint']
    forks=[]
    for node in nodes:
        if len(node.get('recovery_sha',node.get('head_sha','')))!=40:continue
        saved=ops.fork(node['id'],'P5 independent recovery audit; no agent executed','controller')
        expected=node.get('recovery_sha',node['head_sha']);assert saved['head_sha']==expected
        forks.append({'node':node['id'],'head_sha':expected,'branch':saved['branch'],'worktree':saved['worktree']})
    assert git(ROOT,'rev-parse','HEAD')==before
    backup=ops.export();target=memory.root/'restores'/('p5-'+str(time.time_ns()));target.parent.mkdir(exist_ok=True)
    recovered,repository=restore(backup['path'],target)
    assert recovered.verify()['tail_hash']==memory.verify()['tail_hash']
    for node in nodes:
        head=node.get('recovery_sha',node.get('head_sha'))
        if head:assert git(repository,'rev-parse',head)==head
    controls=json.loads((ROOT/'.local-workbench/audits/p5-controls.json').read_text())
    offline=json.loads((ROOT/'.local-workbench/audits/p5-offline.json').read_text())
    assert controls['verdict']==offline['verdict']=='PASS'
    ledger=memory.get('project_contract','p5-ledger')
    runs=[r for r in memory.list('run') if r.get('phase')=='P5']
    complete=any(r['status']=='COMPLETED' and r.get('native',{}).get('task_verdict')=='PASS' for r in runs)
    value={'phase':'P5','functional_gate':'LIVE_CHAIN_PRESENT_REQUIRES_BROWSER_REVIEW' if complete else 'PARTIAL_BLOCKED_EXTERNAL_CODEX_QUOTA',
           'local_recovery_backup_gate':'PASS','remote_delivery':'DEFERRED_BY_USER','github_mutations':0,
           'new_model_requests':0,'new_subscription_turns':0,'api_cash_usd':0,'elapsed_seconds':time.perf_counter()-tick,
           'pre_audit':audit,'after_audit':memory.verify(),'forks':forks,'original_head_unchanged':git(ROOT,'rev-parse','HEAD')==before,
           'backup':backup,'restored_path':str(target),'ledger':ledger,'run_ids':[r['id'] for r in runs],
           'offline_evidence_sha256':sha((ROOT/'.local-workbench/audits/p5-offline.json').read_bytes()),
           'native_control_sha256':sha((ROOT/'.local-workbench/audits/p5-controls.json').read_bytes()),
           'p6_started':False}
    target=ROOT/'.local-workbench/audits/p5-local.json';target.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:value[k] for k in ('functional_gate','local_recovery_backup_gate','remote_delivery','elapsed_seconds','original_head_unchanged','backup')}))

if __name__=='__main__':main()
