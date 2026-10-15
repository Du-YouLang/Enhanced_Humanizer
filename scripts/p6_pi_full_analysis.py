"""Offline 128-cell Pi analysis. Never dispatches models or executes candidates."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import html
import json
from pathlib import Path
import statistics

PROFILES = ('P0', 'P1', 'P2', 'P3')
PROVIDERS = ('deepseek', 'subscription')
STATUSES = {'PASS', 'FAIL', 'INDETERMINATE', 'INFRA_FAIL', 'INFRA_RETRY_PENDING'}


def finite_measurement(value):
    import math
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def validate_input(data):
    rows = data['pi_rows']
    keys = [(r['task_id'], r['profile'], r['provider']) for r in rows]
    tasks = {r['task_id'] for r in rows}
    expected = {(t, p, m) for t in tasks for p in PROFILES for m in PROVIDERS}
    if len(tasks) != 16 or len(rows) != 128 or len(set(keys)) != 128 or set(keys) != expected:
        raise ValueError('Exactly 16 tasks x four profiles x two providers, no duplicates or redo samples')
    if Counter(r['cohort'] for r in rows) != {'retained_original16': 16, 'missing112': 112}:
        raise ValueError('Original16 and missing112 must remain distinct')
    for r in rows:
        if r['original_outcome'] not in STATUSES or r['official_status'] not in STATUSES:
            raise ValueError('Unknown outcome; missing evidence cannot become a pass')
        if r['original_outcome'] != r['official_status']:
            e = r.get('supplement')
            if not isinstance(e, dict) or not e.get('evidence_sha256') or e.get('head_commit') != r['head_commit'] or e.get('raw_result_sha256') != r['result_sha256']:
                raise ValueError('Changed verdict needs a bound supplement matching head and raw result')
            if r['original_outcome'].startswith('INFRA') and not e.get('authorized_same_role_recovery'):
                raise ValueError('Infrastructure rows cannot silently become successes or rerun samples')
    if len(data['main_rows']) != 96 or len({(r['task_id'], r['arm']) for r in data['main_rows']}) != 96:
        raise ValueError('Historical six-arm main table must contain96 distinct rows')
    ledger = data['ledger']
    if ledger['actual_cash_usd'] != 'unavailable':
        raise ValueError('No provider invoice evidence: actual cash must remain unavailable')
    if ledger['settled_requests'] + ledger['unknown_requests'] != ledger['deepseek_requests']:
        raise ValueError('Unknown reservations must remain in request total')
    total, unknown = Decimal(str(ledger['api_upper_bound_usd'])), Decimal(str(ledger['unknown_charge_bound_usd']))
    if not Decimal(0) <= unknown <= total <= Decimal(str(ledger['max_usd'])):
        raise ValueError('Invalid retained budget bounds')
    if not 0 <= ledger['deepseek_requests'] <= ledger['max_requests']:
        raise ValueError('Request cap exceeded')
    if data.get('supplemental_redo_count') != 1 or data.get('new_model_calls') != 0 or data.get('new_candidate_executions') != 0:
        raise ValueError('Reporting must preserve separate redo and execute no models/candidates')


def summarize(data):
    validate_input(data)
    rows = data['pi_rows']
    profiles = []
    for profile in PROFILES:
        for provider in PROVIDERS:
            group = [r for r in rows if (r['profile'], r['provider']) == (profile, provider)]
            counts = Counter(r['official_status'] for r in group)
            timing = [r['coding_and_public_seconds'] for r in group if finite_measurement(r.get('coding_and_public_seconds'))]
            public = [r for r in group if not r['task_id'].startswith('SCI-')]
            science = [r for r in group if r['task_id'].startswith('SCI-')]
            profiles.append({'profile': profile, 'provider': provider, 'total': len(group),
                             'PASS': counts['PASS'], 'FAIL': counts['FAIL'],
                             'INDETERMINATE': counts['INDETERMINATE'],
                             'INFRA': counts['INFRA_FAIL'] + counts['INFRA_RETRY_PENDING'],
                             'public_pass': sum(r['official_status'] == 'PASS' for r in public),
                             'science_pass': sum(r['official_status'] == 'PASS' for r in science),
                             'median_original_coding_and_public_seconds': statistics.median(timing) if timing else 'unavailable',
                             'coding_time_coverage': len(timing), 'total_end_to_end_seconds': 'unavailable',
                             'internal_provider_wire_for_subscription': 'UNVERIFIED' if provider == 'subscription' else 'RECORDED_PER_CELL'})
    ledger = dict(data['ledger'])
    ledger['settled_usage_charge_bound_usd'] = float(Decimal(str(ledger['api_upper_bound_usd'])) - Decimal(str(ledger['unknown_charge_bound_usd'])))
    ledger['remaining_upper_bound_usd'] = float(Decimal(str(ledger['max_usd'])) - Decimal(str(ledger['api_upper_bound_usd'])))
    return {'status': 'COMPLETE_ANALYSIS_WITH_ORIGINAL_FAILURES_AND_EVIDENCE_GAPS_RETAINED',
            'pi_tasks': 16, 'pi_cells': 128, 'profiles': profiles,
            'pi_raw_status_counts': dict(Counter(r['original_outcome'] for r in rows)),
            'pi_reviewed_status_counts': dict(Counter(r['official_status'] for r in rows)),
            'missing112_raw_counts': dict(Counter(r['original_outcome'] for r in rows if r['cohort'] == 'missing112')),
            'missing112_reviewed_counts': dict(Counter(r['official_status'] for r in rows if r['cohort'] == 'missing112')),
            'historical_main_status_counts': dict(Counter(r['official_status'] for r in data['main_rows'])),
            'ledger': ledger, 'supplemental_redo_count': 1,
            'new_model_calls': 0, 'new_candidate_executions': 0, 'raw_results_modified': False,
            'protocols_pooled_for_causal_claim': False, 'full_product_acceptance': False,
            'analysis_evidence_gaps': data['limitations']}


def markdown_report(data, summary):
    text = [
        '# P6完整覆盖补充分析与全系统结果（2026-10-16）', '',
        'Pi已覆盖16题×4个profile×2条供应商通道，共128个不同格。原两题16格与后来14题112格分别保留；112格中的85项续行全部执行结束。执行完成包含失败和基础设施未决，不表示全部模型成功。', '',
        '本表只使用冻结的原程序及绑定其身份的独立补充审核。修复我们造成的验收条件后才补充判定；没有替候选修代码、重跑完成模型、重置账本或混入单格网络重试作为第129个样本。', '',
        '## Pi完整16题', '',
        'P0=原生Pi，P1=Scientific Skills，P2=NeuroForge，P3=Research Loop。DeepSeek为原冻结请求模型deepseek-flash；订阅通道请求gpt-6.1-sol。profile是工作流配置，不是八种独立基础模型；供应商实际内部版本和订阅内部wire次数不可据请求名填造。', '',
        '| Profile | 通道 | 公共12题通过 | 科学4题通过 | 通过/16 | 失败 | 科学待判 | 基础设施未决 |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for r in summary['profiles']:
        text.append(f"| {r['profile']} | {r['provider']} | {r['public_pass']} | {r['science_pass']} | {r['PASS']}/16 | {r['FAIL']} | {r['INDETERMINATE']} | {r['INFRA']} |")
    text += ['', '原始128格：' + json.dumps(summary['pi_raw_status_counts'], ensure_ascii=False) + '。',
             '独立补充后的128格：' + json.dumps(summary['pi_reviewed_status_counts'], ensure_ascii=False) + '。原始行全部保持，不将未决从分母删除。', '',
             '| 任务 | P0 DS | P1 DS | P2 DS | P3 DS | P0 订阅 | P1 订阅 | P2 订阅 | P3 订阅 |',
             '|---|---|---|---|---|---|---|---|---|']
    by_key = {(r['task_id'], r['profile'], r['provider']): r['official_status'] for r in data['pi_rows']}
    for task in sorted({r['task_id'] for r in data['pi_rows']}):
        text.append('| ' + task + ' | ' + ' | '.join(by_key[task, p, m] for m in PROVIDERS for p in PROFILES) + ' |')
    text += ['', '## 科学判定与失败归因', '',
        '- PC-ALM：6份单种子复现补充通过；DS/P2报告将比例标为pp，DS/P3两处表头将BP减方法写成方法减BP，二者报告忠实性失败。两份数值/原独立复验通过仍保留，不能把报告问题叫算法失败。',
        '- EGL：5份完整补充通过。DS/P0旧KeyError经明确等价别名复核，18组原训练、旧权重复验、源码/报告/图表均通过。DS/P1/P2/P3在N20000/GD三种子过程曲线RMSE为6.2116/5.2760/4.1168pp，超过原1pp；终点准确率相同，不能抵消过程门。源码浮点运算写法不同是可能因素，未通过新对照证明因果；不改阈值、不倒推算法错误。',
        '- STROKE：8份各21项原检查通过；完整补充5通过、3项DS/P0/P1/P3输入契约失败。字符串false被bool转换为真，P3对缺失审查标记还默认为真；此为源码路径审阅发现。48幅保存数组图仅作视觉呈现，不替代数值评分；没有临床、患者组或PCI有效性结论。',
        '- 原GRANGER：7份源码/数值通过，DS/P3缺跨warp同步屏障仍失败。手工修复副本未给原模型补分；额外小ridge压力差异另列，不插入原冻结成绩。',
        '- 4项基础设施未决留在正式分母：原generic处理错误、订阅usage不可用、角色时限/网络与预算停止等按各自原回执记录，不统一改称过载或模型能力失败。另一次授权网络redo公开通过但隐藏格式化失败，单独保留1FAIL，不替换主格。', '',
        '## A–F主集的独立历史结果', '',
        '原Humanfia/DSH/Codex六臂仍为16题96格，65通过、22失败、9条件/证据待判定；128份原主集候选和16次轨迹敏感性并非新增独立题。这里复用已交付复核，不用Pi较新验收条件替旧程序补造历史训练计量或其他缺失证据。', '',
        '| 臂 | 系统 | 通过/16 | 失败 | 条件/证据待判定 |', '|---|---|---:|---:|---:|']
    for arm, r in data['historical_main_summary']['main']['counts'].items():
        text.append(f"| {arm} | {r['system']} | {r['PASS']}/16 | {r['FAIL']} | {r['PENDING']} |")
    text += ['', '原J0/J1/J3评分与J2/Jev地区凭据阻塞均保留。评分器不另算解题模型；未运行的Jev不算能力失败；没有OpenRouter或OpenAI API现金实验。', '',
        '## 时间、Token与预算', '',
        '时间表见summary.json的原编码与公开检查中位数及覆盖数。科学训练验收、恢复和角色编码分别计时；没有完整用户端到端时间就写unavailable，不将恢复后的局部耗时冒充整次训练或原任务总时长。订阅原过载后的同角色恢复保留单独记录，不能用缺失片段计算端到端排名。', '',
        f"累计DeepSeek请求{summary['ledger']['deepseek_requests']}，订阅预留{summary['ledger']['subscription_reservations']}。API保守上界USD{summary['ledger']['api_upper_bound_usd']:.6f} / {summary['ledger']['max_usd']:.0f}；实际扣款unavailable。",
        f"其中{summary['ledger']['settled_requests']}次已有用量的费用上界合计USD{summary['ledger']['settled_usage_charge_bound_usd']:.6f}；{summary['ledger']['unknown_requests']}次未知用量仍保留USD{summary['ledger']['unknown_charge_bound_usd']:.6f}预留。两者都不是供应商账单，不能把未知预留退款或当成已消费现金。", '',
        '有用量请求的累计归一化Token：' + json.dumps(summary['ledger']['observed_settled_token_totals'], ensure_ascii=False) + '。未知请求没有补0。input、cache_read、cache_creation按账本原分类分列；不把订阅预留算API调用或现金，不将不同共享路径费用相加成每个系统独立账单。', '',
        '## 可支持的结论与限制', '',
    ]
    text += ['- ' + x for x in data['limitations']]
    text += ['', '本报告完成分析与证据归档，不代表所有实验通过、科研假设成立或产品全部验收。旧结果、候选、协议和账本不改；新版P7安装/回滚另验，对外产品发布仍需用户确认。', '']
    return '\n'.join(text)


def write_report(data, destination):
    summary = summarize(data)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    content = markdown_report(data, summary)
    (destination / 'report.md').write_text(content, encoding='utf-8')
    (destination / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    (destination / 'analysis-data.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    groups = summary['profiles']
    fig, ax = plt.subplots(figsize=(12, 6))
    left = [0] * len(groups)
    for key, label, color in [('PASS', 'Reviewed PASS', '#237a57'), ('FAIL', 'FAIL', '#b33e47'), ('INDETERMINATE', 'Evidence pending', '#6a6b73'), ('INFRA', 'Infrastructure pending', '#c58a21')]:
        counts = [r[key] for r in groups]
        ax.barh(range(8), counts, left=left, label=label, color=color)
        left = [a + b for a, b in zip(left, counts)]
    ax.set(yticks=range(8), yticklabels=[f"{r['profile']} / {r['provider']}" for r in groups], xlim=(0, 16), xlabel='Distinct tasks (denominator includes unresolved infrastructure)', title='Pi: 16-task coverage, bound scientific supplements; descriptive only')
    ax.invert_yaxis()
    ax.legend(loc='upper center', bbox_to_anchor=(.5, -.16), ncol=2)
    fig.tight_layout()
    fig.savefig(destination / 'pi-reviewed-outcomes.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    ledger = summary['ledger']
    fig, ax = plt.subplots(figsize=(10, 3))
    for value, left, label, color in [(ledger['settled_usage_charge_bound_usd'], 0, 'Measured usage charge bound', '#237a57'), (ledger['unknown_charge_bound_usd'], ledger['settled_usage_charge_bound_usd'], 'Unknown usage reservations', '#c58a21'), (ledger['remaining_upper_bound_usd'], ledger['api_upper_bound_usd'], 'Remaining authorization', '#dddddd')]:
        ax.barh([0], [value], left=[left], label=f'{label}: ${value:.2f}', color=color)
    ax.set(xlim=(0, ledger['max_usd']), yticks=[], xlabel='USD authorization/bound; actual provider invoice unavailable', title='Cumulative ledger: no refunds, no reset, no per-system cost pooling')
    ax.legend(loc='upper center', bbox_to_anchor=(.5, -.3), ncol=1)
    fig.tight_layout()
    fig.savefig(destination / 'cumulative-budget-bound.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    doc = '<!doctype html><meta charset="utf-8"><title>P6 Pi full analysis</title><style>body{max-width:1100px;margin:2rem auto;padding:1rem;font:16px/1.7 sans-serif}img{width:100%}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>P6 Pi full analysis</h1><img src="pi-reviewed-outcomes.png" alt="Reviewed outcomes"><img src="cumulative-budget-bound.png" alt="Budget bound"><pre>' + html.escape(content) + '</pre>'
    (destination / 'report.html').write_text(doc, encoding='utf-8')
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = {'status': summary['status'], 'created_at': datetime.now(timezone.utc).isoformat(),
                'generator_sha256': sha(Path(__file__)), 'model_calls': 0, 'candidate_executions': 0,
                'files_sha256': {p.name: sha(p) for p in sorted(destination.iterdir()) if p.is_file()}}
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    if not args.output.resolve().is_relative_to(root / '.local-workbench'):
        p.error('Report output must stay in the private project folder')
    summary = write_report(json.loads(args.input.read_bytes()), args.output)
    print(json.dumps({'status': summary['status'], 'pi_counts': summary['pi_reviewed_status_counts'], 'models_started': 0}))


if __name__ == '__main__':
    main()
