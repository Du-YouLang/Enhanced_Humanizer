// One entitlement probe, no coding tools or benchmark task, using Pi's own login.
import {writeFile} from 'node:fs/promises';
const base='/opt/workbench/pi-comparison';
const root=process.argv[2];
if(!root?.startsWith(base+'/subscription-login-')||root.includes('..'))throw new Error('Project login required');
const {ModelRuntime}=await import(base+'/runtime/node_modules/@earendil-works/pi-coding-agent/dist/core/model-runtime.js');
const start=performance.now();
let row;
try {
  const r=await ModelRuntime.create({authPath:root+'/auth.json',modelsPath:null,
    modelsStorePath:root+'/models-store.private.json',allowModelNetwork:false});
  const m=r.getModel('openai','gpt-6.1-sol');
  if(!m||!r.isUsingSubscription('openai'))throw new Error('Requested subscription model unavailable');
  const response=await r.completeSimple(m,{messages:[{role:'user',content:'Reply with the word READY. This is an access probe; no tools.',timestamp:Date.now()}]},
    {reasoning:'low',timeoutMs:600000,maxRetries:0,signal:AbortSignal.timeout(600000),transport:'sse'});
  row={status:response.stopReason==='stop'?'PASS_SUBSCRIPTION_ACCESS':'ACCESS_PROBE_NOT_COMPLETED',
    auth_method:'CHATGPT_SUBSCRIPTION_OFFICIAL_PI_OAUTH',provider:'openai',model_requested:m.id,
    model_returned:response.model,stop_reason:response.stopReason,usage:response.usage,
    api_cash_usd:0,subscription_cost_usd:'unavailable',provider_request_retries:0,
    account_comparison:'UNAVAILABLE_ENCRYPTED_METADATA',user_selected_current_account:true,
    benchmark_acceptance:'NOT_RUN',tools_enabled:false,elapsed_seconds:(performance.now()-start)/1000};
} catch(e) {
  row={status:'ACCESS_PROBE_NOT_COMPLETED',error_type:e?.name??'Error',usage:'unavailable',
    api_cash_usd:0,subscription_cost_usd:'unavailable',benchmark_acceptance:'NOT_RUN',
    elapsed_seconds:(performance.now()-start)/1000};
}
await writeFile(root+'/access-probe-v1.private.json',JSON.stringify(row,null,2)+'\n',{mode:0o600,flag:'wx'});
console.log(JSON.stringify({status:row.status,model_requested:row.model_requested,model_returned:row.model_returned,
  stop_reason:row.stop_reason,usage:row.usage,api_cash_usd:row.api_cash_usd,benchmark_acceptance:'NOT_RUN',elapsed_seconds:row.elapsed_seconds}));
