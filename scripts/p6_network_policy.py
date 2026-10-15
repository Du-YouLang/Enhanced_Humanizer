"""Prospective human-authorized transport recovery; historical policies stay fixed."""

REVISION = 'USER_APPROVED_2026-10-12_ROLE1000_REQUEST600_NETWORK5'
POLICY = {
    'network_recovery_revision': REVISION,
    'per_role_inference_requests': 1000,
    'per_request_timeout_seconds': 600,
    'network_consecutive_failure_limit': 5,
    'network_retry_backoff_seconds': [1, 2, 4, 8],
    'automatic_retry_after_infrastructure_failure': True,
    'network_retry_scope': 'FIXED_ALLOWED_PROVIDER_REQUEST_ONLY',
    'network_partial_stream_policy': 'BUFFER_UNTIL_COMPLETE_NO_DUPLICATE_TOOLS',
}

# Transport-only successor. Existing budgets and frozen runs retain POLICY.
RETRY10_REVISION = 'USER_APPROVED_2026-10-15_DEEPSEEK_NETWORK10'
RETRY10_POLICY = {**POLICY,
    'network_recovery_revision': RETRY10_REVISION,
    'network_consecutive_failure_limit': 10,
    'network_retry_backoff_seconds': [2, 4, 8, 16, 30, 45, 60, 60, 60],
}


class NetworkCheckRequired(RuntimeError):
    """Five consecutive transient failures; no model failure is inferred."""


class NetworkRetryPending(RuntimeError):
    """Recovery cannot finish within the existing role/aggregate budget."""


def enabled(config):
    return config.get('network_recovery_revision') == REVISION


def validate(config):
    policy = RETRY10_POLICY if config.get('network_recovery_revision') == RETRY10_REVISION else POLICY
    if config.get('network_recovery_revision') != policy['network_recovery_revision'] or any(type(config.get(k)) is not type(v) or config[k] != v for k, v in policy.items()):
        raise ValueError('Exact human-authorized request/recovery policy required')
    return config


def retry10_transport(value):
    """A separately pinned transport amendment, not a new ledger budget."""
    if value != RETRY10_POLICY or any(type(value.get(k)) is not type(v) for k,v in RETRY10_POLICY.items()):
        raise ValueError('Exact prospective DeepSeek retry10 policy required')
    return dict(value)
