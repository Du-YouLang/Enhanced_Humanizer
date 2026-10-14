// The pinned official Pi SDK owns resources, tools and the entire agent loop.
// Real subscription credentials arrive only on stdin and stay in AuthStorage
// memory. Refreshes leave on a dedicated controller pipe, never the model trace.
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
import {recoveryGuard} from './pi_retry_policy.mjs';

const spec=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const incoming=JSON.parse(fs.readFileSync(0,'utf8'));
const base='/opt/workbench/pi-comparison';
if(!spec.root.startsWith('/opt/workbench/benchmark/private/pi-comparison/formal-')||spec.root.includes('..'))throw new Error('Fresh project-private formal directory required');
if(![900,1200].includes(spec.authorized_role_seconds??spec.role_seconds)||spec.request_seconds!==600||
  !(spec.role_seconds>0&&spec.role_seconds<=(spec.authorized_role_seconds??spec.role_seconds))||
  !(spec.role_requests>0&&spec.role_requests<=1000)||(!spec.recovery&&spec.role_requests!==1000))
  throw new Error('Frozen role/request limits required');
const sdk=await import(pathToFileURL(base+'/runtime/node_modules/@earendil-works/pi-coding-agent/dist/index.js').href);
const {AuthStorage}=await import(pathToFileURL(base+'/runtime/node_modules/@earendil-works/pi-coding-agent/dist/core/auth-storage.js').href);
const storage=AuthStorage.inMemory(incoming.credentials??{});
const emit=r=>process.stdout.write(JSON.stringify(r)+'\n');
const tick=performance.now();
const retryEnabled=Boolean(spec.prospective_transient_retry||spec.recovery&&(spec.subscription||spec.recovery.fixture_agent_retry));
const guard=recoveryGuard(spec.recovery?.prior_consecutive_failures??0);
const settings=sdk.SettingsManager.inMemory({retry:{enabled:retryEnabled,maxRetries:4,baseDelayMs:1000,maxAgentDelayMs:600000,provider:{maxRetries:0,timeoutMs:600000}},
  compaction:{enabled:false},cacheWarming:'off',transport:'sse',enableAnalytics:false,enableInstallTelemetry:false});
const loader=new sdk.DefaultResourceLoader({cwd:spec.work,agentDir:spec.root+'/agent',settingsManager:settings,
  noExtensions:true,noSkills:true,noPromptTemplates:true,noThemes:true,noContextFiles:true,disabledBuiltinExtensions:['mcp'],
  additionalExtensionPaths:spec.extensions,additionalSkillPaths:spec.skills,additionalPromptTemplatePaths:spec.prompts});
await loader.reload();
const loaded=loader.getExtensions();
if(loaded.errors.length||loader.getAgentsFiles().agentsFiles.length)throw new Error('Unexpected ambient resources or extension errors');
emit({type:'resources_observed',profile:spec.profile,skills:loader.getSkills().skills.map(s=>s.name),
  extension_tools:loaded.extensions.flatMap(e=>[...e.tools.keys()]),context_files:0});
let session,stop,dispatches=0,wirePolicies=[];
try {
  const denied=spec.denied.map(p=>{
    try{fs.readFileSync(p);return 'ALLOWED_FAILURE';}
    catch(e){return ['EACCES','EPERM'].includes(e.code)?'DENIED':'MISSING_NOT_PROOF';}
  });
  const cap=fs.readFileSync('/proc/self/status','utf8').match(/^CapEff:\s*(\w+)/m)?.[1];
  const privatePid=fs.readlinkSync('/proc/self/ns/pid')!==spec.parent_namespace;
  let readonly=false;
  try{fs.closeSync(fs.openSync(base+'/runtime/node_modules/@earendil-works/pi-coding-agent/package.json','a'));}
  catch(e){readonly=['EACCES','EPERM'].includes(e.code);}
  emit({type:'credential_isolation',denied,credential_storage:'IN_MEMORY_STDIN_ONLY',uid:process.getuid(),
    cap_eff:cap,private_pid_namespace:privatePid,runtime_readonly:readonly});
  if(denied.some(v=>v!=='DENIED')||!privatePid||process.getuid()===0||cap!=='0000000000000000'||!readonly)
    throw new Error('Credential/private/peer isolation failed');
  if(spec.mode==='auth-control'||spec.mode==='prl-control') {
    if(spec.mode==='prl-control') {
      const tools=new Map(loaded.extensions.flatMap(e=>[...e.tools.entries()].map(([n,v])=>[n,v.definition])));
      const ctx={cwd:spec.work,hasUI:false,sessionManager:{getSessionId:()=>spec.root}};
      const call=async(name,args,context=ctx)=>(await tools.get(name).execute('zero-model-'+name,args,new AbortController().signal,()=>{},context)).details;
      const task=await call('prl_task_start',{name:'zero-model-background-control'});
      fs.writeFileSync(task.worktree+'/checkpoint_marker.txt','zero model checkpoint\n');
      const checkpoint=await call('prl_task_checkpoint',{task_id:task.task_id,message:'control checkpoint'});
      if(!checkpoint.created||!checkpoint.commit)throw new Error('PRL Git checkpoint failed');
      const launched=await call('prl_run_launch',{task_id:task.task_id,
        argv:['python3','-c',"import pathlib,time; time.sleep(.5); pathlib.Path('completed-once.txt').write_text('completed once')"]});
      let finished;
      for(let i=0;i<100;i++) {
        finished=await call('prl_run_inspect',{run_id:launched.run_id,mode:'status'});
        if(!['running','queued'].includes(finished.status))break;
        await new Promise(r=>setTimeout(r,100));
      }
      if(finished.status!=='succeeded')throw new Error('PRL background process did not succeed');
      let ownerDenied=false;
      try{await call('prl_run_inspect',{run_id:launched.run_id,mode:'status'},
        {...ctx,sessionManager:{getSessionId:()=>spec.root+'-other-owner'}});}catch{ownerDenied=true;}
      if(!ownerDenied)throw new Error('PRL cross-owner control was allowed');
      const core=await import(pathToFileURL(base+'/packages/p3/package/dist/core.js').href);
      core.recoverRuns(spec.work);
      const after=await call('prl_run_inspect',{run_id:launched.run_id,mode:'status'});
      if(after.status!==finished.status||after.superseded_by)throw new Error('PRL replayed a finished run');
      emit({type:'prl_control_pass',background_completed:true,git_checkpoint_created:true,
        different_owner_denied:true,finished_run_not_replayed_after_recovery:true,
        power_loss_training_resume:'NOT_ESTABLISHED_BY_THIS_CONTROL',model_calls:0});
    }
    emit({type:'auth_control_pass',real_provider_calls:0});
  } else {
    const runtime=await sdk.ModelRuntime.create({credentials:storage,modelsPath:spec.models_path,
      modelsStorePath:spec.root+'/agent/models-store.private.json',allowModelNetwork:false});
    const model=runtime.getModel(spec.provider,spec.model);
    if(!model||spec.subscription&&!runtime.isUsingSubscription('openai'))throw new Error('Exact provider/model route unavailable');
    const original=runtime.streamSimple.bind(runtime);
    runtime.streamSimple=(m,context,options={})=>{
      if(dispatches>=spec.role_requests)throw new Error('ROLE_REQUEST_CAP');
      ++dispatches;
      const signal=AbortSignal.any([options.signal??new AbortController().signal,AbortSignal.timeout(spec.request_seconds*1000)]);
      emit({type:'transport_dispatch',dispatch:dispatches,model_requested:m.id,provider:m.provider,
        request_seconds:spec.request_seconds,internal_retries:0,elapsed_seconds:(performance.now()-tick)/1000});
      return original(m,context,{...options,signal,timeoutMs:600000,maxRetries:0,transport:'sse',
        ...(!spec.subscription?{maxTokens:256000}:{}),
        onPayload:payload=>{
          // Explicitly match the baseline requested low DeepSeek reasoning mode.
          if(!spec.subscription){payload.thinking={type:'enabled'};payload.reasoning_effort='low';payload.max_tokens=256000;}
          wirePolicies.push({thinking:payload.thinking??null,reasoning_effort:payload.reasoning_effort??payload.reasoning?.effort??null,
            max_tokens:payload.max_tokens??payload.max_output_tokens??null,model:payload.model});
          return payload;
        }});
    };
    ({session}=await sdk.createAgentSession({cwd:spec.work,agentDir:spec.root+'/agent',modelRuntime:runtime,model,
      thinkingLevel:'low',tools:['read','bash','edit','write',...loaded.extensions.flatMap(e=>[...e.tools.keys()])],resourceLoader:loader,settingsManager:settings,
      sessionManager:spec.recovery?.session_file?
        sdk.SessionManager.forkFrom(spec.recovery.session_file,spec.work,spec.root+'/agent/sessions'):
        sdk.SessionManager.create(spec.work,spec.root+'/agent/sessions')}));
    emit({type:'session_bound',session_id:session.sessionId??session.sessionManager?.getSessionId?.()??null,
      requested_thinking_level:'low',active_tools:session.getActiveToolNames()});
    session.subscribe(emit);
    if(retryEnabled)session.subscribe(event=>{
      if(event.type==='message_end'&&event.message?.role==='assistant') {
        const decision=guard.observe(event.message);
        settings.setRetryEnabled(decision.retry);
        emit({type:'provider_recovery_decision',...decision});
      }
    });
    stop=setTimeout(()=>{void session.abort();},spec.role_seconds*1000);
    await session.prompt(spec.prompt);
    emit({type:'formal_finished',transport_dispatches:dispatches,wire_policies:wirePolicies,
      elapsed_seconds:(performance.now()-tick)/1000,subscription:spec.subscription,
      consecutive_provider_failures:guard.failures(),official_sdk_retry_enabled:retryEnabled});
  }
} catch(e) {
  emit({type:'formal_error',error_type:e?.name??'Error',transport_dispatches:dispatches,
    elapsed_seconds:(performance.now()-tick)/1000});
  process.exitCode=1;
} finally {
  clearTimeout(stop);
  session?.dispose();
  // A separate pipe is not inherited by Pi's normal child-tool processes.
  // Never print this object or place it in a candidate-readable file.
  if(Number.isInteger(incoming.credential_fd)) {
    const credential=await storage.read('openai');
    fs.writeSync(incoming.credential_fd,JSON.stringify({openai:credential??null}));
    fs.closeSync(incoming.credential_fd);
  }
}
