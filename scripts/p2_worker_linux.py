"""One isolated task using the existing Humanize Flow and official DSH runtime."""

from datetime import timedelta
import json
import os
from pathlib import Path
import signal
import sys
import time

from p1_broker import protect_memory
from p1_drivers import MeteredDriver
from p1_fixture import TASK
from p2_candidates import exclusive_json
from p2_isolation import auditor


def main():
    job=json.load(sys.stdin)
    if os.getuid()==0:raise RuntimeError('Agents must never run as root')
    protect_memory()
    signal.signal(signal.SIGTERM,lambda *_:sys.exit(143))
    if job.get('offline_control')=='sleep':
        time.sleep(60)
        raise RuntimeError('Offline watchdog did not stop the worker')
    os.environ['DEEPSEEK_API_KEY']=job.pop('capability')
    os.environ['DEEPSEEK_BASE_URL']=job.pop('broker_url')
    from hmz.sdk import Hmz
    turns=[];tick=time.perf_counter()
    record={'kind':'REAL_MODEL_EXPERIMENT','status':'RUNNING','uid':os.getuid(),'pid':os.getpid(),
            'cap_eff':next(line.strip().split()[-1] for line in Path('/proc/self/status').read_text().splitlines() if line.startswith('CapEff:')),
            'proc_namespace':os.readlink('/proc/self/ns/pid'),'turns':turns}
    try:
        if record['cap_eff']!='0000000000000000':raise RuntimeError('Candidate retained effective namespace capabilities')
        Hmz(workspace=job['work']).run('/opt/workbench/source/flows/p0_coding_demo',job.get('task_contract',{}).get('prompt',TASK),
            agents={'builder':MeteredDriver('builder=dsh/deepseek-flash:low',None,job['scope'],turns,1,600,fence_auditor=auditor(job))},
            budget={'duration':timedelta(seconds=600),'graceful':False}).run()
        record.update(status='COMPLETED',session_id=turns[0]['session_id'],
                      tool_trace=str(Path(os.environ['HUMANIZE_HOME'])/'epics'))
    except BaseException as error:
        record.update(status='INFRA_FAIL',error_type=type(error).__name__,error=str(error)[:1000])
    finally:
        record['elapsed_seconds']=time.perf_counter()-tick
        exclusive_json(Path(job['root'])/'worker.json',record)
    return 0 if record['status']=='COMPLETED' else 1


if __name__=='__main__':sys.exit(main())
