// Use the pinned Pi provider's official PKCE flow; no copied Codex credentials.
import { readFile, writeFile, mkdir, chmod } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
const base='/opt/workbench/pi-comparison';
const root=process.argv[2];
if (!root?.startsWith(base+'/subscription-login-') || root.includes('..')) throw new Error('Fresh project login path required');
await mkdir(root,{mode:0o700});
const { openaiChatGPTOAuth }=await import(base+'/runtime/node_modules/@earendil-works/pi-ai/dist/auth/oauth/openai-chatgpt.js');
const { AuthStorage }=await import(base+'/runtime/node_modules/@earendil-works/pi-coding-agent/dist/core/auth-storage.js');
const signal=AbortSignal.timeout(15*60*1000);
try {
  const credential=await openaiChatGPTOAuth.login({signal,
    notify:async e=>{
      if(e.type==='auth_url') await writeFile(root+'/login-url.private.txt',e.url+'\n',{mode:0o600,flag:'wx'});
    },
    prompt:({signal:promptSignal})=>new Promise((_,reject)=>promptSignal.addEventListener('abort',()=>reject(new Error('Manual callback cancelled')),{once:true}))
  },{agentName:'Pi',getDeviceId:()=>randomUUID()});
  const storage=AuthStorage.create(root+'/auth.json');
  await storage.modify('openai',()=>credential);await chmod(root+'/auth.json',0o600);
  const registered=await storage.list();
  await writeFile(root+'/receipt.private.json',JSON.stringify({status:'LOGIN_COMPLETE_ACCESS_UNVERIFIED',
    provider:'openai',auth_method:'CHATGPT_SUBSCRIPTION_OFFICIAL_PI_OAUTH',
    configured:registered.length>0,provider_inference_calls:0,api_cash_usd:0,
    current_account_match:'PENDING_PRIVATE_METADATA_CHECK',scope:'PROJECT_PI_ONLY',global_auth_copied:false})+'\n',{mode:0o600,flag:'wx'});
} catch(e) {
  await writeFile(root+'/failure.private.json',JSON.stringify({status:'LOGIN_NOT_COMPLETED',error_type:e?.name??'Error',provider_inference_calls:0})+'\n',{mode:0o600,flag:'wx'});
  process.exitCode=1;
}
