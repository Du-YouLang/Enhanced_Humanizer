"""Same frozen evidence, distinct J0/J1/J2/J3 algorithms; hard failures cannot win acceptance."""

import json
import math
from pathlib import Path
import time
from types import SimpleNamespace

from p1_budget import BudgetDenied, ChatUsage, MAX_OUTPUT
from p2_candidates import validate_pool, digest


def evidence(pool):
    validate_pool(pool)
    return {'task':pool['task_contract'],'rubric':pool['rubric'],
            'candidates':[{k:c.get(k,'unavailable') for k in ('id','source','patch','test_report','verdict','known_failures','head_commit')}
                          for c in pool['candidates']]}


def result(pool,judge_id,algorithm,ranking,scores,**metadata):
    validate_pool(pool)
    ids={c['id'] for c in pool['candidates']}
    if len(ranking)!=len(ids) or set(ranking)!=ids:raise ValueError('Judge ranking must cover every candidate exactly once')
    passed={c['id'] for c in pool['candidates'] if c['verdict']=='PASS'}
    return {'judge':judge_id,'algorithm':algorithm,'status':'COMPLETED','pool_hash':pool['pool_hash'],
            'rubric_hash':pool['rubric_hash'],'evidence_hash':digest(evidence(pool)),
            'ranking':ranking,'scores':scores,'raw_selected':ranking[0],
            'eligible_selected':next((cid for cid in ranking if cid in passed),None),
            'human_review_required':True,'api_bill_usd':'unavailable',**metadata}


def blocked(pool,kind,status,reason):
    validate_pool(pool)
    return {'judge':kind,'status':status,'reason':reason,'pool_hash':pool['pool_hash'],
            'rubric_hash':pool['rubric_hash'],'evidence_hash':digest(evidence(pool)),
            'eligible_selected':None,'human_review_required':True,'requests':0}


class J0:
    def judge(self,pool):
        tick=time.perf_counter()
        rows=sorted(pool['candidates'],key=lambda c:(c['verdict']!='PASS',c['id']))
        return result(pool,'J0','frozen-tests-stable-id-tie-break',[c['id'] for c in rows],
                      {c['id']:int(c['verdict']=='PASS') for c in rows},elapsed_seconds=time.perf_counter()-tick,
                      tokens='not_applicable',api_cash_usd=0)


def namespaces(value):
    if isinstance(value,dict):return SimpleNamespace(**{k:namespaces(v) for k,v in value.items()})
    if isinstance(value,list):return [namespaces(v) for v in value]
    return value


class LavTransport:
    """Client-shaped metered HTTP transport, injected via official LAV's public client= API."""
    _llm_verifier_deepseek=True
    _llm_verifier_model='deepseek-flash'

    def __init__(self,key,ledger,scope,deadline,source_module,private_response_root=None):
        self.key,self.ledger,self.scope,self.deadline=key,ledger,scope,deadline
        self.source_module=source_module
        self.chat=SimpleNamespace(completions=SimpleNamespace(create=self.create))
        self.probability_evidence=[]
        self.requests_sent=0
        self.private_response_root=private_response_root
        self.max_output=getattr(ledger,'max_output',MAX_OUTPUT)

    def create(self,**kwargs):
        import httpx
        if time.monotonic()>=self.deadline:raise BudgetDenied('Judge time cap')
        body=dict(kwargs);body.update(body.pop('extra_body',{}))
        allowed={'model','messages','max_tokens','temperature','logprobs','top_logprobs','thinking','reasoning_effort'}
        if set(body)-allowed or body.get('model')!='deepseek-flash' or body.get('logprobs') is not True:
            raise BudgetDenied('Unauthorized LAV request')
        if type(body.get('max_tokens')) is not int or not 0<body['max_tokens']<=self.max_output:
            raise BudgetDenied('LAV output limit')
        config=getattr(self.ledger,'config',{})
        from p6_network_policy import enabled,NetworkCheckRequired,NetworkRetryPending
        new_policy=enabled(config)
        reserve=lambda:self.ledger.reserve_request(self.scope,scope_requests=config['per_role_inference_requests'] if new_policy else 15,
                                                   scope_cash_nano=None if new_policy else 1_000_000_000)
        index=reserve()
        tick=time.perf_counter()
        import asyncio
        async def call(index=None,seconds=120):
            self.requests_sent+=1
            async with asyncio.timeout(min(seconds,max(.01,self.deadline-time.monotonic()))):
                async with httpx.AsyncClient(trust_env=False,follow_redirects=False,timeout=seconds) as client:
                    result=await client.post('https://api.deepseek.com/chat/completions',json=body,
                                             headers={'Authorization':'Bearer '+self.key})
                    if new_policy:
                        from p6_network_recovery import TRANSIENT_HTTP,TransientNetworkError
                        if result.status_code in TRANSIENT_HTTP:raise TransientNetworkError('Transient LAV provider status')
                    return result
        network_events=[]
        if new_policy:
            from p6_network_recovery import recover
            try:response=asyncio.run(recover(call,reserve,self.deadline,config,network_events,first_index=index))
            finally:
                if self.private_response_root is not None:
                    from p2_candidates import exclusive_json
                    self.private_response_root.mkdir(parents=True,exist_ok=True)
                    exclusive_json(self.private_response_root/('network-request-'+str(index)+'.json'),{'events':network_events,'model_failure':False})
            index=network_events[-1]['request_index']
        else:response=asyncio.run(call())
        if response.status_code!=200:raise RuntimeError('LAV upstream HTTP '+str(response.status_code))
        raw=response.json();tracker=ChatUsage();tracker.event(raw);tracker.event('[DONE]')
        if self.private_response_root is not None:
            from p2_candidates import exclusive_json
            self.private_response_root.mkdir(parents=True,exist_ok=True)
            exclusive_json(self.private_response_root/('response-'+str(index)+'.json'),raw)
        self.ledger.settle(index,tracker.verified(),{'model_id':raw.get('model'),'http_status':200,'protocol':'chat-completions-logprobs',
                          'elapsed_seconds':time.perf_counter()-tick,'bill_cash_usd':'unavailable','cache_creation_accounting':'not_applicable_in_protocol'})
        choice=raw['choices'][0]
        positions=(choice.get('logprobs') or {}).get('content') or []
        tokens=[p['token'] for p in positions]
        alts=[[(a['token'],a['logprob']) for a in p.get('top_logprobs',[])] for p in positions]
        # Original extraction has a literal-score fallback. For J1, reject BEFORE it
        # can be used: both exact score positions must expose genuine scale-token probabilities.
        masses={}
        for tag in ('<score_A>','<score_B>'):
            found=self.source_module._find_tag_logprobs(tokens,alts,tag)
            mass=sum(math.exp(lp) for token,lp in (found or [])
                     if token.strip().lstrip('>').strip() in self.source_module.SCALE['valid_tokens'] and math.isfinite(lp))
            if mass<=0:raise ValueError('BLOCKED_LOGPROBS: no score-position distribution')
            masses[tag]=mass
        if choice.get('finish_reason')!='stop':raise ValueError('Incomplete probability judgment')
        self.probability_evidence.append({'response_sha256':digest(raw),'score_token_probability_mass':masses,
                                          'output_positions':len(positions),'request_index':index})
        return namespaces(raw)


class J1:
    def __init__(self,client,source_path,cache_root):self.client,self.source_path,self.cache_root=client,source_path,Path(cache_root)

    def judge(self,pool):
        import sys
        validate_pool(pool)
        sys.path.insert(0,str(self.source_path))
        from llm_verifier import select
        tick=time.perf_counter();ev=evidence(pool)
        self.cache_root.mkdir(parents=True,exist_ok=True)
        output_cap=getattr(self.client,'max_output',4096)
        cache=self.cache_root/('strict-v3-lav030-K1-p1-off-'+str(output_cap)+'-'+pool['pool_hash']+'-'+pool['rubric_hash']+'.json')
        proof_path=cache.with_suffix('.proof.json')
        prior=[]
        if cache.exists():
            if not proof_path.exists():raise ValueError('Cached probabilities lack provenance')
            proof=json.loads(proof_path.read_text())
            if proof['cache_sha256']!=digest(cache.read_bytes()) or proof['pool_hash']!=pool['pool_hash']:
                raise ValueError('Cached probability provenance mismatch')
            prior=proof['probability_evidence']
        chosen=select(ev['task'],[json.dumps(c,sort_keys=True) for c in ev['candidates']],
                      criteria={'contract_quality':'Assess correctness, robustness and maintainability against the frozen task/tests; cite code evidence.'},
                      n_evaluations=1,pivots=1,seed=0,max_workers=1,model='deepseek-flash',cache=str(cache),progress=False,
                      on_error='raise',client=self.client)
        ids=[c['id'] for c in pool['candidates']]
        all_proof=prior+self.client.probability_evidence
        proof_path.write_text(json.dumps({'cache_sha256':digest(cache.read_bytes()),'pool_hash':pool['pool_hash'],
                                          'probability_evidence':all_proof},indent=2)+'\n')
        return result(pool,'J1','original-llm-verifier-0.3.0-PPT-logprob-expectation-K1',
                      [ids[i] for i in chosen.ranking],dict(zip(ids,chosen.scores)),
                      source_commit='90e8fc215606447d6d31e9e24bff7200fb0c0994',elapsed_seconds=time.perf_counter()-tick,
                      probability_evidence=all_proof,n_comparisons=chosen.n_comparisons,requests=self.client.requests_sent,
                      cache_identity=cache.name,configuration={'K':1,'pivots':1,'seed':0,'effort':'off','max_output':output_cap},
                      note='K1 smoke and compact evidence; full-trace sensitivity and benchmark accuracy remain P6')


class J2:
    def __init__(self,authorized_transport=None):self.transport=authorized_transport

    def judge(self,pool):
        if self.transport is None:return blocked(pool,'J2','BLOCKED_CREDENTIAL','No authorized Jev credential or Jev-specific budget; no request sent')
        state=json.dumps(evidence(pool),sort_keys=True)
        questions={}
        for c in pool['candidates']:
            for dimension in pool['rubric']['dimensions']:
                questions[c['id']+'_'+dimension]={'type':'score','instructions':f"Evaluate candidate {c['id']} {dimension} against task/evidence",
                                                  'criteria':['Unsupported or incorrect','Partially supported','Strongly supported']}
        raw=self.transport({'model':'jev-latest','state':state,'questions':questions})
        scores={c['id']:{} for c in pool['candidates']}
        for name in questions:
            cid,dimension=name.split('_',1);answer=raw['answers'][name]
            if answer.get('type')!='score' or not isinstance(answer.get('score'),(int,float)) or not 0<=answer['score']<=2:
                raise ValueError('Invalid Jev typed score')
            scores[cid][dimension]=answer['score']
        ranking=sorted(scores,key=lambda cid:(-sum(scores[cid].values()),cid))
        return result(pool,'J2','Jev-typed-Score-independent-dimensions',ranking,scores,model_id=raw['model'],
                      usage=raw.get('usage','unavailable'),confidence_and_probabilities=raw['answers'])


class J3:
    def __init__(self,evaluate):self.evaluate=evaluate

    def judge(self,pool):
        tick=time.perf_counter();raw,metadata=self.evaluate(evidence(pool))
        ids={c['id'] for c in pool['candidates']}
        if {c['id'] for c in raw['candidates']}!=ids or len(raw['candidates'])!=len(ids):raise ValueError('Sol candidate coverage mismatch')
        scores={}
        for c in raw['candidates']:
            if not c.get('evidence'):raise ValueError('Sol judgment lacks cited evidence')
            values={d:c[d] for d in pool['rubric']['dimensions']}
            if any(type(v) is not int or not 0<=v<=4 for v in values.values()):raise ValueError('Sol rubric score out of range')
            scores[c['id']]=values
        return result(pool,'J3','Sol-independent-structured-rubric-not-logprobs',raw['ranking'],scores,
                      elapsed_seconds=time.perf_counter()-tick,model_id='gpt-6.1-sol',judgment=raw,**metadata)
