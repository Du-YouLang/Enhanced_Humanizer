"""Real local Git checks; remote API/approval fixtures are not live acceptance."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from workbench.memory import Memory
from workbench.gitops import GitOps,git
from workbench.review import Reviews
from workbench.publish import Publisher


class RemoteFixture:
    login='FixtureOwner'
    private=False
    can_push=True
    def __init__(self,base):self.base=base;self.created=[];self.fail=False
    def identity(self):return self.login
    def metadata(self,repo,base):return {'repository':repo,'private':self.private,'can_push':self.can_push,'base_head_sha':self.base}
    def fetch(self,repo,base):return self.base
    def scan(self,base,head):return {'scanner':'TEST_FIXTURE_NO_LIVE_SCANNER','verdict':'PASS','range':base+'..'+head}
    def create(self,target,head,branch,title,body):
        self.created.append((target,head,branch))
        if self.fail:raise RuntimeError('TEST_FIXTURE_AMBIGUOUS_REMOTE_OUTCOME')
        return 'https://github.com/FixtureOwner/fixture/pull/1'


class PublishTests(unittest.TestCase):
    def setUp(self):
        root=ROOT/'.local-workbench/test-tmp';root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root);self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.repo=self.root/'repo';self.repo.mkdir()
        subprocess.run(['git','init',str(self.repo)],capture_output=True,check=True)
        git(self.repo,'config','user.name','Fixture');git(self.repo,'config','user.email','fixture@example.invalid')
        (self.repo/'README.md').write_text('Fixture base\n');self.commit()
        self.base=git(self.repo,'rev-parse','HEAD')
        (self.repo/'change.py').write_text('VALUE = 2\n');self.commit();self.head=git(self.repo,'rev-parse','HEAD')
        self.memory=Memory(self.root/'memory')
        self.memory.record('task','fixture',{'contract':{'prompt':'TEST_ONLY'}})
        self.memory.record('attempt','node',{'task_id':'fixture','role':'builder','status':'PASS','head_sha':self.head,'base_sha':self.base,'artifacts':{}})
        self.memory.record('test_result','test',{'task_id':'fixture','attempt_id':'node','verdict':'PASS','kind':'TEST_FIXTURE'})
        self.reviews=Reviews(self.memory,'FIXTURE_REVIEW_KEY_NOT_A_REAL_HUMAN_APPROVAL')
        self.remote=RemoteFixture(self.base);self.approval=self.root/'approval.json'
        self.approval.write_text(json.dumps({'approved_by':'human_user','authorization_reference':'TEST_FIXTURE_ONLY',
           'owner':'FixtureOwner','repository':'fixture','visibility':'PUBLIC','allowed_ref_prefixes':['refs/heads/codex/']}))
        self.publisher=Publisher(self.memory,GitOps(self.memory,self.repo),self.reviews,self.approval,self.remote)

    def commit(self):
        git(self.repo,'add','--all');git(self.repo,'commit','-m','TEST FIXTURE')

    def approved(self):
        value=self.publisher.prepare('node','TEST FIXTURE: reviewable change')
        self.reviews.approve(value['id'],'FIXTURE_REVIEW_KEY_NOT_A_REAL_HUMAN_APPROVAL',self.head,'TEST FIXTURE ONLY')
        return value

    def test_no_upload_before_review_and_approved_head_is_used_only_once(self):
        intent=self.publisher.prepare('node','TEST FIXTURE ONLY')
        with self.assertRaises(PermissionError):self.publisher.publish(intent['id'])
        self.assertEqual(self.remote.created,[])
        self.reviews.approve(intent['id'],'FIXTURE_REVIEW_KEY_NOT_A_REAL_HUMAN_APPROVAL',self.head,'TEST FIXTURE ONLY')
        result=self.publisher.publish(intent['id'])
        self.assertEqual(self.remote.created[0][1],self.head)
        self.assertTrue(self.remote.created[0][2].startswith('codex/product-pr-'))
        self.assertEqual(result['status'],'DRAFT_PR_CREATED_AWAITING_CI_AND_GITHUB_HUMAN_REVIEW')
        with self.assertRaises(PermissionError):self.publisher.publish(intent['id'])
        self.assertEqual(len(self.remote.created),1)

    def test_wrong_account_visibility_target_or_advanced_base_prevents_upload(self):
        intent=self.approved()
        for attr,value in [('login','OtherOwner'),('private',True),('can_push',False),('base',self.head)]:
            before=getattr(self.remote,attr);setattr(self.remote,attr,value)
            with self.assertRaises((PermissionError,ValueError)):self.publisher.publish(intent['id'])
            setattr(self.remote,attr,before)
        with self.assertRaises(PermissionError):self.publisher.prepare('node','fixture',{'repository':'Other/repo','base':'main'})
        self.assertEqual(self.remote.created,[])

    def test_hidden_file_in_intermediate_history_is_rejected_even_if_deleted(self):
        hidden=self.repo/'.local-workbench/private.txt';hidden.parent.mkdir();hidden.write_text('TEST PRIVATE MATERIAL')
        self.commit();hidden.unlink();self.commit()
        node=self.memory.get('attempt','node');node['head_sha']=git(self.repo,'rev-parse','HEAD');self.memory.record('attempt','node',node)
        with self.assertRaises(ValueError):self.publisher.prepare('node','fixture')
        self.assertEqual(self.remote.created,[])

    def test_changed_test_evidence_or_artifact_blocks_previous_approval(self):
        intent=self.approved()
        self.memory.record('test_result','later',{'task_id':'fixture','attempt_id':'node','verdict':'FAIL','kind':'TEST_FIXTURE'})
        with self.assertRaises(ValueError):self.publisher.publish(intent['id'])
        self.assertEqual(self.remote.created,[])

    def test_tabular_research_output_requires_a_separate_distribution_review(self):
        (self.repo/'measurements.csv').write_text('subject,value\nTEST,1\n');self.commit()
        node=self.memory.get('attempt','node');node['head_sha']=git(self.repo,'rev-parse','HEAD');self.memory.record('attempt','node',node)
        with self.assertRaises(ValueError):self.publisher.prepare('node','fixture')
        self.assertEqual(self.remote.created,[])

    def test_ambiguous_external_failure_consumes_approval_without_replay(self):
        intent=self.approved();self.remote.fail=True
        with self.assertRaises(RuntimeError):self.publisher.publish(intent['id'])
        self.assertEqual(self.memory.get('action',intent['id'])['status'],'PUBLISH_UNCERTAIN_RECONCILE_BEFORE_NEW_REVIEW')
        with self.assertRaises(PermissionError):self.publisher.publish(intent['id'])
        self.assertEqual(len(self.remote.created),1)


if __name__=='__main__':unittest.main()
