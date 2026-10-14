"""Read-only timing summaries; native tool durations are distinct from model latency."""
from datetime import datetime
import math


def timestamp(row):
    value = row.get('time')
    if isinstance(value, (int, float)) and math.isfinite(value):
        return value / 1000
    value = row.get('timestamp')
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
    return None


def tool_ids(row):
    data = row.get('data', {})
    if row['type'] == 'tool/call':
        return [data.get('callId') or data.get('call_id')]
    if data.get('call_id'):
        return [data['call_id']]
    return [part.get('toolCallId') for part in data.get('message', {}).get('content', [])
            if part.get('type') == 'tool-result']


def tool_timing(trace):
    calls, results = {}, {}
    for row in trace['records']:
        table = calls if row['type'] == 'tool/call' else results
        for identifier in tool_ids(row):
            if not identifier:
                continue
            if identifier in table:
                raise ValueError('Duplicate tool event identity; timing is ambiguous')
            table[identifier] = timestamp(row)
    intervals = []
    for identifier, start in calls.items():
        end = results.get(identifier)
        if start is None or end is None:
            continue
        if end < start:
            raise ValueError('Native clock moved backwards; do not invent latency')
        intervals.append((start, end))
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    complete = bool(calls) and len(intervals) == len(calls) == len(results)
    return {'status': 'COMPLETE' if complete else 'PARTIAL',
            'native_tools_observed_seconds': sum(end - start for start, end in merged) if intervals else 'unavailable',
            'tool_calls': len(calls), 'paired_timed_results': len(intervals),
            'unpaired_calls': len(calls) - len(intervals),
            'unmatched_results': len(set(results) - set(calls)),
            'aggregation': 'Union of native tool-call/result intervals; overlapping calls counted once',
            'scope': 'Native tool wall time only; not provider queue/generation, first patch, or test-pass time',
            'origin_hashes': trace['origin_hashes']}
