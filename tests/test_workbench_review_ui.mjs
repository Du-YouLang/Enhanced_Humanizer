import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

function fixture() {
  class Element {
    children=[]; textContent=''; value=''; style={}; dataset={};
    classList={toggle(){}};
    append(...children){this.children.push(...children);}
    replaceChildren(...children){this.children=children;}
    addEventListener(){}
    setAttribute(){}
    focus(){this.focused=true;}
  }
  const elements=new Map(), requests=[];
  const context=vm.createContext({URL,console,setInterval(){},
    document:{getElementById(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id);},
      createElement(){return new Element();},querySelectorAll(){return [];}},
    fetch(path){requests.push(path);if(path==='/api/state')return new Promise(()=>{});
      return Promise.resolve({ok:true,text:async()=>JSON.stringify('diff --git a/budget b/budget\n+10000')});}
  });
  vm.runInContext(fs.readFileSync(new URL('../src/workbench/web/app.js',import.meta.url),'utf8'),context);
  vm.runInContext(`state={attempts:[{id:'implementation',task_id:'task',role:'builder',head_sha:'abc',artifacts:{tests:'artifact-sha'}}],
    actions:[{id:'proposal',task_id:'task',attempt_id:'implementation',head_sha:'abc',review_scope:'one PR',status:'AWAITING_HUMAN_REVIEW',target:{mode:'GITHUB_DRAFT_PR'},evidence_hash:'hash'}],
    tests:[{attempt_id:'implementation',verdict:'PASS',native_total:119}],judgments:[]};taskId='task';nodeId='proposal';`,context);
  const contents=e=>e.textContent+e.children.map(contents).join('\n');
  return {context,requests,elements,contents};
}

test('proposal diff loads associated exact implementation rather than action id',async()=>{
  const f=fixture();await vm.runInContext("tab='diff';details()",f.context);
  assert.ok(f.requests.includes('/api/diff?node=implementation'));
  assert.match(f.contents(f.elements.get('detail-body')),/diff --git/);
  assert.match(f.contents(f.elements.get('review-intents')),/人工批准此提案/);
});

test('proposal evidence exposes implementation tests and logs',async()=>{
  const f=fixture();await vm.runInContext("tab='evidence';details()",f.context);
  const text=f.contents(f.elements.get('detail-body'));
  assert.match(text,/native_total/);assert.match(text,/119/);assert.match(text,/tests · artifact-s/);
});

test('changed implementation cannot supply evidence or approval for old proposal',async()=>{
  const f=fixture();await vm.runInContext("state.attempts[0].head_sha='changed';tab='diff';details()",f.context);
  assert.equal(f.requests.filter(p=>p.startsWith('/api/diff')).length,0);
  assert.match(f.contents(f.elements.get('detail-body')),/提交已变化/);
  assert.equal(f.elements.get('review-intents').children.length,0);
});

test('empty review opinion explains the refusal beside the button without sending approval',async()=>{
  const f=fixture();await vm.runInContext("tab='evidence';details()",f.context);
  const card=f.elements.get('review-intents').children[0];
  const approve=card.children.find(e=>e.textContent==='人工批准此提案');
  await approve.onclick();
  assert.match(f.contents(card),/请先填写上方审核意见/);
  assert.equal(f.requests.filter(p=>p==='/api/approve').length,0);
  assert.equal(card.children.find(e=>e.textContent==='审核意见（必填）').children[0].focused,true);
});

test('successful owner response immediately replaces approval button with publish step',async()=>{
  const f=fixture();await vm.runInContext("tab='evidence';details()",f.context);
  const card=f.elements.get('review-intents').children[0];
  const input=card.children.find(e=>e.textContent==='审核意见（必填）').children[0];
  input.value='Human-written review opinion';input.oninput();
  const incoming=vm.runInContext('JSON.parse(JSON.stringify(state))',f.context);
  incoming.actions[0].status='HUMAN_APPROVED';
  f.context.fetch=async(path,options)=>{
    if(path==='/api/approve')assert.equal(JSON.parse(options.body).reason,'Human-written review opinion');
    return {ok:true,text:async()=>JSON.stringify(path==='/api/state'?incoming:incoming.actions[0])};
  };
  vm.runInContext('render=()=>{}',f.context);
  await card.children.find(e=>e.textContent==='人工批准此提案').onclick();
  assert.match(f.contents(f.elements.get('review-intents')),/按此次人工批准创建 Draft PR/);
  assert.doesNotMatch(f.contents(f.elements.get('review-intents')),/人工批准此提案/);
});
