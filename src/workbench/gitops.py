"""Non-destructive Git checkpoints and branches; never reset, force-push or delete history."""

import json
from pathlib import Path
import re
import subprocess
import time
import zipfile

from .memory import ROOT,Memory,canonical,local,now,sha,uid


def git(repo,*args):
    argv=['git','-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false','-c','core.pager=cat',
          '-c','diff.external=','-c','core.askPass=',*args]
    result=subprocess.run(argv,cwd=repo,capture_output=True,text=True,encoding='utf-8',timeout=60)
    if result.returncode:raise ValueError('Git operation failed: '+result.stderr.strip()[:1000])
    return result.stdout.strip()


class GitOps:
    def __init__(self,memory,repository=ROOT):
        self.memory=memory;self.repository=local(repository,memory.boundary)
        self.worktrees=memory.root/'worktrees';self.worktrees.mkdir(exist_ok=True)

    def commit(self,value):
        if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{40}',value):raise ValueError('Exact saved commit required')
        if git(self.repository,'rev-parse','--verify',value+'^{commit}')!=value:raise ValueError('Saved commit is unavailable')
        return value

    def fork(self,node_id,reason,actor='human'):
        node=self.memory.get('attempt',node_id);commit=self.commit(node.get('recovery_sha',node.get('head_sha')))
        identity=uid('fork');branch='workbench/'+identity;path=local(self.worktrees/identity,self.memory.root)
        before=git(self.repository,'rev-parse','HEAD')
        git(self.repository,'worktree','add','-b',branch,str(path),commit)
        value={'task_id':node['task_id'],'parent_node':node_id,'role':'checkpoint','status':'READY',
               'head_sha':commit,'base_sha':commit,'branch':branch,'worktree':str(path),'reason':reason,
               'model_id':'not_applicable','harness':'Git checkpoint; no agent executed','artifacts':{},'created_at':now()}
        self.memory.record('attempt',identity,value,actor)
        self.memory.record('checkpoint',uid('checkpoint'),value|{'attempt_id':identity,'immutable_parent':commit},actor)
        assert git(self.repository,'rev-parse','HEAD')==before
        return value|{'id':identity}

    def snapshot(self,node_id,reason):
        node=self.memory.get('attempt',node_id);work=local(node['worktree'],self.worktrees)
        files={}
        for name in git(self.repository,'-C',str(work),'ls-files','--cached','--others','--exclude-standard').splitlines():
            path=local(work/name,work)
            if path.is_symlink() or not path.is_file() or path.stat().st_size>5_000_000:raise ValueError('Snapshot needs regular bounded project files')
            files[name]=path.read_bytes()
        # Snapshot in a new worktree, preserving the user's dirty original unchanged.
        actual=git(self.repository,'-C',str(work),'rev-parse','HEAD')
        checkpoint=uid('dirty-parent')
        self.memory.record('attempt',checkpoint,node|{'head_sha':actual,'recovery_sha':actual,'parents':[node_id],'status':'CHECKPOINT'})
        saved=self.fork(checkpoint,reason,'controller');target=Path(saved['worktree'])
        for name,data in files.items():
            path=local(target/name,target);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        tracked=git(self.repository,'-C',str(target),'ls-files').splitlines()
        for name in tracked:
            if name not in files:(target/name).unlink()
        git(self.repository,'-C',str(target),'add','--all')
        git(self.repository,'-C',str(target),'-c','user.name=Workbench Snapshot','-c','user.email=local@example.invalid',
            'commit','--allow-empty','-m','Program snapshot of partial work; not a model-success result')
        saved.update(head_sha=git(self.repository,'-C',str(target),'rev-parse','HEAD'),kind='PROGRAM_PARTIAL_SNAPSHOT',status='PRESERVED')
        self.memory.record('attempt',saved['id'],saved)
        return saved

    def revert(self,node_id,target_sha,reason):
        target_sha=self.commit(target_sha);saved=self.fork(node_id,reason)
        work=Path(saved['worktree'])
        try:
            git(self.repository,'-C',str(work),'-c','user.name=Workbench Revert','-c','user.email=local@example.invalid','revert','--no-edit',target_sha)
            saved.update(status='REVERTED',head_sha=git(self.repository,'-C',str(work),'rev-parse','HEAD'))
        except ValueError as error:saved.update(status='CONFLICT',diagnostic=str(error))
        self.memory.record('attempt',saved['id'],saved)
        return saved

    def diff(self,node_id):
        node=self.memory.get('attempt',node_id)
        base=self.commit(node['base_sha']);head=self.commit(node.get('recovery_sha',node['head_sha']))
        return git(self.repository,'diff','--no-ext-diff','--no-textconv',base,head,'--')

    def verify(self,node_id,program):
        """Run candidate imports only through the existing non-root Linux fence, never Windows."""
        import sys
        sys.path.insert(0,str(ROOT/'scripts'))
        from wsl_project import run
        node=self.memory.get('attempt',node_id)
        if not node.get('linux_worktree'):raise ValueError('No frozen Linux environment prepared for this node; fork does not execute code')
        work=node['linux_worktree']
        if not work.startswith('/opt/workbench/runs/'):raise ValueError('Only registered project Linux attempts can be verified')
        code='''import json,sys,subprocess
from p2_candidates import namespace_command
from p1_acceptance import verification_command
value=json.load(sys.stdin)
p=subprocess.run(namespace_command(verification_command(value['work'],[sys.executable,'-B','-c',value['program']],value['work']+'/../p4-verify')),cwd=value['work'],capture_output=True,text=True,timeout=20)
print(json.dumps({'verdict':'PASS' if p.returncode==0 else 'FAIL','exit_code':p.returncode,'log':p.stdout+p.stderr}))
'''
        tick=time.perf_counter()
        result=run(['/usr/bin/env','PYTHONPATH=/opt/workbench/source','python','-c',code],input_bytes=canonical({'work':work,'program':program}),timeout=30)
        if result.returncode:raise ValueError('Isolated verifier unavailable')
        value=json.loads(result.stdout);artifact=self.memory.artifact(canonical(value),'frozen-test','human')
        self.memory.record('test_result',uid('test'),{'task_id':node['task_id'],'attempt_id':node_id,'suite_sha256':sha(program.encode()),
                    'verdict':value['verdict'],'exit_code':value['exit_code'],'artifact':artifact,'elapsed_seconds':time.perf_counter()-tick})
        return value

    def export(self):
        folder=self.memory.root/'exports';folder.mkdir(exist_ok=True)
        stamp=uid('backup');bundle=folder/(stamp+'.bundle');archive=folder/(stamp+'.zip')
        git(self.repository,'bundle','create',str(bundle),'--all')
        git(self.repository,'bundle','verify',str(bundle))
        with self.memory.lock():
            audit=self.memory.verify()
            files={'events.ndjson':self.memory.journal.read_bytes(),'history.bundle':bundle.read_bytes()}
            files.update({'artifacts/'+a['id']:self.memory.read_artifact(a['id']) for a in self.memory.list('artifact')})
            manifest={'schema_version':1,'created_at':now(),'private_local_backup':True,'audit':audit,
                      'files':{name:sha(data) for name,data in files.items()}}
            with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as output:
                output.writestr('manifest.json',canonical(manifest))
                for name,data in files.items():output.writestr(name,data)
        return {'path':str(archive),'sha256':sha(archive.read_bytes()),'files':len(files),'private_local_backup':True}


def restore(archive,destination,boundary=ROOT):
    archive=local(archive,boundary);destination=local(destination,boundary)
    if destination.exists():raise ValueError('Restore requires a new path; existing history is preserved')
    with zipfile.ZipFile(archive) as source:
        names=source.namelist()
        if len(names)!=len(set(names)) or sum(i.file_size for i in source.infolist())>250_000_000:raise ValueError('Unsafe archive size/duplicates')
        manifest=json.loads(source.read('manifest.json'))
        if set(names)!=set(manifest['files'])|{'manifest.json'}:raise ValueError('Backup manifest/file coverage differs')
        files={}
        for name,digest in manifest['files'].items():
            local(destination/name,destination)
            if name not in ('events.ndjson','history.bundle') and not re.fullmatch('artifacts/[0-9a-f]{64}',name):raise ValueError('Unexpected backup path')
            data=source.read(name)
            if sha(data)!=digest:raise ValueError('Backup integrity failed')
            files[name]=data
        destination.mkdir()
        for name,data in files.items():
            path=destination/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    memory=Memory(destination,boundary);memory.verify()
    repo=destination/'repository';git(destination,'init',str(repo))
    git(repo,'fetch',str(destination/'history.bundle'),'refs/heads/*:refs/heads/*')
    git(repo,'bundle','verify',str(destination/'history.bundle'))
    branches=git(repo,'for-each-ref','--format=%(refname:short)','refs/heads/').splitlines()
    git(repo,'checkout','main' if 'main' in branches else branches[0])
    return memory,repo
