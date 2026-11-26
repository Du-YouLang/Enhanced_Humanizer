"""Read-only native export and local HTML/CSV/JSON summary. No model execution."""
import argparse
import csv
from datetime import datetime,timezone,timedelta
import html
import json
from pathlib import Path
import re
import sys
from p6_refresh_analysis import build,telemetry,method_label

EXPORT=r"""import json,sys,pathlib,hashlib
v=json.load(sys.stdin);rid=v['run_id']
import re
if not re.fullmatch(r'refresh-[0-9]{8}T[0-9]{6}Z',rid):raise ValueError('Exact run ID required')
base=pathlib.Path('/opt/workbench/benchmark/private/model-refresh');root=base/rid
recovery=v['plan'].get('score_contract_recovery')or{}
source_runs={rid:v['plan']['source_commit']}
if recovery:
 prior=json.loads((pathlib.Path(recovery['prior_root'])/'plan.json').read_bytes());source_runs[recovery['prior_run_id']]=prior['source_commit']
infra_plan=base/'refresh-20261126T032113Z/plan.json'
if infra_plan.exists():source_runs['refresh-20261126T032113Z']=json.loads(infra_plan.read_bytes())['source_commit']
sys.path[:0]=[v['folder'],v['folder']+'/src'];from p6_refresh_accounting import summarize
from pi_full_protocol import digest

def compact(row,path,group_sha,origin_run):
 c=row.get('candidate');a=row.get('acceptance')or{}
 return {**{k:row.get(k) for k in ('task_id','model','method','outcome','frozen','barrier_sha256','scientific_review','metrics','method_timing','acceptance_io_adjustment')},
 'candidate':{k:c.get(k) for k in ('id','root','head_commit','base_commit','verdict','working_tree','protected_paths_modified','test_report')} if c else None,
 'acceptance':{**{k:a.get(k) for k in ('verdict','numeric_verdict','reason','error_type','evidence_root','elapsed_seconds','trusted_measurement')},'detail_sha256':digest(a.get('detail')) if a.get('detail')else None},
 'original_row_sha256':digest(row),'method_source_run_id':origin_run,'method_source_commit':source_runs[origin_run],'candidate_scope':c.get('scope') if c else None,'source_group_file':str(path),'source_group_sha256':group_sha}

def groups(pattern):
 out=[]
 for p in sorted(root.glob(pattern)):
  raw=p.read_bytes();d=json.loads(raw)
  if d.get('value_sha256')!=digest(d['value']):raise ValueError('Completed group hash mismatch')
  g=d['value']
  if not isinstance(g,dict) or 'rows'not in g:continue
  h=hashlib.sha256(raw).hexdigest();origin_run=rid
  if not g.get('is_interface_supplement') and g.get('task_id')=='BIP-black-1' and g.get('model')in recovery.get('retained_groups',{}):origin_run=recovery['prior_run_id']
  out.append({'rows':[compact(r,p,h,origin_run) for r in g['rows']],'stage':d['stage']})
 return out
l=pathlib.Path('/opt/workbench/state/p6-main-local-20261011/ledger.json');raw=l.read_bytes();ledger=json.loads(raw)
infra=base/'refresh-20261126T032113Z';workers={}
for p in infra.glob('*/*/*/controller-outcome.json'):workers[str(p.parent)]=json.loads(p.read_bytes())
attempts=[]
for method in ('Direct','Enhanced'):
 prefix='REFRESH/refresh-20261126T032113Z/BIP-black-1/GPT61-Sol/'+method
 attempts.append({'cell':['BIP-black-1','GPT61-Sol',method],'kind':'RETAINED_MISSING_CODE_MODE_HOST_INFRASTRUCTURE_PREFIX','metrics':summarize(ledger,workers,prefix)})
print(json.dumps({'run_id':rid,'groups':groups('stages/*.completed.json'),'interface_supplements':groups('supplement-stages/*.completed.json'),
 'infrastructure_attempts':attempts,'science_adjudications':[],
 'budget':{'requests':len(ledger['requests']),'subscriptions':len(ledger['codex_turns']),'conservative_bound_usd':ledger['cash_bound_nano']/1e9,'caps':ledger['aggregate_caps'],'actual_cash':'unavailable','ledger_sha256':hashlib.sha256(raw).hexdigest()},
 'snapshot_schema':'MODEL_REFRESH_REPORT_V1','provenance':{'execution_source_commits_by_run':source_runs,'plan_sha256':v['plan']['plan_sha256'],'native_source_commit':v['plan']['source_commit'],'export_model_dispatches':0,'export_candidate_executions':0,'raw_records_edited':False}}))
"""


def export(contract):
    from wsl_project import run
    value=json.loads(Path(contract).read_bytes())
    r=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',EXPORT],input_bytes=json.dumps(value).encode(),timeout=120)
    if r.returncode:raise RuntimeError('Read-only export failed: '+r.stderr.decode(errors='replace')[-2000:])
    return json.loads(r.stdout)


def number(value,places=0):
    if value is None:return '—'
    return f'{value:,.{places}f}'


def tokens(value):
    if value is None:return '—'
    fields=('input_tokens_known','output_tokens_known') if 'input_tokens_known'in value else ('input_tokens_recorded','output_tokens_recorded')
    prefix='≥' if value['lower_bound'] else ''
    return prefix+number(value[fields[0]])+' / '+prefix+number(value[fields[1]])


def render(result):
    esc=html.escape;rows=[]
    for item in result['summary']:
        rows.append('<tr>'+''.join('<td>'+esc(str(s))+'</td>' for s in (
            item['name'],str(item['successes'])+'/16',str(item['completed_cells'])+'/16',item['software_successes'],item['scientific_successes'],
            number(item['elapsed_median_seconds'],2)+' ('+str(item['elapsed_measured_cells'])+'/16)',
            number(item['hidden_acceptance_median_seconds'],2)+' ('+str(item['hidden_acceptance_measured_cells'])+'/16)',
            number(item['io_adjusted_median_seconds'],2)+' ('+str(item['io_adjusted_measured_cells'])+'/16)',
            tokens(item['all_attempt_deepseek']),tokens(item['all_attempt_openai'])) )+'</tr>')
    detail=[]
    raw={ (r['task_id'],r['model'],r['method']):r for r in result['raw_rows'] }
    for r in result['reviewed_rows']:
        original=raw[(r['task_id'],r['model'],r['method'])]
        detail.append('<tr>'+''.join('<td>'+esc(str(s))+'</td>' for s in (r['task_id'],method_label(r['model'],r['method']),original['outcome'],r['reviewed_outcome'],r['result_origin']))+'</tr>')
    generated=datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S 北京时间')
    title='模型与流程基准：最终审阅结果' if result['status']=='FINAL_REVIEWED_144' else '模型与流程基准：进度快照，非最终结果'
    limits=''.join('<li>'+esc(v)+'</li>' for v in result['limitations'])
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>'+title+'</title><style>body{font:15px/1.6 system-ui,sans-serif;margin:28px;color:#172334;background:#f7f9fc}h1{font-size:25px}table{border-collapse:collapse;background:white;width:100%;font-size:13px}th,td{border:1px solid #d7dfeb;padding:8px;text-align:left;vertical-align:top}th{background:#e9eef8;position:sticky;top:0}.scroll{overflow:auto;margin:20px 0}.note{padding:14px;background:#fff4d5;border-left:4px solid #bd8420}code{overflow-wrap:anywhere}a{color:#194dbc}</style><h1>'+title+'</h1><p>'+generated+' · 已闭合 '+str(result['unique_cells'])+'/144 唯一格 · 独立科学审阅 '+str(result['science_audits'])+'/36</p><p class="note">成功数使用审阅后视图；原始结果保留在明细。两项接口补验收不增加144格分母。耗时单位为秒，求解／公开检查与隐藏验收分列；括号内是计量覆盖数，恢复分段不补算。Token列为输入／输出，输入含缓存；≥表示缺失用量下界，费用不是实付账单。</p><div class="scroll"><table><thead><tr><th>方法</th><th>成功／总题</th><th>执行闭合</th><th>软件成功／12</th><th>科研成功／4</th><th>求解＋公开检查中位数</th><th>隐藏验收中位数</th><th>扣本地I/O估计中位数</th><th>DS Token输入／输出</th><th>OpenAI Token输入／输出</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div><p>输入缓存细分、未知用量、全部尝试与共享投影分别保存在JSON；Token统计包括保留的基础设施失败尝试。<a href="analysis.json">分析JSON</a> · <a href="cells.csv">逐格CSV</a> · <a href="summary.csv">汇总CSV</a></p><h2>配对比较</h2><p>仅在同题双方成功且完整计量可用时比较速度。原始及I/O敏感性比值、配对成功差异与探索性检验见分析JSON；便利抽样与同仓库任务相关性限制外推，匹配的是模型活动时间上限。</p><h2>逐格结果</h2><div class="scroll"><table><thead><tr><th>任务</th><th>方法</th><th>原始状态</th><th>审阅后状态</th><th>证据来源</th></tr></thead><tbody>'+''.join(detail)+'</tbody></table></div><h2>解释限制</h2><ul>'+limits+'</ul></html>'


def write(result,output,snapshot):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    for name,value in [('snapshot.json',snapshot),('analysis.json',result)]:
        (output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (output/'report.html').write_text(render(result),encoding='utf-8')
    with (output/'summary.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['name','successes','completed_cells','expected_cells','software_successes','scientific_successes','elapsed_measured_cells','elapsed_sum_seconds','elapsed_median_seconds','hidden_acceptance_measured_cells','hidden_acceptance_median_seconds','active_phase_sum_measured_cells','active_phase_sum_median_seconds','io_adjusted_measured_cells','io_adjusted_median_seconds','ds_input_tokens_known','ds_cached_input_subset','ds_output_tokens_known','ds_unknown_usage_requests','ds_tokens_lower_bound','openai_input_tokens_recorded','openai_cached_input_subset','openai_output_tokens_recorded','openai_tokens_lower_bound']
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for row in result['summary']:
            item={k:row.get(k) for k in fields};ds=row['all_attempt_deepseek'];oa=row['all_attempt_openai']
            if ds:item.update(ds_input_tokens_known=ds['input_tokens_known'],ds_cached_input_subset=ds['cache_read_input_tokens_known'],ds_output_tokens_known=ds['output_tokens_known'],ds_unknown_usage_requests=ds['unknown_usage_requests'],ds_tokens_lower_bound=ds['lower_bound'])
            if oa:item.update(openai_input_tokens_recorded=oa['input_tokens_recorded'],openai_cached_input_subset=oa['cached_input_tokens_subset'],openai_output_tokens_recorded=oa['output_tokens_recorded'],openai_tokens_lower_bound=oa['lower_bound'])
            writer.writerow(item)
    with (output/'cells.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['task_id','model','method','outcome','reviewed_outcome','result_origin','elapsed_seconds','hidden_acceptance_seconds','active_phase_sum_seconds','io_adjusted_estimate_seconds','timing_unavailable_reason','deepseek','openai']
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for row in result['reviewed_rows']:
            item={k:row.get(k) for k in fields[:6]};t=telemetry(row)
            for k in fields[6:]:item[k]=json.dumps(t[k],ensure_ascii=False) if isinstance(t.get(k),dict) else t.get(k)
            writer.writerow(item)
    import hashlib,zipfile
    names=('snapshot.json','analysis.json','report.html','summary.csv','cells.csv')
    inventory={name:hashlib.sha256((output/name).read_bytes()).hexdigest() for name in names}
    (output/'inventory.json').write_text(json.dumps(inventory,indent=2)+'\n',encoding='utf-8')
    archive=output/'report.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name in [*inventory,'inventory.json']:z.write(output/name,name)
    with zipfile.ZipFile(archive)as z:
        if z.testzip()is not None:raise ValueError('Report archive CRC failed')
        for name,h in inventory.items():
            if hashlib.sha256(z.read(name)).hexdigest()!=h:raise ValueError('Report archive inventory mismatch')
    return {'report':str(output/'report.html'),'zip_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'files':len(inventory)+1}


if __name__=='__main__':
    p=argparse.ArgumentParser();source=p.add_mutually_exclusive_group(required=True);source.add_argument('--contract');source.add_argument('--snapshot');p.add_argument('--adjudications');p.add_argument('--output',required=True);p.add_argument('--final',action='store_true');a=p.parse_args()
    snapshot=export(a.contract) if a.contract else json.loads(Path(a.snapshot).read_bytes())
    import hashlib
    snapshot.setdefault('provenance',{})['reporter_source_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),Path(__file__).with_name('p6_refresh_analysis.py'))}
    if a.adjudications:snapshot['science_adjudications']=json.loads(Path(a.adjudications).read_bytes())
    result=build(snapshot,final=a.final);artifact=write(result,a.output,snapshot)
    print(json.dumps({'status':result['status'],'unique_cells':result['unique_cells'],'science_audits':result['science_audits'],**artifact},ensure_ascii=False))
