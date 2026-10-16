"""Finish only the one unpaid role of the stopped original task; no replay."""
import fcntl,hashlib,json,sys
from pathlib import Path


def main(value):
    # Import the original executor in an independent interpreter so none of its
    # task/permission/driver modules can resolve to the corrected successor.
    old=value['original_payload'];folder=old['folder']
    sys.path[:0]=[folder,folder+'/src']
    from p1_broker import protect_memory
    protect_memory()
    import p6_guidance_linux as original
    from pi_full_protocol import exclusive,digest
    original.bind(old)
    root=original.BASE/old['run_id'];tid='SWEL-pytest-dev__pytest-11148'
    stages=root/tid/'control/stages'
    model_names=('initial','code-tests-trace-mentor','code-tests-mentor','code-tests-trace-ds')
    if any(not (stages/(n+'-model.completed.json')).exists() for n in model_names):raise ValueError('Original four completed model stages required')
    if (stages/'code-tests-ds-model.started.json').exists():raise ValueError('Remaining role already started; reconcile, never replay')
    current=json.loads(original.LEDGER.read_bytes());scope='GUIDANCE/'+old['run_id']+'/'+tid+'/code-tests-ds'
    if any(r['experiment']==scope for r in current['requests']+current['codex_turns']):raise ValueError('Unpaid suffix already reserved')
    saved_launch=original.shared.launch
    def guarded(job,env):
        if job['scope']!=scope or job['backend']!='dsh' or job['role']!='builder':raise ValueError('Completed role replay denied')
        return saved_launch(job,env)
    original.shared.launch=guarded
    # The interrupted stage was a public test, after a completed paid role.
    # Retain its start marker and add an independently bound completion receipt.
    name='code-tests-trace-ds-public';done=stages/(name+'.completed.json')
    if not done.exists():
        tp,task,tester=original.make_task(old,tid)
        with task['fixture_context'] as url:
            original.activate(root/tid,old,tp,task,tester,url)
            worker=json.loads((stages/'code-tests-trace-ds-model.completed.json').read_bytes())['value']
            cpath=Path(worker['root'])/'candidate-private.json'
            if cpath.exists():
                c=json.loads(cpath.read_bytes());original.verify(c,original.freeze(c))
            else:
                bundle=Path(worker['root'])/'git-tmp/candidate.bundle'
                if bundle.exists():raise ValueError('Orphan candidate bundle requires reconciliation; preserved')
                c=original.shared.candidate('code-tests-trace-ds',worker)
            exclusive(done,{'stage':name,'value':c,'value_sha256':digest(c)})
            exclusive(root/tid/'control/helper-stop-public-reconciliation.json',{
                'status':'APPENDED_NONMODEL_PUBLIC_COMPLETION','model_replays':0,
                'original_start_sha256':hashlib.sha256((stages/(name+'.started.json')).read_bytes()).hexdigest(),
                'completed_sha256':hashlib.sha256(done.read_bytes()).hexdigest(),
                'public_infrastructure_error_preserved':True})
    old['key']=value['key']
    result=original.task_run(root,old,tid)
    target=Path(value['result_path']);exclusive(target,result)
    return {'status':'ORIGINAL_PARTIAL_TASK_CLOSED_WITHOUT_MODEL_REPLAY','result':str(target)}


if __name__=='__main__':print(json.dumps(main(json.load(sys.stdin))))
