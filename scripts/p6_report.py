"""Generate standalone tables/charts from validated P6 results; missing cells remain NOT_RUN."""
import argparse
import csv
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from workbench.benchmark import ARMS, REQUIRED_METRICS, check_manifest, plan, summarize, validate_result


def report(manifest, results, preparations, output):
    check_manifest(manifest)
    indexed = {}
    for row in results:
        validate_result(row, manifest, preparations.get(row['task_id'], {}))
        key = (row['task_id'], row['arm'])
        if key in indexed:
            raise ValueError('Duplicate task/arm result; retries must be separate preserved attempts')
        indexed[key] = row
    rows = [indexed.get((row['task_id'], row['arm']), row) for row in plan(manifest)]
    summary = summarize(rows)
    output = Path(output)
    private = ROOT/'.local-workbench'
    if not output.resolve().is_relative_to(private.resolve()):
        raise ValueError('Reports stay private until publication review')
    output.mkdir(parents=True, exist_ok=False)
    (output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    columns = ['task_id', 'arm', 'outcome', 'reason', *REQUIRED_METRICS]
    with (output/'results.csv').open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, row.get('metrics', {}).get(key, 'unavailable')) for key in columns})
    cache = ROOT/'.local-workbench/benchmark/cache/matplotlib'
    cache.mkdir(parents=True, exist_ok=True)
    os.environ['MPLCONFIGDIR'] = str(cache)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    actual = [row for row in rows if row['outcome'] != 'NOT_RUN']
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), constrained_layout=True)
    for ax, metric, label in zip(axes, ['end_to_end_seconds', 'api_cash_usd', None],
                                 ['Mean end-to-end seconds (known)', 'Mean billed API cash USD (known)', 'Completion rate (attempted)']):
        known = []
        for arm in ARMS:
            group = [row for row in actual if row['arm'] == arm]
            values = [row['metrics'][metric] for row in group if row['metrics'][metric] != 'unavailable'] if metric else []
            if metric and values:
                known.append((arm, sum(values)/len(values)))
            elif metric is None and group:
                known.append((arm, sum(row['outcome'] == 'PASS' for row in group)/len(group)))
        if known:
            ax.bar([x[0] for x in known], [x[1] for x in known])
        else:
            ax.text(.5, .5, 'NOT RUN / unavailable\nNo zero-value substitution', ha='center', va='center', transform=ax.transAxes)
            ax.set_xticks([])
            ax.set_yticks([])
        ax.set_title(label)
        ax.set_xlabel('Arm (A-F)')
    fig.suptitle('P6 exploratory selected tasks; preparation is not model performance')
    fig.savefig(output/'latency-cost-completion.png', dpi=160)
    plt.close(fig)
    (output/'README.txt').write_text('Exploratory convenience sample. NOT_RUN excluded from attempted denominator but coverage shown. All attempted failures/infra/timeouts retained. Unknown costs/tokens are unavailable. API upper bounds are not bills. No science quality or efficacy conclusion.\n')
    return dict(status='REPORT_GENERATED', actual_model_results=len(actual), planned_cells=len(rows), output=str(output))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT/'configs/benchmark-p6-v2.json')
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--preparations', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(report(json.loads(args.manifest.read_text()), json.loads(args.results.read_text())['results'],
                            json.loads(args.preparations.read_text()) if args.preparations else {}, args.output)))
