"""Exact-head, single-use human capability gate for each product PR, separate from development CI."""

import hmac
import secrets
import time
from functools import wraps

from .memory import canonical,sha,uid


def serialized(method):
    @wraps(method)
    def guarded(self,*args,**kwargs):
        with self.memory.lock():return method(self,*args,**kwargs)
    return guarded


class Reviews:
    def __init__(self,memory,human_key):self.memory,self.human_key=memory,human_key

    @serialized
    def intent(self,node_id,target,reason):
        node=self.memory.get('attempt',node_id)
        if node['status']!='PASS':raise ValueError('Only a hard-accepted implementation can be proposed for PR')
        value={'task_id':node['task_id'],'attempt_id':node_id,'head_sha':node['head_sha'],
               'evidence_hash':sha(node.get('artifacts',{})),'target':target,'reason':reason,
               'status':'AWAITING_HUMAN_REVIEW','expires_at':time.time()+3600,'nonce':secrets.token_hex(16),
               'review_scope':'one product PR at this exact head/evidence/target'}
        return self.memory.record('action',uid('pr-intent'),value,'controller')

    @serialized
    def approve(self,intent_id,capability,reviewed_head,reason):
        if not isinstance(capability,str) or not hmac.compare_digest(capability,self.human_key):raise PermissionError('Human review capability required; agent identity/body claims are insufficient')
        value=self.memory.get('action',intent_id);node=self.memory.get('attempt',value['attempt_id'])
        if value['status']!='AWAITING_HUMAN_REVIEW' or value['expires_at']<time.time():raise ValueError('Review intent is stale or already decided')
        if reviewed_head!=value['head_sha'] or node['head_sha']!=reviewed_head or sha(node.get('artifacts',{}))!=value['evidence_hash']:
            raise ValueError('Code or evidence changed; a fresh human review is required')
        if not reason.strip():raise ValueError('Human review needs a reason')
        value.update(status='HUMAN_APPROVED',review_reason=reason,human_approval=True)
        self.memory.record('action',intent_id,value,'human_owner')
        return value

    @serialized
    def reject(self,intent_id,capability,reason):
        if not hmac.compare_digest(capability,self.human_key):raise PermissionError('Human review capability required')
        value=self.memory.get('action',intent_id)
        if value['status'] not in ('AWAITING_HUMAN_REVIEW','HUMAN_APPROVED'):raise ValueError('Already consumed/rejected')
        value.update(status='REJECTED',review_reason=reason)
        self.memory.record('action',intent_id,value,'human_owner');return value

    @serialized
    def consume(self,intent_id,current_head,target,evidence_hash):
        value=self.memory.get('action',intent_id)
        if value['status']!='HUMAN_APPROVED' or value['expires_at']<time.time():raise PermissionError('Each product PR requires a fresh human review')
        node=self.memory.get('attempt',value['attempt_id'])
        if (current_head,target,evidence_hash)!=(value['head_sha'],value['target'],value['evidence_hash']) or node['head_sha']!=current_head or sha(node.get('artifacts',{}))!=evidence_hash:
            raise PermissionError('Reviewed head, evidence or target changed')
        value['status']='CONSUMED_BEFORE_EXTERNAL_ACTION'
        self.memory.record('action',intent_id,value,'controller')
        return value
