"""Offline paired-guidance reporting. Never imports a model, harness or executor."""
import argparse
from collections import Counter
import hashlib
import html
import json
from pathlib import Path
import statistics

from p6_guidance_protocol import TASKS
from unified_benchmark_analysis import add_observed, exact_p, normalized_codex_usage

METHODS = ('DS-Initial', 'DS-Sol-code-tests', 'DS-Sol-code-tests-trace')
AFFECTED = frozenset(TASKS[6:10])
FIELDS = ('input', 'cache_read', 'cache_write', 'output', 'reasoning')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def observed_total(values):
    result = add_observed(values)
    inputs = [result[k] for k in ('input', 'cache_read', 'cache_write')]
    result['input_including_cache'] = sum(inputs) if all(v is not None for v in inputs) else None
    result['total_excluding_reasoning_subset'] = (
        result['input_including_cache'] + result['output']
        if result['input_including_cache'] is not None and result['output'] is not None else None)
    return result


def subscription_usage(workers):
    """A resumed session has two explicit non-overlapping segments, not two sessions."""
    entries = {}; sessions = set(); missing = []
    for worker in workers:
        usage = worker.get('usage') or []
        if not usage:
            missing.append(worker['scope'])
        for entry in usage:
            session = entry.get('session_id')
            normalized = normalized_codex_usage(entry.get('usage'))
            if not session or normalized is None:
                raise ValueError('Observed subscription entry lacks usable session counters')
            segment = entry.get('usage_segment', 'COMPLETE_SESSION')
            if segment not in ('COMPLETE_SESSION', 'BEFORE_USER_SHUTDOWN', 'RESUMED_DELTA'):
                raise ValueError('Unknown subscription usage segment')
            key = session, segment
            if key in entries:
                raise ValueError('Duplicate subscription token segment')
            entries[key] = normalized; sessions.add(session)
    for session in sessions:
        segments = {key[1] for key in entries if key[0] == session}
        if segments not in ({'COMPLETE_SESSION'}, {'BEFORE_USER_SHUTDOWN', 'RESUMED_DELTA'}):
            raise ValueError('Incomplete or overlapping resumed-session accounting')
    values = list(entries.values()) if workers else [dict.fromkeys(FIELDS, 0)]
    return {'observed': observed_total(values), 'known_sessions': len(sessions),
            'observed_segments': len(entries), 'missing_roles': missing, 'complete': not missing}


def deepseek_usage(requests):
    known = [r for r in requests if r['status'] == 'SETTLED_USAGE_UPPER_BOUND']
    values = [dict(zip(FIELDS, (r['usage']['input_tokens'], r['usage']['cache_read_input_tokens'],
                r['usage']['cache_creation_input_tokens'], r['usage']['output_tokens'], None))) for r in known]
    if not requests:
        values = [dict.fromkeys(FIELDS, 0)]
    unknown = len(requests) - len(known)
    return {'observed': observed_total(values), 'requests': len(requests), 'known_requests': len(known),
            'unknown_requests': unknown, 'complete': unknown == 0,
            'charge_bound_usd': sum(r['charge_bound_nano'] for r in requests) / 1e9}


def load_science(folder):
    folder = Path(folder); result = {}; evidence = {}
    def read(name):
        evidence[name] = sha(folder / name)
        return json.loads((folder / name).read_bytes())
    pc_names = ('initial', 'code-tests', 'code-tests-trace')
    for method, branch in zip(METHODS, pc_names):
        p = read('guidance-pc-' + branch + '-scientific-content-review-20261017.private.json')
        if p['status'] != 'SCIENTIFIC_CONTENT_PASS_TELEMETRY_RECONCILIATION_PENDING':
            raise ValueError('PC scientific review not closed')
        result['SCI-PC-ALM', method] = {'formal': 'INDETERMINATE', 'quality_without_timing': 'PASS',
            'numeric': 'PASS', 'reason': 'SCIENTIFIC_CONTENT_PASS_CLOCK_BASES_UNRESOLVED', 'evidence': evidence.copy()}
    egl = read('guidance-egl-scientific-content-review-20261017.private.json')
    if egl['status'] != 'SCIENTIFIC_CONTENT_PASS_TELEMETRY_RECONCILIATION_PENDING':
        raise ValueError('EGL scientific review not closed')
    for row in egl['rows']:
        result['SCI-EGL', row['method']] = {'formal': 'INDETERMINATE', 'quality_without_timing': 'PASS',
            'numeric': 'PASS', 'head': row['head'], 'reason': 'SAVED_SCHEMA_SUPPLEMENT_PASS_CLOCK_BASES_UNRESOLVED'}
    stroke = read('guidance-stroke-unit-adjudicated-20261017.private.json')
    gc = read('guidance-granger-source-adjudicated-20261017.private.json')
    for review, task, reason in ((stroke, 'SCI-STROKE', 'EXTRA_UNIT_OUTSIDE_EXPLICIT_FROZEN_WHITELIST'),
                                (gc, 'SCI-GRANGER-GPU', 'SHARED_MEMORY_COPY_RIDGE_SYNCHRONIZATION')):
        for method, role in zip(METHODS, ('initial-ds', 'code-tests-ds', 'code-tests-trace-ds')):
            row = next(x for x in review['rows'] if x['role'] == role)
            formal = 'PASS' if row['formal_status'] == 'PASS' else 'FAIL'
            result[task, method] = {'formal': formal, 'quality_without_timing': formal, 'numeric': 'PASS',
                                   'head': row['head'], 'reason': reason if formal == 'FAIL' else 'SOURCE_AND_NUMERIC_PASS'}
    if len(result) != 12:
        raise ValueError('Exactly twelve scientific program reviews required')
    return result, evidence


def paired(rows, left, right, field='quality_without_timing', exclude_affected=False):
    a = {r['task_id']: r for r in rows if r['method'] == left}
    b = {r['task_id']: r for r in rows if r['method'] == right}
    if set(a) != set(b):
        raise ValueError('Paired task identities differ')
    comparable = [t for t in a if not (exclude_affected and t in AFFECTED)
                  and a[t][field] in ('PASS', 'FAIL') and b[t][field] in ('PASS', 'FAIL')]
    lonly = [t for t in comparable if a[t][field] == 'PASS' and b[t][field] != 'PASS']
    ronly = [t for t in comparable if b[t][field] == 'PASS' and a[t][field] != 'PASS']
    ratios = [a[t]['coding_public_seconds'] / b[t]['coding_public_seconds'] for t in comparable]
    return {'left': left, 'right': right, 'view': field, 'exclude_helper_affected': exclude_affected,
            'comparable_tasks': len(comparable), 'left_only': lonly, 'right_only': ronly,
            'both_pass': sum(a[t][field] == b[t][field] == 'PASS' for t in comparable),
            'paired_exact_p_exploratory': exact_p(len(lonly), len(ronly)),
            'median_left_over_right_coding_ratio': statistics.median(ratios) if ratios else None}


def build(intake, science):
    receipt = intake['receipt']
    if receipt['completed_tasks'] != 16 or receipt['status'] != 'GUIDANCE_SHUTDOWN_CONTINUATION_COMPLETED':
        raise ValueError('Complete final receipt required')
    tasks = {t['task_id']: t for t in receipt['results']}
    if set(tasks) != set(TASKS):
        raise ValueError('All sixteen frozen tasks required')
    workers = {}; all_scopes = set()
    for scope, w in intake['workers'].items():
        key = tuple(scope.split('/')[2:])
        if key in workers or w['status'] != 'COMPLETED':
            raise ValueError('Duplicate logical role or unfinished worker')
        workers[key] = w; all_scopes.add(scope); all_scopes.update(w.get('additional_accounting_scopes') or [])
    if len(workers) != 80:
        raise ValueError('Exactly eighty completed logical roles required')
    if any(r['experiment'] not in all_scopes for r in intake['requests'] + intake['subscriptions']):
        raise ValueError('Unattributed experiment accounting scope')
    supplements = {(r['task_id'], r['method']): r for r in receipt['supplements']}
    rows = []
    for tid in TASKS:
        task = tasks[tid]
        for method in METHODS:
            raw = next(r for r in task['rows'] if r['method'] == method)
            branch = None if method == 'DS-Initial' else method.removeprefix('DS-Sol-')
            names = ['initial-ds'] + ([branch + '-mentor', branch + '-ds'] if branch else [])
            selected = [workers[tid, name] for name in names]
            scopes = {w['scope'] for w in selected}
            scopes.update(s for w in selected for s in w.get('additional_accounting_scopes') or [])
            requests = [r for r in intake['requests'] if r['experiment'] in scopes]
            if any(not any(r['experiment'] == w['scope'] for r in requests) for w in selected if not w['scope'].endswith('-mentor')):
                raise ValueError('DS role lacks ledger request evidence')
            public = task['initial']['test_report']['elapsed_seconds']
            if branch:
                public += task['branches'][branch]['candidate']['test_report']['elapsed_seconds']
            formal = quality = numeric = raw['outcome']; reason = 'ORIGINAL_PUBLIC_HIDDEN_ACCEPTANCE'
            if (tid, method) in supplements:
                sup = supplements[tid, method]
                if sup['raw_original_outcome'] != raw['outcome'] or sup['model_replays'] != 0:
                    raise ValueError('Supplement is not an unchanged original program')
                formal = quality = numeric = sup['supplemental_quality_outcome']
                reason = 'UNCHANGED_PROGRAM_HELPER_SUPPLEMENT_PROCESS_AFFECTED'
            if tid.startswith('SCI-'):
                review = science[tid, method]
                if review.get('head') and review['head'] != raw['candidate']['head_commit']:
                    raise ValueError('Scientific review binds another program')
                formal, quality, numeric = (review[k] for k in ('formal', 'quality_without_timing', 'numeric'))
                reason = review['reason']
            row = {'task_id': tid, 'method': method, 'raw_status': raw['outcome'], 'formal_status': formal,
                'quality_without_timing': quality, 'numeric_only_status': numeric, 'reason': reason,
                'helper_process_affected': tid in AFFECTED, 'scientific': tid.startswith('SCI-'),
                'head': raw['candidate']['head_commit'], 'frozen': raw['frozen'],
                'model_seconds': sum(w['wall_seconds'] for w in selected), 'public_seconds': public,
                'coding_public_seconds': sum(w['wall_seconds'] for w in selected) + public,
                'acceptance_seconds': raw['acceptance']['elapsed_seconds'],
                'acceptance_speed_comparable': tid not in ('SCI-PC-ALM', 'SCI-EGL'),
                'ds': deepseek_usage(requests), 'openai': subscription_usage([w for w in selected if w['scope'].endswith('-mentor')]),
                'scopes': sorted(scopes), 'shared_initial_projection': branch is not None,
                'subscription_reservations': sum(r['experiment'] in scopes for r in intake['subscriptions'])}
            rows.append(row)
    summaries = []
    for method in METHODS:
        subset = [r for r in rows if r['method'] == method]
        value = {'method': method, 'tasks': 16,
            'formal': dict(Counter(r['formal_status'] for r in subset)),
            'quality_without_timing': dict(Counter(r['quality_without_timing'] for r in subset)),
            'numeric_only': dict(Counter(r['numeric_only_status'] for r in subset)),
            'raw': dict(Counter(r['raw_status'] for r in subset)),
            'coding_public_median_seconds': statistics.median(r['coding_public_seconds'] for r in subset),
            'coding_public_sum_seconds': sum(r['coding_public_seconds'] for r in subset),
            'complete_model_public_time_cells': 16, 'complete_acceptance_time_comparable_cells': 14}
        for provider in ('ds', 'openai'):
            parts = [r[provider] for r in subset]
            value[provider] = {'observed': observed_total([p['observed'] for p in parts]),
                'complete_cells': sum(p['complete'] for p in parts),
                'requests': sum(p.get('requests', 0) for p in parts),
                'unknown_requests': sum(p.get('unknown_requests', 0) for p in parts),
                'known_sessions': sum(p.get('known_sessions', 0) for p in parts),
                'observed_segments': sum(p.get('observed_segments', 0) for p in parts),
                'charge_bound_usd': sum(p.get('charge_bound_usd', 0) for p in parts)}
        summaries.append(value)
    pairs = [(METHODS[1], METHODS[0]), (METHODS[2], METHODS[0]), (METHODS[1], METHODS[2])]
    comparisons = [paired(rows, l, r, field, exclude) for l, r in pairs
                   for field in ('formal_status', 'quality_without_timing') for exclude in (False, True)]
    return {'status': 'COMPLETE_EXECUTION_SCIENTIFIC_ADJUDICATION_WITH_EXPLICIT_TIMING_GAPS', 'task_count': 16,
        'logical_roles': 80, 'cell_count': 48, 'methods': summaries, 'rows': rows, 'comparisons': comparisons,
        'unique_paid_activity': {'ds': deepseek_usage(intake['requests']),
            'openai': subscription_usage([w for w in workers.values() if w['scope'].endswith('-mentor')]),
            'subscription_reservations': len(intake['subscriptions'])}, 'global_budget': intake['global_budget'],
        'raw_results_modified': False, 'new_models_by_analysis': 0,
        'interpretation': ['Shared initial DS is billed once; each guided method projection includes it and projections cannot be added as a bill.',
            'Initial versus guided continuation also adds DS compute; improvements cannot be attributed to Sol alone without a DS-only continuation control.',
            'All low; one paired trial per task; heterogeneous sixteen tasks, no equal-token budget or general superiority/speed proof.',
            'Four helper-affected tasks have unchanged-program quality supplements but are excluded in strict process comparisons.',
            'Numerical-only success intentionally ignores source/input defects; quality-without-timing omits only unresolved timing evidence. Formal view preserves six timing-indeterminate cells.',
            'Coding/public times are recorded worker-role boundaries; PC/EGL acceptance clock disagreements prevent complete end-to-end speed comparison. Shutdown offline time excluded; old 43-second mentor debit included.',
            'DeepSeek input ledger fields exclude cache; Codex raw input includes it and is normalized once. Reasoning is an output subset, never added twice. Unknown DS usage is a lower-bound gap, not zero.',
            'Development, human review and Luna monitoring conversations are outside the experimental supplier ledger; their unavailable tokens are not fabricated as zero.']}


def render(data):
    esc = html.escape
    def table(headers, records):
        return '<table><thead><tr>' + ''.join('<th>' + esc(str(x)) + '</th>' for x in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + esc(str(x)) + '</td>' for x in row) + '</tr>' for row in records) + '</tbody></table>'
    summary = []
    for m in data['methods']:
        ds, oa = m['ds']['observed'], m['openai']['observed']
        summary.append((m['method'], str(m['formal'].get('PASS', 0)) + '/16', m['formal'].get('INDETERMINATE', 0),
            str(m['quality_without_timing'].get('PASS', 0)) + '/16', round(m['coding_public_median_seconds'], 1),
            ds['input_including_cache'], ds['output'], oa['input_including_cache'], oa['output'], m['ds']['unknown_requests']))
    page = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>16题 DS–Sol指导实验终稿</title><style>body{font:16px system-ui;max-width:1500px;margin:32px auto;padding:24px;color:#17293d;background:#f6f8fb}h1,h2{color:#12233a}table{border-collapse:collapse;width:100%;background:white;margin:20px 0;font-size:14px}th,td{padding:10px;border:1px solid #d8e0e9;text-align:left}th{background:#e9eff6}li{margin:8px 0}img{max-width:100%}.note{padding:16px;background:#fff1cd}details{margin:20px 0}</style><h1>DS求解 → Sol文字指导 → DS续改：16题配对验证</h1><p>16/16题、80/80角色执行完毕；原始回执完整保留。代码/测试指导改善了三题，额外轨迹指导本轮没有提高成功数量。计时与输入/源码缺陷分别列示。</p><div class="note">正式确认通过数为8 / 11 / 8，另各2题计时未决；仅排除计时争议的质量视图为10 / 13 / 10。两种视图都不能把全部执行完成解释为全部成功。额外DS时间与导师作用尚未分离。</div>'
    page += table(['方法', '正式PASS', '计时未决', '排除计时的质量PASS', '编码+公开检查中位秒', 'DS输入含缓存', 'DS输出', 'OpenAI输入含缓存', 'OpenAI输出', '未知DS请求'], summary)
    page += '<p>DS Token含所有已记录请求及重试，未知usage只计保守预算、不填零；OpenAI为现有订阅可观测Token，不是API扣费。共享首轮在真实活动中仅算一次，三行资源投影不能相加。逐题完整字段和缓存分解见 <a href="analysis-data.json">analysis-data.json</a>。</p>'
    if data.get('plot_path'):
        page += '<img src="' + esc(data['plot_path'], quote=True) + '" alt="Paired success and timing chart">'
    page += '<h2>逐题结果</h2>'
    matrix = []
    for tid in TASKS:
        cells = [next(r for r in data['rows'] if r['task_id'] == tid and r['method'] == m) for m in METHODS]
        matrix.append((tid, *[r['formal_status'] for r in cells], '助手路径影响，质量补验另列' if tid in AFFECTED else '原同条件；科研另含源码/计量核验'))
    page += table(['任务', *METHODS, '条件'], matrix)
    page += '<h2>结论与边界</h2><ul>' + ''.join('<li>' + esc(x) + '</li>' for x in data['interpretation']) + '</ul><p>GRANGER：两个导师都指出同一同步缺陷，代码/测试分支落实了修改，轨迹分支只增加测试而保留缺陷。轨迹能帮助诊断，但并不保证后续Agent执行建议。STROKE：63项原检查及科学数值内容通过，三份均额外接受冻结白名单以外的μV，因此完整输入契约失败。PC/EGL科学内容通过，正式结果因计时差异仍待判；不修改原失败/未决矩阵。</p>'
    if data.get('legacy_methods'):
        page += '<h2>与之前主实验及Pi的统一目录</h2><p>以下14方法为原224格冻结回顾，本轮另加3方法48格，共17方法、同16题272格。运行批次与预算不同，仅作描述；不按跨轮成功率推断因果或普遍排名。旧报告和数据未修改。</p>'
        page += table(['历史方法', '原已核验PASS/16', '编码中位秒', '时间覆盖'], [(m['method'], str(m['success']) + '/16', round(m['selected_coding_median_seconds'], 1) if m['selected_coding_median_seconds'] is not None else '缺失', m['time_coverage']) for m in data['legacy_methods']])
    if data.get('scientific_figures'):
        page += '<details><summary>查看独立科学审阅图（只使用保存产物）</summary>'
        for item in data['scientific_figures']:
            page += '<p>' + esc(item['label']) + '</p><img src="' + esc(item['path'], quote=True) + '" alt="' + esc(item['label'], quote=True) + '">'
        page += '</details>'
    return page + '</html>'


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--intake', type=Path, required=True)
    parser.add_argument('--reviews-dir', type=Path, required=True); parser.add_argument('--legacy-data', type=Path)
    parser.add_argument('--output', type=Path, required=True); args = parser.parse_args()
    science, evidence = load_science(args.reviews_dir)
    data = build(json.loads(args.intake.read_bytes()), science)
    data['evidence_sha256'] = evidence; data['intake_sha256'] = sha(args.intake)
    if args.legacy_data:
        legacy = json.loads(args.legacy_data.read_bytes())
        if legacy['cell_count'] != 224 or legacy['method_count'] != 14:
            raise ValueError('Unchanged 224-cell baseline required')
        data['legacy_methods'] = legacy['methods']; data['legacy_rows'] = legacy['rows']
        data['legacy_data_sha256'] = sha(args.legacy_data)
        data['unified_method_count'] = 17; data['unified_cell_count'] = 272
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'analysis-data.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf8')
    (args.output / 'report.html').write_text(render(data), encoding='utf8')
    print(json.dumps({'output': str(args.output), 'methods': data['methods'], 'unique_paid_activity': data['unique_paid_activity']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
