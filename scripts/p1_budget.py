"""Persistent P1 reservation ledger. A completed response settles an upper bound, not a bill."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
import time

CONTEXT_TOKENS = 1_048_576
MAX_OUTPUT = 4096
# Integer nano-USD at the documented peak rates; cache discounts are never needed for safety.
INPUT_NANO = 300
OUTPUT_NANO = 1200
REQUEST_RESERVE = CONTEXT_TOKENS * INPUT_NANO + MAX_OUTPUT * OUTPUT_NANO


def replace_ledger(temporary,destination):
    """Bounded Windows sharing retry; never rerun the reservation transaction."""
    for attempt in range(6):
        try:
            os.replace(temporary,destination)
            return
        except PermissionError as error:
            if os.name!='nt' or getattr(error,'winerror',None) not in (5,32,33) or attempt==5:raise
            time.sleep(.02*(attempt+1))


class BudgetDenied(RuntimeError):
    pass


class Ledger:
    def __init__(self, path, *, requests=40, codex_turns=6, cash_nano=1_000_000_000, phase='P1'):
        caps={'P1':(40,1_000_000_000,6),'P2':(100,2_000_000_000,6),'P3':(40,1_000_000_000,12),
              'P5':(160,5_000_000_000,16),'P6':(200,5_000_000_000,32)}
        if phase not in caps:raise BudgetDenied('Unauthorized phase')
        self.path=Path(path)
        self.phase=phase
        self.requests=min(requests,caps[phase][0])
        self.codex_turns=min(codex_turns,caps[phase][2])
        self.cash_nano=min(cash_nano,caps[phase][1])
        self.lock=threading.Lock()

    @contextmanager
    def transaction(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.lock:
            with self.path.with_suffix('.lock').open('a+b') as lock:
                if os.name=='posix':
                    import fcntl
                    fcntl.flock(lock,fcntl.LOCK_EX)
                value=json.loads(self.path.read_text()) if self.path.exists() else {
                    'schema_version':1,'phase':self.phase,'requests':[],'codex_turns':[],'cash_bound_nano':0}
                if value.get('phase')!=self.phase or not isinstance(value.get('requests'),list) or not isinstance(value.get('codex_turns'),list):
                    raise BudgetDenied('Invalid phase ledger')
                expected=sum(r['charge_bound_nano'] for r in value['requests'])
                if type(value.get('cash_bound_nano')) is not int or value['cash_bound_nano']!=expected or expected<0:
                    raise BudgetDenied('Corrupt cash ledger')
                yield value
                temporary=self.path.with_suffix('.tmp')
                with temporary.open('w') as handle:
                    handle.write(json.dumps(value,indent=2)+'\n');handle.flush();os.fsync(handle.fileno())
                replace_ledger(temporary,self.path)

    def reserve_request(self, experiment, *, scope_requests=None, scope_cash_nano=None):
        with self.transaction() as value:
            scoped=[r for r in value['requests'] if r['experiment']==experiment]
            if scope_requests is not None and len(scoped)>=scope_requests:
                raise BudgetDenied('Candidate request cap exhausted')
            if scope_cash_nano is not None and sum(r['charge_bound_nano'] for r in scoped)+REQUEST_RESERVE>scope_cash_nano:
                raise BudgetDenied('Candidate cash cap exhausted')
            if len(value['requests'])>=self.requests or value['cash_bound_nano']+REQUEST_RESERVE>self.cash_nano:
                raise BudgetDenied(self.phase+' request/cash cap exhausted')
            index=len(value['requests'])+1
            value['requests'].append({'index':index,'experiment':experiment,'observed_at':datetime.now(timezone.utc).isoformat(),
                                      'status':'RESERVED_UNKNOWN_USAGE','charge_bound_nano':REQUEST_RESERVE})
            value['cash_bound_nano']+=REQUEST_RESERVE
        return index

    def settle(self,index,usage,metadata):
        fields=('input_tokens','cache_read_input_tokens','cache_creation_input_tokens','output_tokens')
        if any(type(usage.get(k)) is not int or usage[k]<0 for k in fields):
            raise BudgetDenied('Incomplete or invalid usage; keep reservation')
        input_total=sum(usage[k] for k in fields[:3])
        charge=input_total*INPUT_NANO+usage['output_tokens']*OUTPUT_NANO
        if input_total>CONTEXT_TOKENS or usage['output_tokens']>MAX_OUTPUT or charge>REQUEST_RESERVE:
            raise BudgetDenied('Usage exceeded documented request bound')
        with self.transaction() as value:
            request=value['requests'][index-1]
            if request['status']!='RESERVED_UNKNOWN_USAGE':
                raise BudgetDenied('A reservation cannot be settled twice')
            value['cash_bound_nano']-=request['charge_bound_nano']-charge
            request.update(status='SETTLED_USAGE_UPPER_BOUND',charge_bound_nano=charge,usage=usage,**metadata)

    def reserve_codex_turn(self,experiment,model,*,scope_turns=None):
        if model!='gpt-6.1-sol':
            raise BudgetDenied('Unauthorized Codex model identity')
        with self.transaction() as value:
            if scope_turns is not None and sum(r['experiment']==experiment for r in value['codex_turns'])>=scope_turns:
                raise BudgetDenied('Role Codex subscription turn cap exhausted')
            if len(value['codex_turns'])>=self.codex_turns:
                raise BudgetDenied(self.phase+' Codex subscription turn cap exhausted')
            value['codex_turns'].append({'experiment':experiment,'model':model,'observed_at':datetime.now(timezone.utc).isoformat()})


class MessagesUsage:
    """Accept only complete Messages streams. Never infer missing usage as zero."""
    def __init__(self):
        self.values={}
        self.model=None
        self.complete=False
        self.started=False

    def event(self, row):
        kind=row.get('type')
        if kind=='message_start':
            message=row.get('message',{})
            self.model=message.get('model')
            self.values.update(message.get('usage',{}))
            self.started=True
        elif kind=='message_delta':
            self.values.update(row.get('usage',{}))
        elif kind=='message_stop':
            self.complete=True

    def verified(self):
        if not self.started or not self.complete or self.model not in ('deepseek-flash','deepseek-v4-flash'):
            raise BudgetDenied('Incomplete stream or model mismatch')
        required=('input_tokens','output_tokens','cache_read_input_tokens','cache_creation_input_tokens')
        if any(type(self.values.get(k)) is not int for k in required):
            raise BudgetDenied('Required token fields unavailable')
        return {k:self.values[k] for k in required}


class ChatUsage:
    """The published DSH 0.1.5rc1 uses Chat Completions, unlike current upstream main."""
    def __init__(self):
        self.model=None
        self.values={}
        self.complete=False

    def event(self,row):
        if row=='[DONE]':
            self.complete=True
            return
        if row.get('model') is not None:
            if self.model is not None and self.model!=row['model']:
                raise BudgetDenied('Model changed within response')
            self.model=row['model']
        if row.get('usage'):self.values.update(row['usage'])

    def verified(self):
        if not self.complete or self.model!='deepseek-flash':
            raise BudgetDenied('Incomplete stream or unexpected model identity')
        fields=('prompt_tokens','completion_tokens','total_tokens','prompt_cache_hit_tokens','prompt_cache_miss_tokens')
        if any(type(self.values.get(k)) is not int or self.values[k]<0 for k in fields):
            raise BudgetDenied('Required Chat Completions usage unavailable')
        v=self.values
        if v['prompt_tokens']!=v['prompt_cache_hit_tokens']+v['prompt_cache_miss_tokens'] or v['total_tokens']!=v['prompt_tokens']+v['completion_tokens']:
            raise BudgetDenied('Inconsistent Chat Completions counters')
        # This API has cache hit/miss accounting and no separately priced cache-creation field.
        return {'input_tokens':v['prompt_cache_miss_tokens'],'cache_read_input_tokens':v['prompt_cache_hit_tokens'],
                'cache_creation_input_tokens':0,'output_tokens':v['completion_tokens']}
