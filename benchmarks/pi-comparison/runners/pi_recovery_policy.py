"""Authorize only unfinished provider-overload checkpoints, never fresh trials."""
import math
import re


def overload_bounds(worker, role_seconds, previous_recoveries=()):
    if worker.get('status') not in ('INFRA_FAIL','INFRA_RETRY_PENDING'):
        raise ValueError('Only an infrastructure failure can be supplemented')
    spent=max(worker.get('wall_seconds',float('nan')),worker.get('elapsed_seconds',float('nan')))
    dispatches=worker.get('sdk_dispatches')
    if not math.isfinite(spent) or spent<0 or type(dispatches) is not int or dispatches<1:
        raise ValueError('Exact elapsed and dispatch receipts required')
    for old in previous_recoveries:
        spent+=old['wall_seconds'];dispatches+=old['sdk_dispatches']
    seconds=math.floor(role_seconds-spent);requests=1000-dispatches
    if seconds<=0 or requests<=0:raise ValueError('Original role allowance is exhausted')
    return {'role_seconds_remaining':seconds,'role_requests_remaining':requests,
            'prior_role_seconds':spent,'prior_sdk_dispatches':dispatches,
            'authorized_role_seconds':role_seconds,'authorized_role_requests':1000}


def is_overload_message(message):
    text=str(message.get('errorMessage',''))
    return (message.get('stopReason')=='error' and
            not re.search(r'insufficient_quota|usage_limit|spend_limit|billing|authentication|invalid.api.key',text,re.I) and
            bool(re.search(r'server_is_overloaded|server_overloaded|overloaded',text,re.I)))


def validate_runtime_recovery(value, role_seconds):
    if not isinstance(value,dict) or value.get('authorization')!='USER_PROVIDER_OVERLOAD_RETRY_20261014':
        raise ValueError('Explicit provider-overload authorization required')
    if value.get('authorized_role_seconds') not in (900,1200) or value.get('authorized_role_requests')!=1000:
        raise ValueError('Original role limits changed')
    if not 0<role_seconds<=value['authorized_role_seconds'] or not 0<value.get('role_requests_remaining',0)<=1000:
        raise ValueError('No remaining original allowance')
    if value.get('prior_consecutive_failures') not in range(5):raise ValueError('Invalid consecutive failures')
    return value
