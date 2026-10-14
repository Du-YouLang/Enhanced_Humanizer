"""Separate, authorization-bound main ledger; no aggregate ceiling was requested.

Reuses the established atomic reservation/settlement transport accounting. Historical
phase caps and ledgers are deliberately untouched; role watchdogs remain mandatory.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import threading

from p1_budget import BudgetDenied, Ledger, REQUEST_RESERVE, INPUT_NANO, OUTPUT_NANO, CONTEXT_TOKENS, MAX_OUTPUT

PHASE = 'P6_MAIN_LOCAL_20261011'


def authorization(config):
    value = json.loads(Path(config).read_text(encoding='utf-8')) if isinstance(config, (str, Path)) else dict(config)
    required = {
        'phase': PHASE, 'authorization_status': 'APPROVED_BY_USER_2026-10-11',
        'model_execution_enabled': True, 'aggregate_limit_policy': 'NO_USER_CEILING',
        'api_cash_usd': None, 'deepseek_inference_requests': None,
        'codex_subscription_turns': None, 'per_request_timeout_seconds': 120,
        'common_generation_timeout_seconds': 115, 'per_role_inference_requests': 20,
        'per_role_codex_turns': 1, 'per_candidate_timeout_seconds': 600,
        'per_experiment_active_timeout_seconds': 1200, 'top_up_allowed': False,
        'carry_over_allowed': False, 'automatic_retry_after_infrastructure_failure': False,
        'legacy_ledgers_immutable': True, 'gpu_evaluation_concurrency': 1,
        'compute_policy': 'LOCAL_ONLY_CPU_PROTOCOLS_PRESERVED_GPU_TASKS_SINGLE_LOCAL_GPU',
        'product_pr_requires_individual_human_review': True,
        'external_product_release_authorized': False,
        'requires_frozen_task_controls_before_models': True,
    }
    if value.get('authorization_status')=='APPROVED_BY_USER_2026-10-12':
        required.update(authorization_status='APPROVED_BY_USER_2026-10-12',
                        aggregate_limit_policy='USER_FINITE_CEILING',api_cash_usd=100,
                        deepseek_inference_requests=10000,per_role_inference_requests=100)
    if not value.get('authorization_reference') or any(
        key not in value or type(value[key]) is not type(expected) or value[key] != expected
        for key, expected in required.items()
    ):
        raise BudgetDenied('Missing or changed main experiment authorization/watchdogs')
    return value, hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class MainLedger(Ledger):
    def __init__(self, path, config):
        self.config, self.authorization_sha256 = authorization(config)
        self.path = Path(path)
        self.phase = PHASE
        self.requests=self.config['deepseek_inference_requests']
        self.cash_nano=None if self.config['api_cash_usd'] is None else self.config['api_cash_usd']*1_000_000_000
        self.codex_turns=None
        self.role_requests=self.config['per_role_inference_requests']
        self.lock = threading.Lock()

    def caps(self):return {'requests':self.requests,'codex_turns':self.codex_turns,'cash_nano':self.cash_nano}

    def validate(self, value):
        if value.get('authorization_sha256') != self.authorization_sha256 or value.get('aggregate_caps') != self.caps():
            raise BudgetDenied('Ledger is bound to a different authorization')
        if (self.requests is not None and len(value['requests'])>self.requests) or (self.cash_nano is not None and value['cash_bound_nano']>self.cash_nano):
            raise BudgetDenied('Corrupt aggregate cap')
        for index, row in enumerate(value['requests'], 1):
            if (type(row.get('index')) is not int or row.get('index') != index or type(row.get('charge_bound_nano')) is not int
                    or not 0 <= row['charge_bound_nano'] <= REQUEST_RESERVE
                    or row.get('status') not in ('RESERVED_UNKNOWN_USAGE', 'SETTLED_USAGE_UPPER_BOUND')
                    or not isinstance(row.get('experiment'), str) or not row['experiment']):
                raise BudgetDenied('Corrupt request reservation')
            if row['status'] == 'RESERVED_UNKNOWN_USAGE' and row['charge_bound_nano'] != REQUEST_RESERVE:
                raise BudgetDenied('Unknown usage cannot release a reservation')
            if row['status'] == 'SETTLED_USAGE_UPPER_BOUND':
                usage=row.get('usage',{});fields=('input_tokens','cache_read_input_tokens','cache_creation_input_tokens','output_tokens')
                if any(type(usage.get(key)) is not int or usage[key]<0 for key in fields):
                    raise BudgetDenied('Corrupt settled usage')
                inputs=sum(usage[key] for key in fields[:3]);outputs=usage['output_tokens']
                if (inputs>CONTEXT_TOKENS or outputs>MAX_OUTPUT or row.get('model_id')!='deepseek-flash'
                        or row['charge_bound_nano']!=inputs*INPUT_NANO+outputs*OUTPUT_NANO):
                    raise BudgetDenied('Settled usage, model and recorded bound disagree')
        for row in value['codex_turns']:
            if row.get('model') != 'gpt-6.1-sol' or not isinstance(row.get('experiment'), str) or not row['experiment']:
                raise BudgetDenied('Corrupt subscription reservation')
        for rows, cap in ((value['requests'], self.role_requests), (value['codex_turns'], 1)):
            counts = {}
            for row in rows:
                counts[row['experiment']] = counts.get(row['experiment'], 0) + 1
            if any(count > cap for count in counts.values()):
                raise BudgetDenied('Corrupt role cap')

    @contextmanager
    def transaction(self):
        with super().transaction() as value:
            if not self.path.exists():
                value.update(authorization_sha256=self.authorization_sha256,
                             aggregate_caps=self.caps())
            self.validate(value)
            yield value
            self.validate(value)

    def amend_authorization(self,previous_config,archive):
        """Explicit human amendment, under the same lock; no request is reset.

        The old exact bytes are archived before atomic replacement. A different
        fingerprint still cannot be silently rebound by ordinary execution.
        """
        previous=MainLedger(self.path,previous_config)
        if self.config['authorization_status']!='APPROVED_BY_USER_2026-10-12' or previous.config['authorization_status']!='APPROVED_BY_USER_2026-10-11':
            raise BudgetDenied('Only the explicit recorded finite-ceiling amendment is supported')
        if not self.path.exists():raise BudgetDenied('No existing ledger to amend')
        archive=Path(archive)
        with Ledger.transaction(self) as value:
            previous.validate(value)
            before=self.path.read_bytes();snapshot=hashlib.sha256(before).hexdigest()
            retained=json.dumps({k:value[k] for k in ('requests','codex_turns','cash_bound_nano')},sort_keys=True)
            value.setdefault('authorization_history',[]).append({'previous_authorization_sha256':previous.authorization_sha256,
                'previous_aggregate_caps':previous.caps(),'before_ledger_sha256':snapshot,
                'amended_at':datetime.now(timezone.utc).isoformat(),'requests_retained':len(value['requests']),
                'cash_bound_nano_retained':value['cash_bound_nano']})
            value.update(authorization_sha256=self.authorization_sha256,aggregate_caps=self.caps())
            self.validate(value)
            if json.dumps({k:value[k] for k in ('requests','codex_turns','cash_bound_nano')},sort_keys=True)!=retained:
                raise BudgetDenied('Amendment must preserve every request and reservation')
            archive.parent.mkdir(parents=True,exist_ok=True)
            with archive.open('xb') as file:file.write(before);file.flush();os.fsync(file.fileno())
        return {'status':'AMENDED_WITHOUT_RESET','before_ledger_sha256':snapshot,
                'authorization_sha256':self.authorization_sha256,'requests_retained':len(value['requests']),
                'cash_bound_nano_retained':value['cash_bound_nano'],'aggregate_caps':self.caps()}

    @staticmethod
    def scope(experiment):
        if not isinstance(experiment, str) or not experiment or len(experiment) > 300:
            raise BudgetDenied('A bounded, distinct role scope is required')

    def reserve_request(self, experiment, *, scope_requests=None, scope_cash_nano=None):
        self.scope(experiment)
        cap = self.role_requests if scope_requests is None else min(self.role_requests, scope_requests)
        if type(cap) is not int or cap <= 0:
            raise BudgetDenied('Invalid role request cap')
        with self.transaction() as value:
            if (self.requests is not None and len(value['requests'])>=self.requests) or (self.cash_nano is not None and value['cash_bound_nano']+REQUEST_RESERVE>self.cash_nano):
                raise BudgetDenied('Main request/cash cap exhausted')
            scoped = [r for r in value['requests'] if r['experiment'] == experiment]
            if len(scoped) >= cap:
                raise BudgetDenied('Role request cap exhausted')
            if scope_cash_nano is not None and sum(r['charge_bound_nano'] for r in scoped) + REQUEST_RESERVE > scope_cash_nano:
                raise BudgetDenied('Explicit narrower role cash cap exhausted')
            index = len(value['requests']) + 1
            value['requests'].append({'index': index, 'experiment': experiment,
                'observed_at': datetime.now(timezone.utc).isoformat(),
                'status': 'RESERVED_UNKNOWN_USAGE', 'charge_bound_nano': REQUEST_RESERVE})
            value['cash_bound_nano'] += REQUEST_RESERVE
        return index

    def reserve_codex_turn(self, experiment, model, *, scope_turns=None):
        self.scope(experiment)
        if model != 'gpt-6.1-sol' or (scope_turns is not None and (type(scope_turns) is not int or scope_turns < 1)):
            raise BudgetDenied('Unauthorized model/role subscription cap')
        with self.transaction() as value:
            if any(row['experiment'] == experiment for row in value['codex_turns']):
                raise BudgetDenied('Role subscription turn already reserved; failures are not refunded')
            value['codex_turns'].append({'experiment': experiment, 'model': model,
                                       'observed_at': datetime.now(timezone.utc).isoformat()})

    def settle(self, index, usage, metadata):
        if type(index) is not int or index < 1 or not isinstance(metadata, dict) or metadata.get('model_id')!='deepseek-flash' or set(metadata) & {
            'index', 'experiment', 'status', 'charge_bound_nano', 'usage', 'observed_at',
        }:
            raise BudgetDenied('Invalid settlement identity/metadata')
        # The parent transaction serializes the settlement and verifies complete token accounting.
        super().settle(index, usage, metadata)
