"""Download the pinned Linux tools without installing or invoking model agents."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import time

from prepare_wsl_assets import ROOT, acquire


def main():
    tick = time.perf_counter()
    approval = json.loads((ROOT / '.local-workbench/approvals/wsl.json').read_text(encoding='utf-8-sig'))
    if approval.get('approved_by') != 'human_user' or not approval.get('system_components_allowed'):
        raise PermissionError('WSL installation is not authorized')
    lock = json.loads((ROOT / 'configs/linux-tools.lock.json').read_text(encoding='utf-8'))
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(acquire, lock['assets']))
    record = {'observed_at': datetime.now(timezone.utc).isoformat(), 'assets': results,
              'elapsed_seconds': round(time.perf_counter()-tick, 6), 'model_requests': 0}
    (ROOT / '.local-workbench/audits/linux-assets.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
