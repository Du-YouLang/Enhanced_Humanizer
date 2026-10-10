"""Owner HTTP boundary and real backend actions; fixture review approvals only."""
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from workbench.memory import Memory
from workbench.server import WorkbenchServer
from workbench.execution import settings


class FakeExecution:
    running=None
    limits={'api_cash_usd':5}
    def start(self,value,contract=None):return {'kind':'TEST_ONLY_NO_MODEL','settings':settings(value)}
    def request(self,run,action):return {'kind':'TEST_ONLY_NO_MODEL','run':run,'action':action}


class TestUI(unittest.TestCase):
    def setUp(self):
        root=ROOT/'.local-workbench/test-tmp';root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root);self.addCleanup(self.temp.cleanup)
        self.memory=Memory(Path(self.temp.name)/'memory')
        self.memory.record('task','fixture',{'name':'HTTP fixture','contract':{'prompt':'fixture'}})
        self.memory.record('attempt','fixture/node',{'task_id':'fixture','role':'candidate','status':'PASS','head_sha':'a'*40,'base_sha':'a'*40,'artifacts':{}})
        self.memory.record('test_result','fixture/test',{'task_id':'fixture','attempt_id':'fixture/node','verdict':'PASS','kind':'TEST_ONLY'})
        self.server=WorkbenchServer(self.memory,0,FakeExecution())
        self.worker=threading.Thread(target=self.server.serve_forever,daemon=True);self.worker.start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
        self.origin=self.server.origin;self.cookie=None;self.csrf=None

    def request(self,path,body=None,headers=None):
        h={'Host':self.origin.removeprefix('http://')}
        if self.cookie:h['Cookie']=self.cookie
        if body is not None:h.update({'Origin':self.origin,'X-Workbench-CSRF':self.csrf or '', 'Content-Type':'application/json'})
        h.update(headers or {})
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
        connection.request('GET' if body is None else 'POST',path,body=json.dumps(body) if body is not None else None,headers=h)
        response=connection.getresponse();raw=response.read();cookie=response.getheader('Set-Cookie');connection.close()
        try:value=json.loads(raw)
        except ValueError:value=raw.decode()
        return response.status,value,cookie

    def login(self):
        status,html,cookie=self.request('/',headers={'Sec-Fetch-Site':'none','Sec-Fetch-Mode':'navigate'})
        self.assertEqual(status,200);self.assertIn('HttpOnly; SameSite=Strict',cookie)
        self.cookie=cookie.split(';')[0];self.csrf=self.request('/api/state')[1]['csrf']

    def test_anonymous_dns_rebinding_cross_site_and_csrf_fail_before_changes(self):
        before=len(self.memory.events())
        self.assertEqual(self.request('/api/state')[0],403)
        self.assertEqual(self.request('/',headers={'Sec-Fetch-Site':'cross-site','Sec-Fetch-Mode':'navigate'})[0],403)
        self.assertEqual(self.request('/health',headers={'Host':'evil.example'})[0],403)
        self.login()
        payload={'node':'fixture/node','reason':'test annotation'}
        self.assertEqual(self.request('/api/annotate',payload,{'Origin':'https://evil.example'})[0],403)
        self.assertEqual(self.request('/api/annotate',payload,{'X-Workbench-CSRF':'forged'})[0],403)
        self.assertEqual(self.request('/api/annotate',payload|{'actor':'human_user'})[0],403)
        self.assertEqual(len(self.memory.events()),before)

    def test_owner_annotations_and_exact_head_review_are_persisted_no_remote_publish(self):
        self.login()
        status,value,_=self.request('/api/annotate',{'node':'fixture/node','reason':'Explicit HTTP fixture annotation'})
        self.assertEqual(status,200);self.assertEqual(self.memory.events()[-1]['actor'],'human_owner')
        status,intent,_=self.request('/api/pr-intent',{'node':'fixture/node','reason':'TEST FIXTURE NOT REAL USER APPROVAL'})
        self.assertEqual(status,200)
        self.assertEqual(self.request('/api/approve',{'intent':intent['id'],'reviewed_head':'b'*40,'reason':'fixture'})[0],400)
        self.assertEqual(self.request('/api/approve',{'intent':intent['id'],'reviewed_head':'a'*40,'reason':'TEST FIXTURE ONLY'})[0],200)
        self.assertEqual(self.request('/api/publish-pr',{'intent':intent['id']})[0],403)
        self.assertEqual(self.request('/api/reject-pr',{'intent':intent['id'],'reason':'fixture rejected'})[0],200)
        events=self.memory.events();self.assertEqual(events[-1]['data']['status'],'REJECTED')

    def test_settings_and_missing_paths_are_rejected(self):
        self.login()
        for change in ({'n':2},{'n':True},{'judge':'J2'},{'experiment_seconds':1201},{'ds_requests':161},{'api_cash_usd':6},{'codex_turns':17},{'arbitrary_shell':'evil'}):
            self.assertEqual(self.request('/api/start',{'settings':change})[0],400)
        self.assertEqual(self.request('/api/artifact?id=../../auth.json')[0],400)
        self.assertEqual(self.request('/api/unknown',{})[0],400)
        self.assertEqual(self.request('/api/annotate',{'node':'fixture/node','reason':'sk-'+'a'*24})[0],400)

    def test_failed_tests_and_changed_evidence_invalidate_product_review(self):
        self.login()
        intent=self.request('/api/pr-intent',{'node':'fixture/node','reason':'TEST FIXTURE ONLY'})[1]
        self.memory.record('test_result','fixture/later-test',{'task_id':'fixture','attempt_id':'fixture/node','verdict':'FAIL','kind':'TEST_ONLY'})
        self.assertEqual(self.request('/api/approve',{'intent':intent['id'],'reviewed_head':'a'*40,'reason':'TEST ONLY'})[0],400)
        self.assertEqual(self.request('/api/pr-intent',{'node':'fixture/node','reason':'cannot pass a failure'})[0],400)
        self.assertEqual(self.memory.get('action',intent['id'])['status'],'AWAITING_HUMAN_REVIEW')

    def test_p5_limits_are_phase_wide_and_not_reset_by_new_role_or_fork(self):
        from p1_budget import Ledger,BudgetDenied
        path=Path(self.temp.name)/'p5-ledger.json';ledger=Ledger(path,phase='P5',requests=160,codex_turns=16,cash_nano=5_000_000_000)
        # Synthetic complete usage frees cash only; the real request count remains reserved.
        for i in range(160):
            request=ledger.reserve_request('TEST_ONLY/fork-'+str(i))
            ledger.settle(request,{'input_tokens':0,'cache_read_input_tokens':0,'cache_creation_input_tokens':0,'output_tokens':0},{'kind':'TEST_FIXTURE_NOT_MODEL_RESULT'})
        with self.assertRaises(BudgetDenied):Ledger(path,phase='P5',requests=160,codex_turns=16,cash_nano=5_000_000_000).reserve_request('another fork')
        for i in range(16):ledger.reserve_codex_turn('TEST_ONLY/role-'+str(i),'gpt-6.1-sol')
        with self.assertRaises(BudgetDenied):ledger.reserve_codex_turn('new independent role','gpt-6.1-sol')
        with self.assertRaises(BudgetDenied):Ledger(path,phase='P3').reserve_request('wrong phase')

    def test_human_cancellation_is_distinct_from_code_failure(self):
        from p2_candidates import failure_report
        report=failure_report([{'id':'A','verdict':'CANCELLED'}])
        self.assertEqual(report['status'],'CANCELLED');self.assertFalse(report['best_failure_is_success'])
        self.assertEqual(report['failure_categories'],{'CANCELLED':1})

    def test_paused_stop_does_not_start_inference_and_cannot_resume(self):
        from workbench.execution import Execution
        self.memory.record('run','p5-fixture-paused',{'phase':'P5','task_id':'fixture','status':'PAUSED','elapsed_seconds':1})
        self.server.execution=Execution(self.memory);self.login()
        status,value,_=self.request('/api/stop',{'run':'p5-fixture-paused'})
        self.assertEqual(status,200);self.assertEqual(value['status'],'CANCELLED')
        self.assertIsNone(self.server.execution.running)
        self.assertEqual(self.request('/api/resume',{'run':'p5-fixture-paused'})[0],400)

    def test_pool_retry_keeps_n_and_contract_and_uses_explicit_new_run(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from workbench.execution import Execution
        from p2_candidates import digest
        from test_p2 import pool
        p=pool();contract={'kind':'TEST_CONTRACT_NOT_REAL_TASK'};p['contract_manifest']=contract;p.pop('pool_hash');p['pool_hash']=digest(p)
        options=settings({});options['n']=len(p['candidates'])
        # Fixture may contain N3; never silently use a different requested generation N.
        ref=self.memory.artifact(json.dumps(contract),'fixture-contract','human')
        self.memory.record('run','p5-fixture-quota',{'phase':'P5','task_id':'fixture','status':'INFRA_FAIL','settings':options,'contract_artifact':ref})
        execution=Execution(self.memory)
        with patch('workbench.execution.wsl',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(p).encode())),patch.object(execution,'start',return_value={'kind':'TEST_ONLY_ZERO_MODELS'}) as start:
            result=execution.retry_pool('p5-fixture-quota');self.assertEqual(result['kind'],'TEST_ONLY_ZERO_MODELS')
            self.assertEqual(start.call_args.kwargs['reuse_pool'],'/opt/workbench/runs/p5-fixture-quota-pool/frozen-pool.json')
            start.reset_mock()
            with self.assertRaises(ValueError):execution.retry_pool('p5-fixture-quota',{'n':5 if options['n']!=5 else 1})
            start.assert_not_called()

    def test_n1_and_n5_judge_m_comparisons_are_not_real_n2_or_n6_generation(self):
        from p3_contracts import judge_pool,handoff
        from p2_candidates import digest,validate_pool
        from test_p2 import pool
        for n in (1,5):
            p=pool();p['candidates']=[dict(p['candidates'][0],id=chr(65+i)) for i in range(n)]
            p.pop('pool_hash');p['pool_hash']=digest(p);validate_pool(p)
            package=handoff(p,{c['id']:{} for c in p['candidates']},{c['id']:{} for c in p['candidates']})
            m=dict(p['candidates'][0],id='M');graded=judge_pool(package,m)
            self.assertEqual(len(graded['candidates']),n+1)
            self.assertEqual(graded['purpose'],'JUDGE_COMPARISON')
            graded.pop('purpose');graded.pop('pool_hash');graded['pool_hash']=digest(graded)
            with self.assertRaises(ValueError):validate_pool(graded)


if __name__=='__main__':unittest.main()
