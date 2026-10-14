// Existing Pi SDK runs the agent loop. This adapter bounds/observes transport dispatches.
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const spec=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const base='/opt/workbench/pi-comparison';
if(!spec.root?.startsWith(base+'/sdk-probe-')||spec.root.includes('..'))throw new Error('Fresh private Pi probe required');
if(spec.role_requests!==1000||spec.request_seconds!==600||spec.role_seconds!==900)throw new Error('Approved probe limits required');
const sdk=await import(pathToFileURL(base+'/runtime/node_modules/@earendil-works/pi-coding-agent/dist/index.js').href);
const emit=row=>process.stdout.write(JSON.stringify(row)+'\n');
const tick=performance.now();
let session,dispatches=0,stop;
try {
  const runtime=await sdk.ModelRuntime.create({authPath:spec.auth_path,modelsPath:spec.models_path,
    modelsStorePath:spec.root+'/agent/models-store.private.json',allowModelNetwork:false});
  const model=runtime.getModel(spec.provider,spec.model);
  if(!model)throw new Error('Exact requested model unavailable');
  if(spec.subscription&&!runtime.isUsingSubscription('openai'))throw new Error('Subscription route unavailable');
  const original=runtime.streamSimple.bind(runtime);
  runtime.streamSimple=(m,context,options={})=>{
    if(dispatches>=spec.role_requests)throw new Error('ROLE_REQUEST_CAP');
    ++dispatches;
    const signal=AbortSignal.any([options.signal??new AbortController().signal,AbortSignal.timeout(spec.request_seconds*1000)]);
    emit({type:'transport_dispatch',dispatch:dispatches,model_requested:m.id,provider:m.provider,
      request_seconds:spec.request_seconds,internal_retries:0,elapsed_seconds:(performance.now()-tick)/1000});
    return original(m,context,{...options,signal,timeoutMs:spec.request_seconds*1000,maxRetries:0,transport:'sse'});
  };
  const settings=sdk.SettingsManager.inMemory({retry:{enabled:false,provider:{maxRetries:0,timeoutMs:600000}},
    compaction:{enabled:false},cacheWarming:'off',transport:'sse',enableAnalytics:false,enableInstallTelemetry:false});
  const loader=new sdk.DefaultResourceLoader({cwd:spec.work,agentDir:spec.root+'/agent',settingsManager:settings,
    noExtensions:true,noSkills:true,noPromptTemplates:true,noThemes:true,noContextFiles:true,
    disabledBuiltinExtensions:['mcp']});
  await loader.reload();
  if(loader.getAgentsFiles().agentsFiles.length||loader.getSkills().skills.length||loader.getExtensions().extensions.length)
    throw new Error('Unexpected probe resources');
  ({session}=await sdk.createAgentSession({cwd:spec.work,agentDir:spec.root+'/agent',modelRuntime:runtime,model,
    thinkingLevel:'low',tools:['read','bash','edit','write'],resourceLoader:loader,
    settingsManager:settings,sessionManager:sdk.SessionManager.inMemory()}));
  session.subscribe(emit);
  stop=setTimeout(()=>{void session.abort();},spec.role_seconds*1000);
  await session.prompt('This is a tiny tool connectivity probe, not a benchmark. In the current Git repository, create probe_value.py defining answer() returning integer 42. Use the write tool, then use bash to test it with Python and commit the file with Git. Do not install anything, read credentials, use subagents, or access any other directory. Give a short final summary.');
  emit({type:'probe_finished',transport_dispatches:dispatches,elapsed_seconds:(performance.now()-tick)/1000,
    subscription:spec.subscription,benchmark_acceptance:'NOT_RUN'});
} catch(e) {
  emit({type:'probe_error',error_type:e?.name??'Error',transport_dispatches:dispatches,
    elapsed_seconds:(performance.now()-tick)/1000,benchmark_acceptance:'NOT_RUN'});
  process.exitCode=1;
} finally {
  clearTimeout(stop);
  session?.dispose();
}
