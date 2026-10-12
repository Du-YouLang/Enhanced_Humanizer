"""Real filesystem/Git and adversarial memory/review checks, no model calls."""
import concurrent.futures
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from workbench.memory import Memory,sha
from workbench.gitops import GitOps,git,restore
from workbench.review import Reviews


class TestMemory(unittest.TestCase):
    def setUp(self):
        folder=ROOT/'.local-workbench/test-tmp';folder.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=folder);self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.m=Memory(self.root/'state')

    def node(self,head='a'*40):
        self.m.record('task','task',{'contract':{'prompt':'original task'}})
        self.m.record('attempt','node',{'task_id':'task','role':'builder','status':'PASS','head_sha':head,'base_sha':head,
                       'contract':{'prompt':'current task'},'artifacts':{}})
        self.m.record('test_result','fixture-test',{'task_id':'task','attempt_id':'node','verdict':'PASS','kind':'TEST_FIXTURE'})

    def test_fresh_writer_lock_serializes_independent_processes(self):
        shared=self.root/'new-shared-state'
        code='import sys;sys.path.insert(0,sys.argv[1]);from workbench.memory import Memory;m=Memory(sys.argv[2]);' \
             '[m.record("task",sys.argv[3]+"-"+str(i),{"value":i}) for i in range(3)]'
        children=[subprocess.Popen([sys.executable,'-c',code,str(ROOT/'src'),str(shared),str(i)],stdout=subprocess.PIPE,stderr=subprocess.PIPE) for i in range(4)]
        outcomes=[(child.returncode,error) for child in children for _,error in [child.communicate(timeout=30)]]
        for code,error in outcomes:self.assertEqual(code,0,error.decode(errors='replace'))
        m=Memory(shared)
        self.assertEqual(m.verify()['events'],12)
        self.assertEqual(len(m.list('task')),12)

    def test_journal_replays_after_projection_loss_and_retains_epistemic_history(self):
        for state in ('hypothesis','fact','rejected','superseded','unresolved'):
            self.m.record('knowledge','k',{'state':state,'text':state})
        with self.m.connect() as db:
            db.execute('DELETE FROM execution_event');db.execute('DELETE FROM knowledge')
        restarted=Memory(self.m.root)
        self.assertEqual(restarted.verify()['events'],5)
        self.assertEqual([v['data']['state'] for v in restarted.events()],['hypothesis','fact','rejected','superseded','unresolved'])

    def test_tamper_and_torn_tail_fail_closed_without_erasing_evidence(self):
        self.m.record('task','t',{'value':1})
        with self.m.connect() as db:db.execute("UPDATE task SET body='{}'")
        with self.assertRaises(ValueError):self.m.verify()
        self.m.rebuild();self.assertEqual(self.m.get('task','t')['value'],1)
        with self.m.journal.open('ab') as file:file.write(b'{torn')
        before=self.m.journal.read_bytes()
        with self.assertRaises(ValueError):Memory(self.m.root)
        self.assertEqual(before,self.m.journal.read_bytes())

    def test_secrets_paths_and_artifact_tampering(self):
        with self.assertRaises(ValueError):self.m.artifact('sk-'+'a'*24)
        self.assertEqual(len(self.m.events()),0)
        with self.assertRaises(ValueError):Memory(self.root/'..'/'..'/'..'/'..'/'outside')
        identifier=self.m.artifact('immutable','test','human')
        with self.assertRaises(PermissionError):self.m.read_artifact(identifier,'agent')
        with self.assertRaises(ValueError):self.m.artifact('immutable','test','agent')
        (self.m.artifacts/identifier).write_bytes(b'changed')
        with self.assertRaises(ValueError):self.m.verify()

    def test_handoff_uses_current_contract_and_excludes_hidden_answers(self):
        self.node();hidden=self.m.artifact('HIDDEN_GOLD_ANSWER','test','human')
        visible=self.m.artifact('visible source','source','agent')
        self.m.record('test_result','test',{'task_id':'task','artifact':hidden,'hidden_test_artifact':hidden,'verdict':'PASS'})
        self.m.record('knowledge','k',{'task_id':'task','state':'fact','text':'test passed','evidence_refs':[hidden,visible]})
        package=self.m.handoff('node','reviewer','continue')
        self.assertEqual(package['task_contract']['prompt'],'current task')
        self.assertNotIn(hidden,json.dumps(package));self.assertFalse(package['raw_chats_included'])

    def test_product_review_is_exact_head_once_and_not_actor_claim(self):
        self.node();gate=Reviews(self.m,'fixture-human-capability')
        intent=gate.intent('node',{'repository':'fixture','base':'main'},'review me')
        with self.assertRaises(PermissionError):gate.consume(intent['id'],'a'*40,intent['target'],intent['evidence_hash'])
        with self.assertRaises(PermissionError):gate.approve(intent['id'],'agent','a'*40,'claimed human')
        with self.assertRaises(ValueError):gate.approve(intent['id'],'fixture-human-capability','b'*40,'wrong head')
        gate.approve(intent['id'],'fixture-human-capability','a'*40,'fixture approval, not a real user decision')
        def consume(_):
            try:gate.consume(intent['id'],'a'*40,intent['target'],intent['evidence_hash']);return True
            except PermissionError:return False
        with concurrent.futures.ThreadPoolExecutor(4) as pool:self.assertEqual(sum(pool.map(consume,range(4))),1)
        fresh=gate.intent('node',intent['target'],'changed evidence')
        gate.approve(fresh['id'],'fixture-human-capability','a'*40,'fixture')
        node=self.m.get('attempt','node');node['artifacts']={'new':'evidence'};self.m.record('attempt','node',node)
        with self.assertRaises(PermissionError):gate.consume(fresh['id'],'a'*40,fresh['target'],fresh['evidence_hash'])

    def test_git_fork_dirty_snapshot_revert_and_private_backup_restore(self):
        repo=self.root/'repository';repo.mkdir();git(repo,'init','-b','main')
        git(repo,'config','user.name','Memory Test');git(repo,'config','user.email','fixture@example.invalid')
        (repo/'source.txt').write_text('base');git(repo,'add','.');git(repo,'commit','-m','base')
        base=git(repo,'rev-parse','HEAD');self.node(base);ops=GitOps(self.m,repo)
        fork=ops.fork('node','historical fork');work=Path(fork['worktree'])
        self.assertEqual(self.m.handoff(fork['id'],'builder','continue')['task_contract']['prompt'],'current task')
        (work/'source.txt').write_text('committed');git(work,'add','.');git(work,'commit','-m','change')
        changed=git(work,'rev-parse','HEAD');(work/'source.txt').write_text('dirty partial')
        snap=ops.snapshot(fork['id'],'preserve partial')
        self.assertEqual(git(repo,'rev-parse',snap['head_sha']+'^'),changed)
        self.assertEqual((Path(snap['worktree'])/'source.txt').read_text(),'dirty partial')
        self.assertEqual((work/'source.txt').read_text(),'dirty partial')
        reverted=ops.revert(snap['id'],snap['head_sha'],'rollback new branch')
        self.assertEqual(reverted['status'],'REVERTED')
        self.assertEqual((Path(reverted['worktree'])/'source.txt').read_text(),'committed')
        self.assertEqual(git(repo,'rev-parse','HEAD'),base)
        self.m.artifact('full trace','trace','human')
        git(repo,'switch','-c','feature/fixture-source',changed)
        backup=ops.export();restored,restored_repo=restore(backup['path'],self.root/'restored')
        self.assertEqual(git(restored_repo,'rev-parse','HEAD'),changed)
        self.assertEqual(git(restored_repo,'rev-parse','--abbrev-ref','HEAD'),'feature/fixture-source')
        self.assertEqual(self.m.verify()['tail_hash'],restored.verify()['tail_hash'])
        self.assertEqual(git(restored_repo,'rev-parse',snap['head_sha']),snap['head_sha'])
        self.assertEqual(GitOps(restored,restored_repo).fork('node','after restore')['head_sha'],base)
        with self.assertRaises(ValueError):restore(backup['path'],self.root/'restored')
        bad=self.root/'bad.zip'
        with zipfile.ZipFile(bad,'w') as output:
            output.writestr('manifest.json',json.dumps({'files':{'../escape':sha(b'bad')}}));output.writestr('../escape','bad')
        with self.assertRaises(ValueError):restore(bad,self.root/'bad-restore')

    def test_partial_linux_files_are_preserved_without_changing_failure_or_executing(self):
        repo=self.root/'repository';repo.mkdir();git(repo,'init','-b','main')
        git(repo,'config','user.name','Memory Test');git(repo,'config','user.email','fixture@example.invalid')
        (repo/'code.py').write_text('raise RuntimeError("MUST NOT RUN")\n');git(repo,'add','.');git(repo,'commit','-m','base')
        base=git(repo,'rev-parse','HEAD');self.node(base)
        node=self.m.get('attempt','node');self.m.record('attempt','node',node|{'status':'CANCELLED'})
        ops=GitOps(self.m,repo);before=len(self.m.events())
        for name in ('../escape','.git/config','C:/outside','.'):
            with self.assertRaises(ValueError):ops.preserve_partial('node',{name:'bad'})
        self.assertEqual(len(self.m.events()),before)
        saved=ops.preserve_partial('node',{'code.py':'raise RuntimeError("PARTIAL NOT RUN")\n','new.txt':'partial'})
        self.assertEqual(saved['status'],'CANCELLED');self.assertNotEqual(saved['recovery_sha'],base)
        fork=ops.fork('node','recover failed partial')
        self.assertIn('PARTIAL NOT RUN',(Path(fork['worktree'])/'code.py').read_text())
        self.assertEqual((Path(fork['worktree'])/'new.txt').read_text(),'partial')
        self.assertEqual(git(repo,'rev-parse','HEAD'),base)
        self.assertEqual(ops.preserve_partial('node',{'code.py':'raise RuntimeError("PARTIAL NOT RUN")\n','new.txt':'partial'})['recovery_sha'],saved['recovery_sha'])


if __name__=='__main__':unittest.main()
