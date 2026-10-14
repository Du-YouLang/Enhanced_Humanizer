"""Offline, receipt-backed P6 analysis. This module never launches models or tests."""
import argparse
from collections import Counter
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import statistics
from datetime import datetime,timedelta,timezone

ROOT=Path(__file__).resolve().parents[1]
ARMS=tuple('ABCDEF')
OUTCOMES={'PASS','FAIL','TIMEOUT','INFRA_FAIL','INDETERMINATE'}


def validate_input(data):
    rows=data['rows']
    if len(rows)!=96 or len({(r['task_id'],r['arm']) for r in rows})!=96:
        raise ValueError('Exactly 96 distinct frozen task/arm cells required')
    tasks={r['task_id'] for r in rows}
    if len(tasks)!=16 or any({r['arm'] for r in rows if r['task_id']==t}!=set(ARMS) for t in tasks):
        raise ValueError('Complete sixteen-task A-F coverage required')
    for row in rows:
        if row['outcome'] not in OUTCOMES or row['original_outcome'] not in OUTCOMES:
            raise ValueError('Unknown outcome')
        if row['outcome']!=row['original_outcome'] and not re.fullmatch('[0-9a-f]{64}',row.get('adjudication_sha256') or ''):
            raise ValueError('Changed verdict needs an explicit supplemental receipt')
        for key in ('receipt_sha256','contract_sha256','manifest_sha256'):
            if not re.fullmatch('[0-9a-f]{64}',row.get(key,'')):
                raise ValueError('Exact provenance required: '+key)
        for value in row['metrics'].values():
            if isinstance(value,(float,int)) and (isinstance(value,bool) or not math.isfinite(value) or value<0):
                raise ValueError('Invalid measurement')
    budget=data['budget']
    if sum(g['requests'] for g in budget['groups'].values())!=budget['requests']:
        raise ValueError('Request groups must reconcile without duplication')
    if not math.isclose(sum(g['api_upper_bound_usd'] for g in budget['groups'].values()),budget['api_upper_bound_usd'],abs_tol=1e-8):
        raise ValueError('Budget groups must reconcile to the original cumulative ledger')
    if budget['actual_api_cash_usd'] is not None:
        raise ValueError('This cohort has no verified invoice; do not invent billed cash')
    if data['models_started'] or data['whole_task_replays'] or data['github_operations']:
        raise ValueError('This is a read-only analysis scope')
    return data


def measured(values):
    return [v for v in values if type(v) in (int,float) and math.isfinite(v)]


def wilson(success,total):
    if not total:return None
    z=1.959963984540054; p=success/total; d=1+z*z/total
    center=(p+z*z/(2*total))/d
    radius=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/d
    return [max(0.,center-radius),min(1.,center+radius)]


def summarize(data):
    validate_input(data); rows=data['rows']; stats={}
    for arm in ARMS:
        group=[r for r in rows if r['arm']==arm];success=sum(r['outcome']=='PASS' for r in group)
        public=[r for r in group if r['family']=='public'];science=[r for r in group if r['family']=='scientific']
        seconds=measured(r['metrics']['end_to_end_seconds'] for r in group)
        costs=measured(r['metrics']['api_upper_bound_usd'] for r in group)
        stats[arm]={'accepted':success,'total':len(group),'original_accepted':sum(r['original_outcome']=='PASS' for r in group),
                    'public_accepted':sum(r['outcome']=='PASS' for r in public),'public_total':len(public),
                    'scientific_accepted':sum(r['outcome']=='PASS' for r in science),'scientific_total':len(science),
                    'descriptive_wilson95':wilson(success,len(group)),
                    'median_recorded_path_seconds':statistics.median(seconds) if seconds else None,'path_seconds_coverage':len(seconds),
                    'sum_path_api_bound_usd':sum(costs) if len(costs)==len(group) else None,
                    'path_api_bound_per_acceptance_usd':sum(costs)/success if success and len(costs)==len(group) else None,
                    'sum_path_subscription_reservations':sum(r['metrics']['subscription_turns'] for r in group),
                    'token_coverage':sum(type(r['metrics']['input_tokens']) is int for r in group)}
    indexed={(r['task_id'],r['arm']):r for r in rows}; paired={}
    for left,right in (('B','A'),('C','A'),('C','B'),('E','A'),('F','D'),('F','C')):
        counts=Counter(('both_accepted' if indexed[t,left]['outcome']==indexed[t,right]['outcome']=='PASS' else
                        'left_only' if indexed[t,left]['outcome']=='PASS' else
                        'right_only' if indexed[t,right]['outcome']=='PASS' else 'neither_accepted') for t in {r['task_id'] for r in rows})
        paired[left+'_vs_'+right]={k:counts[k] for k in ('both_accepted','left_only','right_only','neither_accepted')}
    judge_stats={}
    for jid in ('J0','J1','J2','J3'):
        group=[j for j in data['judges'] if j['judge']==jid and j['pool']=='original' and j['family']=='public']
        complete=[j for j in group if j['status']=='COMPLETED'];available=[j for j in complete if j['pass_available']]
        times=measured(j['seconds'] for j in complete)
        judge_stats[jid]={'status_counts':dict(Counter(j['status'] for j in group)),
                          'selected_acceptance_count':sum(j['selected_acceptance']=='PASS' for j in complete),
                          'completed':len(complete),'pass_available_completed':len(available),
                          'missed_available_pass':sum(j['selected_acceptance']!='PASS' for j in available),
                          'trace_selection_changed':sum(j['selected']!=j['full_trace_selected'] for j in complete if j['full_trace_status']=='COMPLETED'),
                          'trace_comparable':sum(j['full_trace_status']=='COMPLETED' for j in complete),
                          'median_seconds':statistics.median(times) if times else None}
    merge=data['merges']
    return {'arms':stats,'paired_acceptance':paired,'judges_public_original_pool':judge_stats,
            'merge':{'best_accepted':sum(m['best_acceptance']=='PASS' for m in merge),
                     'with_m_accepted':sum(m['with_m_acceptance']=='PASS' for m in merge),
                     'm_accepted':sum(m['m_acceptance']=='PASS' for m in merge),
                     'm_pass_when_no_original_pass':sum(m['m_acceptance']=='PASS' and not m['any_original_pass'] for m in merge),
                     'all_originals_failed_visible':sum(m['all_originals_failed_visible'] for m in merge),
                     'all_originals_failed_hidden':sum(not m['any_original_pass'] for m in merge)},
            'raw_outcomes':dict(Counter(r['original_outcome'] for r in rows)),
            'reviewed_outcomes':dict(Counter(r['outcome'] for r in rows))}


def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'---|'*len(headers),
                      *['| '+' | '.join(str(v) for v in row)+' |' for row in rows]])


def fmt(value,digits=2):
    return 'unavailable' if value is None or value=='unavailable' else f'{value:,.{digits}f}'


def document(data,summary):
    rows=data['rows']; budget=data['budget']; tasks=list(dict.fromkeys(r['task_id'] for r in rows))
    indexed={(r['task_id'],r['arm']):r for r in rows};a=summary['arms'];j=summary['judges_public_original_pool'];m=summary['merge']
    stamp=datetime.fromisoformat(data['created_at']).astimezone(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S +08:00')
    lines=['# P6 本地分析报告','', '数据与诊断截点：'+stamp+'。','',
        '本报告完成本轮已有证据的分析交付；不表示全部系统、科研任务或产品需求通过验收。16题A–F共96格及16次同池完整轨迹敏感性均已收束，保留全部负结果。除已明确记录的GRANGER补充源码/数值裁决外，原判定不改写；本分析未调用模型、未整题重跑、未操作GitHub。','',
        '## 主要结果','',
        table(['系统','通过/16','公共/12','科研/4','描述性95% Wilson区间','原始通过数'],
              [[arm,f"{a[arm]['accepted']}/16",f"{a[arm]['public_accepted']}/12",f"{a[arm]['scientific_accepted']}/4",
                '–'.join(f'{v:.1%}' for v in a[arm]['descriptive_wilson95']),a[arm]['original_accepted']] for arm in ARMS]),'',
        'A=原生DSH/DS；B=DS三候选+公开测试选优；C=DS增强器；D=原生Codex/Sol；E=原生DS与Sol轮换；F=增强器与Sol轮换。C/F有更多角色和额外订阅调用。区间仅描述这16个便利样本的比例，不是独立随机总体的效应保证；六臂共享任务及N3池，不能视为96个独立样本。','',
        '![逐任务验收](outcomes.png)','',
        table(['任务',*ARMS],[[t,*[indexed[t,arm]['outcome']+('*' if indexed[t,arm]['outcome']!=indexed[t,arm]['original_outcome'] else '') for arm in ARMS]] for t in tasks]),'',
        '* 为既有独立GRANGER补充回执的裁决，原文件仍保留FAIL/INDETERMINATE。原始与复核统计同时输出在summary.json。FAIL表示未完成既定交付/验收，不能不经归因直接解释为模型能力失败。','',
        '## 成本、时间和公平性','',
        table(['系统','路径活动时间中位数/秒','时间覆盖','路径API上界合计/USD','含失败API上界/成功','订阅预留合计','完整Token覆盖'],
              [[arm,fmt(a[arm]['median_recorded_path_seconds']),f"{a[arm]['path_seconds_coverage']}/16",fmt(a[arm]['sum_path_api_bound_usd']),
                fmt(a[arm]['path_api_bound_per_acceptance_usd']),a[arm]['sum_path_subscription_reservations'],f"{a[arm]['token_coverage']}/16"] for arm in ARMS]),'',
        '![时间费用成功率](latency-cost-completion.png)','',
        '旧字段end_to_end_seconds实际由记录的路径模型/公开检查时间加对应隐藏验收组成，不是完整的用户发起到交付墙钟。Black-5、PC-ALM、GRANGER存在恢复计时缺口，保持unavailable；不能拿新会话时间冒充原端到端耗时。比较中位数包含已知的失败任务，未把未知填0。路径费用包含共享候选，A–F列不能相加充当真实账单；API为保守上界，订阅价格不可见，D的API为0不代表免费。','',
        f"累计账本：{budget['requests']}次DeepSeek wire请求、{budget['subscription_reservations']}次订阅预留、API保守上界USD{budget['api_upper_bound_usd']:.7f}；实际扣款unavailable。剩余{budget['request_limit']-budget['requests']}次/USD{budget['cash_limit_usd']-budget['api_upper_bound_usd']:.7f}保守空间。不充值、不重置，未知usage的预留不退款。",'',
        table(['去重账本范围','DS请求','已知usage','未知usage','API上界/USD','其中未知预留/USD'],
              [[k,v['requests'],v['known_usage_requests'],v['unknown_usage_requests'],fmt(v['api_upper_bound_usd'],7),fmt(v['unknown_reservation_bound_usd'],7)] for k,v in budget['groups'].items()]),'',
        table(['范围','非缓存input','cache-read input','cache-create input','output'],
              [[k,*[v['known_usage'][field] for field in ('input_tokens','cache_read_input_tokens','cache_creation_input_tokens','output_tokens')]] for k,v in budget['groups'].items()]),'',
        '上述Token仅汇总已结算请求，32条未知usage不填0；缓存读取和非缓存输入分列。原路径metrics.input_tokens已含缓存输入，不能再次加cache_read_tokens。历史/其他探针单列，不混入正式完成率。订阅预留不是API wire数，推理Token在不可见时不补估。','',
        '角色限时为公共900秒/科研1200秒，单请求600秒、每DS角色1000请求、输出256000；同题限制相同。但多角色系统总可用工作量更高，现有结果不构成等成本因果实验，也没有同一系统多个预算点可画可靠预算响应曲线。路径费用/活动时长与成败的观察性比较已给出，不能据此宣称等费用或等墙钟优势。','',
        'time_to_first_patch、time_to_first_test_pass、真实用户time_to_accepted、DS排队/工具/测试完整分解及每题CI时间缺少统一事件计量，均为unavailable。J3记录中的微秒级elapsed_seconds只是结构化解析耗时，本报告使用独立judge worker墙钟。旧human_interventions/human_seconds默认0没有完整人工计量支持，不作为实测零；已知有关机暂停、登录、代理和恢复决定，精确人时不可见。','',
        '## 配对结果与Judge/Merge消融','',
        table(['配对：左vs右','仅左通过','仅右通过','均通过','均未通过'],
              [[key,v['left_only'],v['right_only'],v['both_accepted'],v['neither_accepted']] for key,v in summary['paired_acceptance'].items()]),'',
        table(['公开原池Judge','完成数','选中隐藏PASS','存在PASS却漏选','全轨迹改选/可比','耗时中位/秒'],
              [[jid,j[jid]['completed'],j[jid]['selected_acceptance_count'] if j[jid]['completed'] else 'unavailable',
                f"{j[jid]['missed_available_pass']}/{j[jid]['pass_available_completed']}" if j[jid]['completed'] else 'BLOCKED_REGION',
                f"{j[jid]['trace_selection_changed']}/{j[jid]['trace_comparable']}" if j[jid]['trace_comparable'] else 'unavailable',fmt(j[jid]['median_seconds'],3)] for jid in ('J0','J1','J2','J3')]),'',
        'Judge表以12个公共任务的同一原N3池为主要客观检验；科研的不完整交付门与验收器问题另列，不能把这些标签当纯科学正确性金标准。J0是公开测试+稳定ID顺序，J1为原LAV K1/logprobs，J2因用户地区限制阻塞而非0分，J3为Sol结构化判断而非概率期望。完整128条原池/扩展池判断及其全轨迹对照保存在analysis-data.json，包含BLOCKED_LOGPROBS等状态。对不可用评分器不付费补跑、不伪造排名。','',
        f"Merge：原best-of-N通过{m['best_accepted']}/16，扩展池含M选择通过{m['with_m_accepted']}/16；M自身通过{m['m_accepted']}/16；原三候选隐藏门均无PASS时M形成PASS为{m['m_pass_when_no_original_pass']}次。公开全失败池{m['all_originals_failed_visible']}，隐藏门均无PASS池{m['all_originals_failed_hidden']}，两者分开。",'',
        'B与C还包含评分器、角色次数和选择规则的变化，其净差不能全部归因于合并。M额外墙钟、每池原/扩展选择和每角色消耗另存数据；原/全轨迹使用相同冻结对象，未重跑候选或隐藏验收。','',
        '## 科研失败归因与Pi补充','',
        'PC-ALM：原六臂在run manifest git_commit门失败；沙箱复制排除了.git，现有D的记录明确显示git rev-parse失败，需将验收环境/接口问题与算法表现分开。既有只读诊断D/E均75/75格落在本机冻结容差内；F为74/75，最大梯度余弦偏差0.04391527超过0.02。C1–C5科学统计通过不替代执行忠实性；独立两格重放等门未完成，不将诊断改写成完整PASS，也不重训补分。','',
        'EGL：七个候选遇到SystemExit(0)提前离开runpy，可信worker未写optimizer_usage；这已由既有生命周期正负控制证实，不能算作七次独立算法失败。D的另一summary字段契约未过。既有只读数值检查DS0/A/C/D/E的18/18曲线运行通过，B/M/F仅15/18（最大曲线RMSE约6.2116pp），所有50个signed/zero优化器探针通过。D有18个权重重放证据，其余七份缺训练使用计量/独立权重重放，源代码/图表门也未完成。原FAIL保留，未给这些候选补发PASS。','',
        'STROKE：既有数值检查揭示null/零输入边界与ROI元数据不匹配；这是明确的协议/数值失败，不能以生成图表替代。限定健康/合成离线任务，不支持临床有效性结论。GRANGER主集：既有同机独立数值与源码补充使8候选/六臂PASS，原拒绝和INDETERMINATE另存，不与新增Pi源码缺陷混淆。','',
        'Pi两任务×四profile×两通道共16格：公共8格通过（含一次官方会话fork过载恢复），科研原8格数值通过；源码最终7通过、1为共享内存同步缺陷。两项默认solve错误状态疑点在每份18组定向试验中均有11组真实后端报错并抛异常，疑点排除。另两份在ridge=1e-12近奇异ramp压力输入出现约1.0884e-5绝对误差，原容差约1e-7，作为新增压力诊断FAIL完整保留，不插入旧矩阵重新计分。P3同步缺陷由未改动CUDA的PTX与跨warp索引证明；未运行sanitizer、未声称已动态观察原样本数值出错。','',
        '## 本机、环境和阶段测量','',
        '诊断时的只读GPU快照：'+data['gpu_observation']+'。CuPy '+data['environment_observation']['cupy']+' / NumPy '+data['environment_observation']['numpy']+
        '，CUDA runtime '+str(data['environment_observation']['runtime_version'])+'、driver API '+str(data['environment_observation']['driver_api_version'])+
        '、NVRTC '+'.'.join(map(str,data['environment_observation']['nvrtc_version']))+'；该快照不冒充全部历史运行的GPU驱动证明。原硬件摘要仅覆盖CPU/kernel/thread信息，未包含GPU字段，这属于历史计量缺口。','',
        '所有计算在本机项目WSL中进行，保留各科研任务冻结的CPU/GPU协议。EGL使用8线程CPU，TMS使用单核CPU协议，GRANGER独立CPU参考计时限制1线程；GPU任务使用本地4060。每题A–F共用固定环境/权限/基础提交，跨题因依赖不同使用各自环境锁。16题准备摘要相同，本次环境观测摘要则不同；历史恢复没有完整记录实际GPU/内核快照，不能仅用旧准备字段证明全程系统未变化。','',
        table(['任务','环境摘要前12位','硬件摘要前12位','基础提交前12位'],
              [[t,*[indexed[t,'A']['environment'][k][:12] for k in ('env_sha256','hardware_sha256','base_commit')]] for t in tasks]),'',
        table(['角色阶段','有记录数量','模型阶段墙钟中位/秒'],
              [[role,len(values),fmt(statistics.median(values))] for role in sorted({s['role'] for s in data['stages']})
               if (values:=measured(s['seconds'] for s in data['stages'] if s['role']==role))]),'',
        '阶段墙钟只描述对应模型角色，不含全局人工作业；角色之间有共享前缀和并行，不能直接相加作为系统交付时间。Reviewer和Judge的额外时间已分别保留。请求级elapsed及first_delta样本及超时字段覆盖在analysis-data.json；完整SSE缓冲交付下，内部first_delta不等于用户首字延迟。','',
        '## 技术决策与边界','',
        'F在本样本有更多交付通过，代价是更多角色、订阅和路径活动时间；这支持继续保留可选增强/协作路径，不支持默认所有任务启用。原生DSH/Codex应保留快速路径。B/C和Judge的收益具有任务差异，须报告误选、退化和全失败池，不宣称DS增强、Jev或融合机制天然有效。Jev未获得可用接入证据，保持独立阻塞身份。','',
        'Aider/Agentless作为以后低开销编码/定位对照的候选场景；OpenEvolve/KDA作为数值优化或GPU kernel子任务的后续研究场景。本轮均未运行，未添加依赖，也没有效果或价格比较证据。','',
        '限制：固定seed42、每题一次、便利选题；含本机资源/提供商波动、人工恢复、现金授权后继与Black-5检查点协议。旧v8–v11等协议只记历史成本，不能混算本轮成功率。现金后继只改预算授权，旧p6_main_budget.py可由保留Git精确重建；并非所有历史路径的当前文件字节仍等于旧合同。真实主集没有公开全失败池，该Merge分层不能宣称已覆盖。缺失测量与科研验收器问题使完整P6有效性验收仍有保留。报告完成不等于科研任务全PASS、产品PR获批或允许发布。','',
        '## 证据与复现','',
        'analysis-data.json保留96行原/复核状态、指标、16个主回执与16个敏感性回执SHA、128条Judge记录、16份Merge记录、阶段墙钟及补充诊断。summary.json为自动计算结果，provenance.json绑定本报告输入和生成器摘要。生成器仅离线读取现有证据，输出限制在项目.local-workbench目录；所有原始私有数据、凭据和候选仓库未发布。','',
        '预算账本SHA256：`'+budget['ledger_sha256']+'`。GitHub继续暂缓；本机30秒只读监控和45分钟巡检保持。P7功能062a064的包及本地安装验收保持有效，本报告是独立私有分析交付。']
    return '\n'.join(lines)+'\n'


def plots(data,summary,output):
    os.environ['MPLCONFIGDIR']=str(ROOT/'.local-workbench/benchmark/report-cache/matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    tasks=list(dict.fromkeys(r['task_id'] for r in data['rows']));indexed={(r['task_id'],r['arm']):r for r in data['rows']}
    fig,ax=plt.subplots(figsize=(10,9),layout='constrained')
    ax.imshow([[1 if indexed[t,a]['outcome']=='PASS' else 0 for a in ARMS] for t in tasks],cmap=ListedColormap(['#e9c5bf','#407b8d']),vmin=0,vmax=1,aspect='auto')
    ax.set_yticks(range(16),tasks,fontsize=9);ax.set_xticks(range(6),ARMS)
    for y,t in enumerate(tasks):
        for x,a in enumerate(ARMS):ax.text(x,y,'PASS' if indexed[t,a]['outcome']=='PASS' else 'NOT ACCEPTED',ha='center',va='center',fontsize=7,color='white' if indexed[t,a]['outcome']=='PASS' else '#4c2926')
    ax.set_title('16 frozen tasks / 6 linked arms; includes documented GC review\nNot-accepted cells include protocol and evaluator limitations',fontsize=12)
    fig.savefig(output/'outcomes.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(14,4),layout='constrained');a=summary['arms']
    axes[0].bar(ARMS,[a[x]['accepted']/16 for x in ARMS],color='#407b8d');axes[0].set_ylim(0,1);axes[0].set_title('Accepted deliveries / 16\nExploratory linked observations')
    axes[1].bar(ARMS,[a[x]['median_recorded_path_seconds'] for x in ARMS],color='#7c96b8');axes[1].set_title('Median recorded path seconds\nCoverage shown; not user end-to-end')
    for i,x in enumerate(ARMS):axes[1].text(i,a[x]['median_recorded_path_seconds'],str(a[x]['path_seconds_coverage'])+'/16',ha='center',va='bottom',fontsize=8)
    axes[2].bar(ARMS,[a[x]['sum_path_api_bound_usd'] for x in ARMS],color='#c28f61');axes[2].set_title('Sum of per-arm API safety bounds, USD\nShared paths; do not add arms or infer bills')
    axes[2].annotate('D: subscription unpriced',xy=(3,0),xytext=(1.7,max(a[x]['sum_path_api_bound_usd'] for x in ARMS)*.7),arrowprops={'arrowstyle':'->'},fontsize=8)
    for ax in axes:ax.spines[['top','right']].set_visible(False);ax.set_xlabel('Arm')
    fig.savefig(output/'latency-cost-completion.png',dpi=160);plt.close(fig)


def html_report(markdown):
    parts=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>P6 本地分析报告</title><style>body{max-width:1120px;margin:40px auto;padding:0 24px;font:16px/1.8 system-ui;color:#20323b}table{border-collapse:collapse;width:100%;font-size:13px;margin:24px 0}td,th{padding:7px;border:1px solid #cbd5db;text-align:left}th{background:#edf3f5}img{max-width:100%}h2{margin-top:44px}code{overflow-wrap:anywhere}p{margin:16px 0}</style>']
    in_table=False;first=False
    for line in markdown.splitlines():
        if line.startswith('|'):
            if set(line.replace('|','').replace('-','').strip())==set():continue
            if not in_table:parts.append('<table>');in_table=True;first=True
            tag='th' if first else 'td';first=False
            parts.append('<tr>'+''.join('<'+tag+'>'+html.escape(x.strip())+'</'+tag+'>' for x in line.strip('|').split('|'))+'</tr>');continue
        if in_table:parts.append('</table>');in_table=False
        if not line:continue
        image=re.fullmatch(r'!\[(.*?)\]\((.*?)\)',line)
        if image:parts.append('<figure><img alt="'+html.escape(image[1])+'" src="'+html.escape(image[2])+'"></figure>');continue
        count=len(line)-len(line.lstrip('#'))
        if count:parts.append(f'<h{count}>'+html.escape(line[count:].strip())+f'</h{count}>')
        else:parts.append('<p>'+html.escape(line)+'</p>')
    if in_table:parts.append('</table>')
    return '\n'.join(parts)+'</html>'


def generate(input_path,output):
    input_path=Path(input_path);output=Path(output)
    if not output.resolve().is_relative_to((ROOT/'.local-workbench').resolve()):
        raise ValueError('Private results require publication review before export')
    raw=input_path.read_bytes();data=json.loads(raw);summary=summarize(data)
    output.mkdir(parents=True,exist_ok=False)
    (output/'analysis-data.json').write_bytes(raw)
    (output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    plots(data,summary,output);text=document(data,summary)
    (output/'report.md').write_text(text,encoding='utf-8')
    (output/'report.html').write_text(html_report(text),encoding='utf-8')
    provenance={'input_sha256':hashlib.sha256(raw).hexdigest(),'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'model_calls':0,'whole_task_replays':0,'github_operations':0,'full_p6_acceptance':False,
                'files_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()}}
    (output/'provenance.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
    return {'status':'P6_ANALYSIS_DELIVERED_WITH_LIMITATIONS','output':str(output),'accepted_by_arm':{a:v['accepted'] for a,v in summary['arms'].items()},'models_started':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(generate(args.input,args.output)))
