"""Append-only event authority, rebuildable SQLite projections, immutable local artifacts."""

from contextlib import contextmanager
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import uuid

ROOT=Path(__file__).resolve().parents[2]
KINDS=('project_contract','task','run','attempt','test_result','judgment','decision','handoff',
       'knowledge','checkpoint','link','action','artifact')
STATES={'fact','hypothesis','rejected','superseded','unresolved'}
SECRET=re.compile(r'(?i)(?:\bsk-[a-z0-9_-]{16,}|\bBearer\s+[a-z0-9._~+/-]{16,}|(?:api[_-]?key|access[_-]?token|refresh[_-]?token)\s*["\x27]?\s*[:=]\s*["\x27][^"\x27\s]{12,})')


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def sha(value):return hashlib.sha256(value if isinstance(value,bytes) else canonical(value)).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def uid(prefix):return prefix+'-'+uuid.uuid4().hex[:16]


def local(path,boundary=ROOT):
    path=Path(path).absolute()
    if not path.resolve().is_relative_to(Path(boundary).resolve()):raise ValueError('Path is outside the project')
    if path.is_symlink():raise ValueError('Symlink state paths are refused')
    return path


def safe_text(text,*,redact=False):
    if SECRET.search(text):
        if not redact:raise ValueError('Credential-like content refused before persistence')
        return SECRET.sub('[REDACTED CREDENTIAL]',text)
    return text


class Memory:
    def __init__(self,root,boundary=ROOT):
        self.boundary=Path(boundary).resolve();self.root=local(root,self.boundary)
        self.root.mkdir(parents=True,exist_ok=True)
        self.artifacts=self.root/'artifacts';self.artifacts.mkdir(exist_ok=True)
        self.journal=self.root/'events.ndjson';self.database=self.root/'index.sqlite3'
        self.mutex=threading.RLock();self.depth=threading.local()
        with self.lock():self._sync()

    @contextmanager
    def lock(self):
        with self.mutex:
            if getattr(self.depth,'value',0):
                yield
                return
            with (self.root/'writer.lock').open('a+b') as lock:
                if os.name=='nt':
                    import msvcrt
                    if lock.tell()==0:lock.write(b'0');lock.flush()
                    lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_LOCK,1)
                else:
                    import fcntl
                    fcntl.flock(lock,fcntl.LOCK_EX)
                self.depth.value=1
                try:yield
                finally:
                    self.depth.value=0
                    if os.name=='nt':lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
                    else:fcntl.flock(lock,fcntl.LOCK_UN)

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.database,timeout=20)
        try:
            db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=FULL')
            db.execute('CREATE TABLE IF NOT EXISTS execution_event(seq INTEGER PRIMARY KEY, hash TEXT UNIQUE, body TEXT NOT NULL)')
            for name in KINDS:db.execute(f'CREATE TABLE IF NOT EXISTS {name}(id TEXT PRIMARY KEY,event_seq INTEGER NOT NULL,body TEXT NOT NULL)')
            with db:yield db
        finally:db.close()

    def events(self):
        previous='0'*64;sequence=0
        if not self.journal.exists():return []
        events=[]
        with self.journal.open('rb') as file:
            for raw in file:
                if not raw.endswith(b'\n'):raise ValueError('Torn event tail; preserve journal and restore verified backup')
                value=json.loads(raw);claimed=value['hash'];body={k:v for k,v in value.items() if k!='hash'}
                sequence+=1
                if value['seq']!=sequence or value['previous']!=previous or sha(body)!=claimed:raise ValueError('Event chain integrity failed')
                if value['kind'] not in KINDS:raise ValueError('Unknown event schema')
                previous=claimed;events.append(value)
        return events

    @staticmethod
    def project(db,event):
        name=event['kind']
        db.execute('INSERT INTO execution_event VALUES(?,?,?)',(event['seq'],event['hash'],canonical(event).decode()))
        db.execute(f'INSERT OR REPLACE INTO {name} VALUES(?,?,?)',(event['id'],event['seq'],canonical(event['data']).decode()))

    def _sync(self):
        events=self.events()
        with self.connect() as db:
            indexed=list(db.execute('SELECT seq,hash FROM execution_event ORDER BY seq'))
            if indexed!=[(e['seq'],e['hash']) for e in events[:len(indexed)]]:
                raise ValueError('SQLite event index differs from the authoritative journal')
            for event in events[len(indexed):]:self.project(db,event)

    def rebuild(self):
        with self.lock():
            events=self.events()
            with self.connect() as db:
                db.execute('DELETE FROM execution_event')
                for name in KINDS:db.execute(f'DELETE FROM {name}')
                for event in events:self.project(db,event)
        return len(events)

    def record(self,kind,identifier,data,actor='controller'):
        if kind not in KINDS or not isinstance(identifier,str) or not identifier:raise ValueError('Unknown record type/id')
        safe_text(canonical(data).decode())
        if kind=='knowledge' and data.get('state') not in STATES:raise ValueError('Knowledge must carry an explicit epistemic state')
        with self.lock():
            self._sync();events=self.events()
            event={'schema_version':1,'seq':len(events)+1,'previous':events[-1]['hash'] if events else '0'*64,
                   'kind':kind,'id':identifier,'timestamp':now(),'actor':actor,'data':data}
            event['hash']=sha(event)
            with self.journal.open('ab') as file:file.write(canonical(event)+b'\n');file.flush();os.fsync(file.fileno())
            # A crash here is recovered by replaying the fully fsynced journal, not by erasing it.
            with self.connect() as db:self.project(db,event)
        return data|{'id':identifier,'event_seq':event['seq']}

    def get(self,kind,identifier):
        if kind not in KINDS:raise ValueError('Unknown record type')
        with self.connect() as db:row=db.execute(f'SELECT body FROM {kind} WHERE id=?',(identifier,)).fetchone()
        if row is None:raise KeyError(identifier)
        return json.loads(row[0])|{'id':identifier}

    def list(self,kind,task_id=None):
        if kind not in KINDS:raise ValueError('Unknown record type')
        with self.connect() as db:rows=db.execute(f'SELECT id,body FROM {kind} ORDER BY event_seq').fetchall()
        values=[json.loads(body)|{'id':identifier} for identifier,body in rows]
        return [v for v in values if task_id is None or v.get('task_id')==task_id]

    def artifact(self,data,kind='evidence',access='human',source=None):
        if isinstance(data,str):data=data.encode()
        if access not in ('human','agent'):raise ValueError('Unknown artifact access')
        safe_text(data.decode('utf-8',errors='replace'))
        identifier=sha(data);path=self.artifacts/identifier
        if path.exists():
            if path.is_symlink() or sha(path.read_bytes())!=identifier:raise ValueError('Artifact collision/tampering')
        else:
            with path.open('xb') as file:file.write(data);file.flush();os.fsync(file.fileno())
        try:old=self.get('artifact',identifier)
        except KeyError:old=None
        if old is None:self.record('artifact',identifier,{'kind':kind,'access':access,'bytes':len(data),'source':source or 'local'})
        elif old['access']!=access:
            if old['access']=='human':raise ValueError('Human-only artifact cannot be promoted silently')
            self.record('artifact',identifier,{**old,'access':'human'})
        return identifier

    def read_artifact(self,identifier,actor='human'):
        if not re.fullmatch('[0-9a-f]{64}',identifier):raise ValueError('Invalid artifact ID')
        value=self.get('artifact',identifier)
        if actor!='human' and value['access']!='agent':raise PermissionError('Hidden tests and full traces are human-only')
        path=local(self.artifacts/identifier,self.root)
        data=path.read_bytes()
        if sha(data)!=identifier:raise ValueError('Artifact integrity failed')
        return data

    def handoff(self,node_id,to_role,next_action):
        node=self.get('attempt',node_id);task_id=node['task_id']
        knowledge=self.list('knowledge',task_id)
        human_routes=[{k:a[k] for k in ('id','kind','reason','head_sha','attempt_id') if k in a}
                      for a in self.list('action',task_id) if a.get('kind') in ('annotate','reject','route')]
        package={'schema_version':1,'task_id':task_id,'from_attempt':node_id,'from_role':node['role'],'to_role':to_role,
                 'current_commit':node.get('recovery_sha',node.get('head_sha','unavailable')),'task_contract':node.get('contract',self.get('task',task_id)['contract']),
                 'verified_facts':[v for v in knowledge if v['state']=='fact'],
                 'hypotheses':[v for v in knowledge if v['state']=='hypothesis'],
                 'rejected_routes':[v for v in knowledge if v['state'] in ('rejected','superseded')],
                 'unresolved':[v for v in knowledge if v['state']=='unresolved'],
                 'failures':[{'id':a['id'],'status':a['status'],'head_sha':a.get('head_sha'),'evidence':a.get('artifacts',{})}
                             for a in self.list('attempt',task_id) if a['status'] in ('FAIL','INFRA_FAIL','TIMEOUT','CANCELLED','BUDGET_EXHAUSTED','REFUSED','INTERRUPTED')],
                 'tests':self.list('test_result',task_id),'next_action':next_action,
                 'remaining_budget':node.get('remaining_budget','unavailable'),
                 'human_routes':human_routes,
                 'raw_chats_included':False,'human_review_required':True}
        try:
            run=self.get('run',node['run_id']);limits=run['limits'];ledger=self.get('project_contract','p5-ledger')
            if run.get('phase')=='P5':package['remaining_budget']={
                'api_cash_remaining_usd_upper_bound':max(0,limits['api_cash_usd']-ledger['cash_upper_bound_usd']),
                'deepseek_requests_remaining':max(0,limits['deepseek_inference_requests']-ledger['requests']),
                'codex_reserved_turns_remaining':max(0,limits['codex_subscription_turns']-ledger['codex_turns']),
                'ledger_hash':ledger['ledger_hash'],'usage_cost_availability':'see phase ledger; subscription monetary cost unavailable'}
        except KeyError:pass
        # Only explicitly agent-visible evidence can enter another agent's handoff.
        for row in package['tests']:
            row.pop('hidden_test_artifact',None)
            if row.get('artifact') and self.get('artifact',row['artifact'])['access']!='agent':row.pop('artifact')
        for row in package['failures']:
            row['evidence']={k:v for k,v in row['evidence'].items() if self.get('artifact',v)['access']=='agent'}
        for rows in (package['verified_facts'],package['hypotheses'],package['rejected_routes'],package['unresolved']):
            for row in rows:row['evidence_refs']=[v for v in row.get('evidence_refs',[]) if self.get('artifact',v)['access']=='agent']
        package['hash']=sha(package)
        self.record('handoff',uid('handoff'),package)
        return package

    def verify(self):
        with self.lock():return self._verify()

    def _verify(self):
        self._sync()
        expected={}
        for event in self.events():expected[(event['kind'],event['id'])]=event['data']
        with self.connect() as db:
            actual={(kind,identifier):json.loads(body) for kind in KINDS for identifier,body in db.execute(f'SELECT id,body FROM {kind}')}
        if expected!=actual:raise ValueError('SQLite projection tampered; rebuild from the journal')
        for item in self.list('artifact'):self.read_artifact(item['id'])
        return {'verdict':'PASS','events':len(self.events()),'artifacts':len(self.list('artifact')),'tail_hash':self.events()[-1]['hash'] if self.events() else '0'*64}
