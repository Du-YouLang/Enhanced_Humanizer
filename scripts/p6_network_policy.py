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


class NetworkCheckRequired(RuntimeError):
    """Five consecutive transient failures; no model failure is inferred."""


class NetworkRetryPending(RuntimeError):
    """Recovery cannot finish within the existing role/aggregate budget."""


def enabled(config):
    return config.get('network_recovery_revision') == REVISION


def validate(config):
    if not enabled(config) or any(type(config.get(k)) is not type(v) or config[k] != v for k, v in POLICY.items()):
        raise ValueError('Exact human-authorized request/recovery policy required')
    return config
