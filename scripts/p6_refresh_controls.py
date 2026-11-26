"""Official Humanize fake-session control; never dispatches a provider request."""
import asyncio
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from p6_refresh_protocol import TASKS,MODELS
from p6_refresh_sessions import run_matched


def session_controls(budget):
    from hmz.sdk.fakes import FakeAgentDriver
    from p1_drivers import MeteredDriver
    from p6_main_budget import MainLedger
    from p3_worker_linux import RoleLedger
    rows=[]
    for label,model in MODELS.items():
        for seconds in (900,1200):
            with tempfile.TemporaryDirectory() as temp:
                root=Path(temp);(root/'code').mkdir()
                scope='REFRESH/refresh-20261126T000000Z/'+TASKS[0]+'/'+label+'/SingleAgent-MatchedBudget/matched-1'
                backend='dsh' if model=='deepseek-flash' else 'codex'
                ledger=MainLedger(root/'fixture-ledger.json',budget,fixture=True)
                # Construction is the real finite-limit adapter. Only its inner
                # upstream transport is replaced by the official fake driver.
                driver=MeteredDriver('builder=codex/gpt-6.2-sol:low',RoleLedger(ledger),scope,[],1,
                    seconds,turn_seconds_ceiling=seconds)
                fake=FakeAgentDriver(harness=backend,model=model,reply='fake answer',cost=0,output_tokens=7)
                fake._spec=SimpleNamespace(role='builder');driver.inner=fake
                job={'root':str(root),'work':str(root/'code'),'scope':scope,'requested_model':model,
                    'backend':backend,'budget':budget,'refresh_slots':6,'refresh_per_turn_seconds':seconds,
                    'role_seconds':6*seconds,'refresh_slot_file':str(root/'controller-slot.json'),'prompt':'solve the frozen task'}
                answer,slots=asyncio.run(run_matched(driver,job))
                if len(fake.sessions)!=1 or len(fake.prompts)!=6 or len(driver.turns)!=6:raise ValueError('Same official session was not reused exactly six times')
                ids={r['same_official_session_id'] for r in slots}
                if len(ids)!=1 or {t['session_id'] for t in driver.turns}!=ids:raise ValueError('Session identity drift')
                if any(t['status']!='COMPLETED' for t in driver.turns) or driver.turns[-1]['usage']['output_tokens']!=42:raise ValueError('Cumulative usage missing')
                reservations=json.loads(ledger.path.read_bytes())['codex_turns'] if ledger.path.exists() else []
                if len(reservations)!=(0 if backend=='dsh' else 6):raise ValueError('Incorrect slot reservation count')
                rows.append({'model':model,'per_turn_seconds':seconds,'official_fake_sessions':1,'bounded_turns':6,
                    'final_cumulative_output_tokens':42,'subscription_reservations':len(reservations),'provider_model_calls':0})
    return {'status':'PASS_OFFICIAL_FAKE_MATCHED_SESSION_CONTROLS','rows':rows,'provider_model_calls':0}
