"""Continue the frozen partial task only after its official mentor thread resumes."""
import json,sys
from pathlib import Path

def main(value):
    old=value['original'];sys.path[:0]=[old['folder'],old['folder']+'/src',value['folder']]
    import p6_guidance_linux as original
    from p6_guidance_shutdown import SOURCE_RUN,PARTIAL_TASK,MENTOR,SESSION_ID,allow_partial
    from pi_full_protocol import exclusive,digest
    original.bind(old);root=original.BASE/SOURCE_RUN;stages=root/PARTIAL_TASK/'control/stages'
    worker=dict(value['worker'])
    if worker['status']!='COMPLETED' or worker['session_id']!=SESSION_ID or not worker.get('original_session_resumed'):
        raise ValueError('Verified completion of the original interrupted mentor required')
    if not (stages/(MENTOR+'-model.started.json')).exists() or (stages/(MENTOR+'-model.completed.json')).exists():
        raise ValueError('Original interrupted marker is missing or already reconciled')
    setup=json.loads((stages/(MENTOR+'-setup.completed.json')).read_bytes())['value']
    if worker['work']!=setup['descriptor']['work'] or worker['input_sha256']!=setup['descriptor']['input_sha256']:
        raise ValueError('Resume changed original mentor input or readonly workspace')
    before=original.shared.program_evidence(worker['work'],next(t['base_commit'] for t in old['plan']['manifest']['tasks'] if t['task_id']==PARTIAL_TASK))
    initial=json.loads((stages/'initial-public.completed.json').read_bytes())['value']
    if before!=original.shared.program_evidence(Path(initial['root'])/'code',initial['base_commit']):raise ValueError('Read-only mentor changed its program')
    worker['resume_wall_seconds']=worker['wall_seconds']
    worker['pre_shutdown_seconds_bound']=worker['prior_role_seconds_debited']
    worker['wall_seconds']+=worker['prior_role_seconds_debited']
    exclusive(stages/(MENTOR+'-model.completed.json'),{'stage':MENTOR+'-model','value':worker,'value_sha256':digest(worker)})
    exclusive(root/PARTIAL_TASK/'control/shutdown-mentor-reconciliation.json',{
        'status':'ORIGINAL_OFFICIAL_SESSION_RESUMED','old_started_marker_preserved':True,'session_id':SESSION_ID,
        'resumed_worker_root':worker['root'],'completed_models_replayed':0,'prior_role_seconds_debited':worker['prior_role_seconds_debited']})
    saved=original.shared.launch
    def guarded(job,env):
        if not allow_partial(job):raise ValueError('Completed original role replay denied')
        return saved(job,env)
    original.shared.launch=guarded;old['key']=value['key']
    result=original.task_run(root,old,PARTIAL_TASK);result['interruption']='USER_SHUTDOWN_RESUMED_SAME_SESSION'
    exclusive(value['result'],result)
    return {'status':'ORIGINAL_PARTIAL_TASK_COMPLETED_WITHOUT_REPLAY'}

if __name__=='__main__':print(json.dumps(main(json.load(sys.stdin))))
