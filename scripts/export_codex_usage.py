"""Export only model/session/usage fields, never raw transcripts or login files."""

import argparse
import json
from pathlib import Path


def collect(root):
    sessions=[]
    for path in Path(root).rglob('rollout-*.jsonl'):
        record={'trace_file':str(path),'session_id':'unavailable','model_id':'unavailable','usage':'unavailable'}
        with path.open(encoding='utf-8') as stream:
            for line in stream:
                row=json.loads(line)
                payload=row.get('payload',{})
                if row.get('type')=='session_meta':
                    record['session_id']=payload.get('id','unavailable')
                elif row.get('type')=='turn_context':
                    record['model_id']=payload.get('model','unavailable')
                elif row.get('type')=='event_msg' and payload.get('type')=='token_count' and payload.get('info'):
                    record['usage']=payload['info'].get('total_token_usage','unavailable')
        sessions.append(record)
    return sessions


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root')
    print(json.dumps(collect(parser.parse_args().root)))
