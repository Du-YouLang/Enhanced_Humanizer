"""One exact fresh trial explicitly authorized after the original role expired."""
AUTH='USER_NETWORK_REDO_BLACK5_P1_20261015'
CELL={'task_id':'BIP-black-5','profile':'P1','provider':'deepseek','repetition':0}
ORIGINAL='formal-full-compare-20261015T012431Z'


def validate_redo(plan,original):
    if (plan.get('authorization')!=AUTH or plan.get('cell')!=CELL or plan.get('original_run')!=ORIGINAL
            or original.get('cell')!=CELL or original.get('outcome')!='INFRA_RETRY_PENDING'
            or original.get('role_seconds')!=900 or plan.get('fresh_role_seconds')!=900
            or type(plan.get('fresh_role_seconds')) is not int or plan.get('fresh_role_requests')!=1000
            or type(plan.get('fresh_role_requests')) is not int or plan.get('maximum_new_trials')!=1
            or type(plan.get('maximum_new_trials')) is not int
            or plan.get('cumulative_caps')!={'deepseek_requests':10000,'api_cash_usd':200}
            or plan.get('original_result_preserved') is not True or plan.get('external_release_authorized') is not False):
        raise ValueError('Only the explicitly authorized Black5/P1/DeepSeek fresh trial is allowed')
    return plan
