"""Zero-model independent replay, controlled failure pools and real process-watchdog test."""

from datetime import timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from p1_broker import protect_memory
from p1_fixture import SOURCE
from p2_candidates import BASE,validate_pool,digest,run_tests,safe_git,prepare,finalize,freeze,exclusive_json,candidate_env
from p2_judges import J0


def main():
    protect_memory();tick=time.perf_counter()
    ledger=BASE/'state/p2-budget/ledger.json';before=digest(ledger.read_bytes())
    verified=[];sessions=set();ns=[]
    for path in sorted((BASE/'runs').glob('p2-n*/frozen-pool.json')):
        pool=validate_pool(json.loads(path.read_text()))
        n=len(pool['candidates']);events=[]
        for c in pool['candidates']:
            work=path.parent/c['id']/'worktree'
            assert safe_git(work,'rev-parse','HEAD')==c['head_commit']
            assert safe_git(work,'status','--porcelain')==''
            assert run_tests(work,independent=True)['verdict']=='PASS'
            assert c['isolation']['verdict']=='PASS'
            assert c['session_id'] not in sessions;sessions.add(c['session_id'])
            ns.append(c['isolation']['proc_namespace'])
            events.extend([(c['timeline']['started_at_seconds'],1),(c['timeline']['completed_at_seconds'],-1)])
        active=peak=0
        for _,delta in sorted(events):active+=delta;peak=max(active,peak)
        assert peak==({1:1,3:3,4:2,5:5}[n])
        if n==4:assert max(c['queue_seconds'] for c in pool['candidates'])>1
        verified.append({'run_id':path.parent.name,'n':n,'pool_hash':pool['pool_hash'],'peak_concurrent_candidates':peak,
                         'verdict':'PASS','cache_replay':'validated frozen result; no model regeneration'})
    assert sorted(v['n'] for v in verified)==[1,3,4,5] and len(sessions)==13
    # Separate trusted fault fixtures. They are never labelled model-produced failures.
    original=json.loads(next((BASE/'runs').glob('p2-n3-*/frozen-pool.json')).read_text())
    controls=[]
    stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
    from p1_experiment_linux import git
    for name in ('mixed','all-failed','infrastructure'):
        root=BASE/'runs'/('p2-control-'+name+'-'+stamp)
        base,jobs=prepare(root,3);rows=[]
        for index,job in enumerate(jobs):
            work=Path(job['work']);source=original['candidates'][index]['source']
            if name=='all-failed' or (name=='mixed' and index>0):source=SOURCE
            (work/'weighted_stats.py').write_text(source)
            (work/'CONTROLLED_FIXTURE.txt').write_text('Program-created fault fixture; NOT a model result\n')
            git(work,'add','.');git(work,'commit','-m','Controlled P2 '+name+' fixture '+job['id'])
            worker={'kind':'CONTROLLED_FAULT_INJECTION','status':'INFRA_FAIL' if name=='infrastructure' else 'COMPLETED'}
            row=finalize(job,worker,{'kind':'CONTROLLED_FIXTURE'},0,original['env_hash'])
            rows.append(row)
            git(work,'bundle','create',str(root/(job['id']+'.bundle')),'--all')
        pool=freeze(root,rows,base,original['env_hash']);selection=J0().judge(pool)
        expected={'mixed':'PASS','all-failed':'FAIL','infrastructure':'INDETERMINATE'}[name]
        assert pool['failure_report']['status']==expected
        assert (selection['eligible_selected'] is not None)==(name=='mixed')
        controls.append({'run_id':root.name,'kind':'CONTROLLED_FAULT_INJECTION','pool_hash':pool['pool_hash'],
                         'expected':expected,'observed':pool['failure_report']['status'],'eligible_selected':selection['eligible_selected']})
    # Exercise the real scheduler's timeout against a namespace child, with no brokers or APIs.
    from hmz.sdk import Hmz
    root=BASE/'runs'/('p2-control-watchdog-'+stamp);root.mkdir()
    attempt=root/'A';attempt.mkdir();work=attempt/'worktree';work.mkdir()
    (work/'weighted_stats.py').write_text(SOURCE)
    job={'id':'A','root':str(attempt),'work':str(work),'scope':'CONTROLLED_WATCHDOG_ONLY',
         'capability':'NO_API_TRANSPORT','broker_url':'http://127.0.0.1:1','offline_control':'sleep'}
    descriptor=root/'descriptors.json';exclusive_json(descriptor,[job])
    result=Hmz(workspace=root).run('/opt/workbench/source/flows/ds_candidates','Offline watchdog test; zero model calls',agents={},
                  params={'descriptor_path':str(descriptor),'concurrency':1,'candidate_seconds':1},
                  budget={'duration':timedelta(seconds=20),'graceful':False}).run()
    timed=result['candidates'][0]
    assert timed['worker']['status']=='TIMEOUT'
    assert timed['timeline']['candidate_wall_seconds']<8
    after=digest(ledger.read_bytes());assert before==after,'Offline replay changed real spending ledger'
    report={'verdict':'PASS','kind':'ZERO_MODEL_INDEPENDENT_VERIFICATION','real_pools_replayed':verified,
            'real_sessions':len(sessions),'controlled_failures':controls,'watchdog':timed,
            'real_ledger_sha256_before':before,'real_ledger_sha256_after':after,'model_requests_added':0,
            'elapsed_seconds':time.perf_counter()-tick}
    exclusive_json(BASE/'evidence'/('p2-independent-'+stamp+'.json'),report)
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
