"""Separate, authorization-bound main ledger with preserved amendment history.

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
from p6_output_policy import OUTPUT_REVISION,MAIN_OUTPUT_TOKENS
from p6_network_policy import POLICY as NETWORK_POLICY, REVISION as NETWORK_REVISION, enabled as network_enabled

PHASE = 'P6_MAIN_LOCAL_20261011'
TIME_REVISION = 'USER_APPROVED_2026-10-12_PUBLIC15_SCIENCE20'
CASH_REVISION = 'USER_APPROVED_2026-10-13_CUMULATIVE_USD200'
CASH250_REVISION = 'USER_APPROVED_2026-10-15_CUMULATIVE_USD250_BLACK5_P1_ONLY'
CASH250_SCOPE = 'ONLY_AUTHORIZED_BLACK5_P1_DEEPSEEK_NETWORK_REDO'


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
        if value.get('time_budget_revision') == TIME_REVISION:
            for field in ('role_timeout_seconds_by_family','experiment_timeout_seconds_by_family'):
                if not isinstance(value.get(field),dict) or any(type(v) is not int for v in value[field].values()):
                    raise BudgetDenied('Integer family time limits required')
            required.update(time_budget_revision=TIME_REVISION,
                            common_generation_timeout_seconds=900,
                            role_timeout_seconds_by_family={'public':900,'scientific':1200},
                            per_candidate_timeout_seconds=1200,
                            per_experiment_active_timeout_seconds=10800,
                            experiment_timeout_seconds_by_family={'public':7200,'scientific':10800})
        elif 'time_budget_revision' in value:
            raise BudgetDenied('Unknown human time-budget revision')
        if 'network_recovery_revision' in value:
            if (not network_enabled(value) or value.get('time_budget_revision')!=TIME_REVISION
                    or value.get('output_budget_revision')!=OUTPUT_REVISION):
                raise BudgetDenied('Unknown or unbound human network revision')
            required.update(NETWORK_POLICY)
        if 'cash_budget_revision' in value:
            if (value['cash_budget_revision'] not in (CASH_REVISION,CASH250_REVISION) or not network_enabled(value)
                    or value.get('output_budget_revision') != OUTPUT_REVISION
                    or value.get('time_budget_revision') != TIME_REVISION):
                raise BudgetDenied('Unknown or unbound human cash-budget revision')
            required.update(api_cash_usd=200,cash_budget_revision=CASH_REVISION)
            if value['cash_budget_revision']==CASH250_REVISION:
                required.update(api_cash_usd=250,cash_budget_revision=CASH250_REVISION,paid_scope_policy=CASH250_SCOPE)
    elif 'cash_budget_revision' in value:
        raise BudgetDenied('Cash extension requires the existing finite authorization')
    if not value.get('authorization_reference') or any(
        key not in value or type(value[key]) is not type(expected) or value[key] != expected
        for key, expected in required.items()
    ):
        raise BudgetDenied('Missing or changed main experiment authorization/watchdogs')
    if 'output_budget_revision' in value:
        if (value.get('time_budget_revision')!=TIME_REVISION or
            value.get('output_budget_revision')!=OUTPUT_REVISION or
            type(value.get('per_request_output_tokens')) is not int or
            value['per_request_output_tokens']!=MAIN_OUTPUT_TOKENS):
            raise BudgetDenied('Explicit prospective output revision required')
    elif 'per_request_output_tokens' in value:
        raise BudgetDenied('Output cap cannot change without a protocol revision')
    return value, hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def task_limits(config, task):
    """One family policy for every arm and role, including scoring and LAV."""
    value,_ = authorization(config)
    if task.get('family') not in ('BugsInPy','SWE-bench Lite','scientific'):
        raise BudgetDenied('Unknown task family for time allocation')
    family = 'scientific' if task['family']=='scientific' else 'public'
    if value.get('time_budget_revision') == TIME_REVISION:
        return {'role_seconds':value['role_timeout_seconds_by_family'][family],
                'active_seconds':value['experiment_timeout_seconds_by_family'][family]}
    return {'role_seconds':value['common_generation_timeout_seconds'],
            'active_seconds':value['per_experiment_active_timeout_seconds']}


class MainLedger(Ledger):
    def __init__(self, path, config, *, fixture=False):
        if type(fixture) is not bool:raise BudgetDenied('Explicit fixture flag required')
        self.fixture=fixture
        self.config, self.authorization_sha256 = authorization(config)
        self.path = Path(path)
        self.phase = PHASE
        self.requests=self.config['deepseek_inference_requests']
        self.cash_nano=None if self.config['api_cash_usd'] is None else self.config['api_cash_usd']*1_000_000_000
        self.codex_turns=None
        self.role_requests=self.config['per_role_inference_requests']
        self.max_output=self.config.get('per_request_output_tokens',MAX_OUTPUT)
        self.request_reserve=CONTEXT_TOKENS*INPUT_NANO+self.max_output*OUTPUT_NANO
        self.lock = threading.Lock()

    def caps(self):return {'requests':self.requests,'codex_turns':self.codex_turns,'cash_nano':self.cash_nano}

    def validate(self, value):
        if value.get('authorization_sha256') != self.authorization_sha256 or value.get('aggregate_caps') != self.caps():
            raise BudgetDenied('Ledger is bound to a different authorization')
        if (self.requests is not None and len(value['requests'])>self.requests) or (self.cash_nano is not None and value['cash_bound_nano']>self.cash_nano):
            raise BudgetDenied('Corrupt aggregate cap')
        for index, row in enumerate(value['requests'], 1):
            output_cap=row.get('output_token_cap',MAX_OUTPUT)
            if (type(output_cap) is not int or output_cap not in (MAX_OUTPUT,self.max_output) or
                ('output_token_cap' in row and row.get('output_policy_revision')!=OUTPUT_REVISION)):
                raise BudgetDenied('Corrupt request output policy')
            reserve=CONTEXT_TOKENS*INPUT_NANO+output_cap*OUTPUT_NANO
            if (type(row.get('index')) is not int or row.get('index') != index or type(row.get('charge_bound_nano')) is not int
                    or not 0 <= row['charge_bound_nano'] <= reserve
                    or row.get('status') not in ('RESERVED_UNKNOWN_USAGE', 'SETTLED_USAGE_UPPER_BOUND')
                    or not isinstance(row.get('experiment'), str) or not row['experiment']):
                raise BudgetDenied('Corrupt request reservation')
            if row['status'] == 'RESERVED_UNKNOWN_USAGE' and row['charge_bound_nano'] != reserve:
                raise BudgetDenied('Unknown usage cannot release a reservation')
            if row['status'] == 'SETTLED_USAGE_UPPER_BOUND':
                usage=row.get('usage',{});fields=('input_tokens','cache_read_input_tokens','cache_creation_input_tokens','output_tokens')
                if any(type(usage.get(key)) is not int or usage[key]<0 for key in fields):
                    raise BudgetDenied('Corrupt settled usage')
                inputs=sum(usage[key] for key in fields[:3]);outputs=usage['output_tokens']
                if (inputs>CONTEXT_TOKENS or outputs>output_cap or row.get('model_id')!='deepseek-flash'
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
        finite_amendment = self.config['authorization_status']=='APPROVED_BY_USER_2026-10-12' and previous.config['authorization_status']=='APPROVED_BY_USER_2026-10-11' and 'time_budget_revision' not in self.config
        time_amendment = (previous.config['authorization_status']=='APPROVED_BY_USER_2026-10-12'
                          and 'time_budget_revision' not in previous.config
                          and self.config.get('time_budget_revision')==TIME_REVISION
                          and self.caps()==previous.caps()
                          and self.role_requests==previous.role_requests)
        output_amendment=(previous.config.get('time_budget_revision')==TIME_REVISION
                          and 'output_budget_revision' not in previous.config
                          and self.config.get('output_budget_revision')==OUTPUT_REVISION
                          and self.caps()==previous.caps())
        network_amendment=('network_recovery_revision' not in previous.config
                           and network_enabled(self.config)
                           and previous.config.get('output_budget_revision')==OUTPUT_REVISION
                           and self.caps()==previous.caps())
        cash_amendment=(previous.config.get('network_recovery_revision')==NETWORK_REVISION
                        and 'cash_budget_revision' not in previous.config
                        and self.config.get('cash_budget_revision')==CASH_REVISION
                        and previous.cash_nano==100_000_000_000 and self.cash_nano==200_000_000_000)
        cash250_amendment=(previous.config.get('cash_budget_revision')==CASH_REVISION
                            and self.config.get('cash_budget_revision')==CASH250_REVISION
                            and previous.cash_nano==200_000_000_000 and self.cash_nano==250_000_000_000)
        if cash_amendment or cash250_amendment:
            allowed={'authorization_reference','api_cash_usd','cash_budget_revision'}
            if cash250_amendment:allowed.add('paid_scope_policy')
            if any(self.config.get(key)!=previous.config.get(key) for key in set(self.config)|set(previous.config) if key not in allowed):
                raise BudgetDenied('Cash amendment cannot change any other authorized control')
        if network_amendment:
            allowed={'authorization_reference',*NETWORK_POLICY}
            if any(self.config.get(key)!=previous.config.get(key) for key in set(self.config)|set(previous.config) if key not in allowed):
                raise BudgetDenied('Network amendment cannot change other authorized controls')
        if output_amendment:
            allowed={'authorization_reference','output_budget_revision','per_request_output_tokens'}
            if any(self.config.get(key)!=previous.config.get(key) for key in set(self.config)|set(previous.config) if key not in allowed):
                raise BudgetDenied('Output amendment cannot change other authorized controls')
        if time_amendment:
            allowed={'authorization_reference','time_budget_revision','common_generation_timeout_seconds',
                     'role_timeout_seconds_by_family','per_candidate_timeout_seconds',
                     'per_experiment_active_timeout_seconds','experiment_timeout_seconds_by_family'}
            if any(self.config.get(key)!=previous.config.get(key) for key in set(self.config)|set(previous.config) if key not in allowed):
                raise BudgetDenied('Time amendment cannot change other authorized controls')
        if not (finite_amendment or time_amendment or output_amendment or network_amendment or cash_amendment or cash250_amendment):
            raise BudgetDenied('Only the explicit finite-ceiling or human time-budget amendment is supported')
        if not self.path.exists():raise BudgetDenied('No existing ledger to amend')
        archive=Path(archive)
        with Ledger.transaction(self) as value:
            previous.validate(value)
            before=self.path.read_bytes();snapshot=hashlib.sha256(before).hexdigest()
            retained=json.dumps({k:value[k] for k in ('requests','codex_turns','cash_bound_nano')},sort_keys=True)
            value.setdefault('authorization_history',[]).append({'previous_authorization_sha256':previous.authorization_sha256,
                'previous_aggregate_caps':previous.caps(),'before_ledger_sha256':snapshot,
                'amended_at':datetime.now(timezone.utc).isoformat(),'requests_retained':len(value['requests']),
                'subscription_turns_retained':len(value['codex_turns']),
                'amendment_kind':CASH_REVISION if cash_amendment else NETWORK_REVISION if network_amendment else OUTPUT_REVISION if output_amendment else TIME_REVISION if time_amendment else 'USER_FINITE_CEILING',
                'cash_bound_nano_retained':value['cash_bound_nano']})
            value.update(authorization_sha256=self.authorization_sha256,aggregate_caps=self.caps())
            self.validate(value)
            if json.dumps({k:value[k] for k in ('requests','codex_turns','cash_bound_nano')},sort_keys=True)!=retained:
                raise BudgetDenied('Amendment must preserve every request and reservation')
            archive.parent.mkdir(parents=True,exist_ok=True)
            with archive.open('xb') as file:file.write(before);file.flush();os.fsync(file.fileno())
        return {'status':'AMENDED_WITHOUT_RESET','before_ledger_sha256':snapshot,
                'authorization_sha256':self.authorization_sha256,'requests_retained':len(value['requests']),
                'subscription_turns_retained':len(value['codex_turns']),
                'cash_bound_nano_retained':value['cash_bound_nano'],'aggregate_caps':self.caps()}

    @staticmethod
    def scope(experiment):
        if not isinstance(experiment, str) or not experiment or len(experiment) > 300:
            raise BudgetDenied('A bounded, distinct role scope is required')

    def reserve_request(self, experiment, *, scope_requests=None, scope_cash_nano=None):
        self.scope(experiment)
        if self.config.get('cash_budget_revision')==CASH250_REVISION and not self.fixture:
            import re
            if not re.fullmatch(r'PI_FORMAL/formal-network-redo-[0-9TZ]+/BIP-black-5-P1-deepseek',experiment):
                raise BudgetDenied('USD250 amendment is reserved for the authorized Black5/P1/DeepSeek redo only')
        cap = self.role_requests if scope_requests is None else min(self.role_requests, scope_requests)
        if type(cap) is not int or cap <= 0:
            raise BudgetDenied('Invalid role request cap')
        with self.transaction() as value:
            if (self.requests is not None and len(value['requests'])>=self.requests) or (self.cash_nano is not None and value['cash_bound_nano']+self.request_reserve>self.cash_nano):
                raise BudgetDenied('Main request/cash cap exhausted')
            scoped = [r for r in value['requests'] if r['experiment'] == experiment]
            if len(scoped) >= cap:
                raise BudgetDenied('Role request cap exhausted')
            if scope_cash_nano is not None and sum(r['charge_bound_nano'] for r in scoped) + self.request_reserve > scope_cash_nano:
                raise BudgetDenied('Explicit narrower role cash cap exhausted')
            index = len(value['requests']) + 1
            value['requests'].append({'index': index, 'experiment': experiment,
                'observed_at': datetime.now(timezone.utc).isoformat(),
                'status': 'RESERVED_UNKNOWN_USAGE', 'charge_bound_nano': self.request_reserve})
            if self.config.get('output_budget_revision')==OUTPUT_REVISION:
                value['requests'][-1].update(output_token_cap=self.max_output,output_policy_revision=OUTPUT_REVISION)
            value['cash_bound_nano'] += self.request_reserve
        return index

    def reserve_codex_turn(self, experiment, model, *, scope_turns=None):
        self.scope(experiment)
        if self.config.get('cash_budget_revision')==CASH250_REVISION and not self.fixture:
            raise BudgetDenied('USD250 amendment does not authorize new subscription trials')
        if model != 'gpt-6.1-sol' or (scope_turns is not None and (type(scope_turns) is not int or scope_turns < 1)):
            raise BudgetDenied('Unauthorized model/role subscription cap')
        with self.transaction() as value:
            if any(row['experiment'] == experiment for row in value['codex_turns']):
                raise BudgetDenied('Role subscription turn already reserved; failures are not refunded')
            value['codex_turns'].append({'experiment': experiment, 'model': model,
                                       'observed_at': datetime.now(timezone.utc).isoformat()})

    def settle(self, index, usage, metadata):
        if type(index) is not int or index < 1 or not isinstance(metadata, dict) or metadata.get('model_id')!='deepseek-flash' or set(metadata) & {
            'index', 'experiment', 'status', 'charge_bound_nano', 'usage', 'observed_at','output_token_cap','output_policy_revision',
        }:
            raise BudgetDenied('Invalid settlement identity/metadata')
        fields=('input_tokens','cache_read_input_tokens','cache_creation_input_tokens','output_tokens')
        if any(type(usage.get(k)) is not int or usage[k]<0 for k in fields):
            raise BudgetDenied('Incomplete usage; keep full reservation')
        inputs=sum(usage[k] for k in fields[:3]);charge=inputs*INPUT_NANO+usage['output_tokens']*OUTPUT_NANO
        with self.transaction() as value:
            if index>len(value['requests']):raise BudgetDenied('Unknown reservation')
            row=value['requests'][index-1]
            if row['status']!='RESERVED_UNKNOWN_USAGE':raise BudgetDenied('A reservation cannot be settled twice')
            if inputs>CONTEXT_TOKENS or usage['output_tokens']>row.get('output_token_cap',MAX_OUTPUT) or charge>row['charge_bound_nano']:
                raise BudgetDenied('Usage exceeds this request reservation')
            value['cash_bound_nano']-=row['charge_bound_nano']-charge
            row.update(status='SETTLED_USAGE_UPPER_BOUND',charge_bound_nano=charge,usage=usage,**metadata)
