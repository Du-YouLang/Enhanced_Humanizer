"""Exact never-started Pi suffix authorized on 2026-10-15; no trial replay."""
REVISION='USER_APPROVED_2026-10-15_CUMULATIVE_USD250_PI85_UNSTARTED'
SCOPE='ONLY_REMAINING85_UNSTARTED_PI_CELLS'
TASKS=('BIP-black-1','BIP-black-3','BIP-black-4','BIP-black-5','BIP-black-6',
 'SWEL-psf__requests-1963','SWEL-psf__requests-2148','SWEL-pytest-dev__pytest-11143',
 'SWEL-pytest-dev__pytest-11148','SWEL-sympy__sympy-11400','SWEL-sympy__sympy-11870',
 'SCI-PC-ALM','SCI-STROKE','SCI-EGL')


def allowed_cells():
    return [{'task_id':t,'profile':p,'provider':v,'repetition':0}
            for t in TASKS for v in ('deepseek','subscription') for p in ('P0','P1','P2','P3')][27:]


def allowed_scope(experiment,provider):
    import re
    prefix=r'PI_FORMAL/formal-full-compare-[0-9TZ]+/'
    for c in allowed_cells():
        if c['provider']==provider and re.fullmatch(prefix+re.escape(c['task_id']+'-'+c['profile']+'-'+provider),experiment):
            return True
    return False
