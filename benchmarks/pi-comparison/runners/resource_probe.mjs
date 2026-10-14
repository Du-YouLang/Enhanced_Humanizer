// Zero-inference probe of the real, pinned Pi resource loader.
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import net from 'node:net';

const spec = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const {DefaultResourceLoader, SettingsManager} = await import(pathToFileURL(path.join(spec.sdk_root, 'dist/index.js')).href);
const loader = new DefaultResourceLoader({
  cwd: spec.work, agentDir: spec.agent_dir,
  settingsManager: SettingsManager.inMemory({retry:{enabled:false},enableAnalytics:false,enableInstallTelemetry:false}),
  noExtensions:true, noSkills:true, noPromptTemplates:true, noThemes:true, noContextFiles:true,
  disabledBuiltinExtensions:['mcp'],
  additionalExtensionPaths: spec.extensions,
  additionalSkillPaths: spec.skills,
  additionalPromptTemplatePaths: spec.prompts,
});
await loader.reload();
const loaded = loader.getExtensions();
const extensions = loaded.extensions.map(e=>({
  path:e.path,
  tools: e.tools instanceof Map ? [...e.tools.keys()] : Object.keys(e.tools ?? {}),
  commands: e.commands instanceof Map ? [...e.commands.keys()] : Object.keys(e.commands ?? {}),
}));
const denied = spec.denied.map(file=>{
  try {fs.readFileSync(file);return 'ALLOWED_FAILURE';}
  catch(e) {return e.code === 'EACCES' || e.code === 'EPERM' ? 'DENIED' : 'MISSING_NOT_PROOF';}
});
let immutable = false;
try {fs.openSync(spec.readonly, 'a');} catch(e) {immutable = e.code === 'EACCES' || e.code === 'EPERM';}
const marker=path.join(spec.work,'probe-own-write.txt');fs.writeFileSync(marker,'control only');
const currentNamespace=fs.readlinkSync('/proc/self/ns/pid');
const cap=fs.readFileSync('/proc/self/status','utf8').match(/^CapEff:\s*(\w+)/m)?.[1];
const networkDenied = await new Promise(resolve=>{
  const socket=net.createConnection({host:'127.0.0.1',port:spec.network_canary_port});
  socket.setTimeout(1500);
  socket.once('connect',()=>{socket.destroy();resolve(false);});
  socket.once('error',e=>resolve(e.code==='EPERM'||e.code==='EACCES'));
  socket.once('timeout',()=>{socket.destroy();resolve(false);});
});
const result={
  kind:'ZERO_MODEL_PINNED_PI_RESOURCE_CONTROL', profile:spec.profile,
  uid:process.getuid(), cap_eff:cap, private_pid_namespace:currentNamespace!==spec.parent_namespace,
  skills:loader.getSkills().skills.map(s=>({name:s.name,filePath:s.filePath})),
  skill_diagnostics:loader.getSkills().diagnostics,
  extensions, extension_errors:loaded.errors, prompts:loader.getPrompts().prompts.map(p=>p.name),
  context_files:loader.getAgentsFiles().agentsFiles.length,
  denied, network_canary_denied:networkDenied, runtime_readonly:immutable, own_write:fs.existsSync(marker),
  provider_calls:0, live_tool_calls:0,
};
console.log(JSON.stringify(result));
