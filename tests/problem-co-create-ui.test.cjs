'use strict';

// Run the shipped page controller with a deliberately small DOM and in-memory
// transports. This is state/interaction coverage, not a layout/browser substitute.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const script = fs.readFileSync(path.join(root, 'modules/co_create/static/problem-create.js'), 'utf8');
const template = fs.readFileSync(path.join(root, 'modules/co_create/templates/problem_create.html'), 'utf8');
const problem = {id:'CL-TEST-01',title:'输入与输出',description:'<p>读取整数并输出结果。</p>',judge_mode:'integer'};
const user = {id:42,username:'learner'};
const starter = 'import sys\nprint(sys.stdin.read())\n';
const copy = value => JSON.parse(JSON.stringify(value));
const plain = value => String(value).replace(/<[^>]*>/g, '').replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&');

function sessionRecord({mode='examples',code='saved code',input='1'}={}) {
  const examples = [
    {id:'official-1',input:'1\n',expected:'2\n',source:'official',readonly:true},
    {id:'custom-1',input:'7\n',expected:null,source:'unknown',readonly:false},
  ];
  return {
    id:'session-7',mode,problem_id:problem.id,language:'python',legacy:false,
    title:problem.title,revision:4,updated_at:'2026-10-16T01:00:00+00:00',
    problem:{...problem,reference_available:true,changed:false,public_examples:[examples[0]]},
    state:{kind:'problem',examples,generations:[],current_generation_id:null,selected:null,runs:[],events:[],
      practice_context:{code,input_text:input,submission_id:null},
      review:{code,source:code?'student':'empty',model:null,code_revision:1,reflection:'saved reflection',
        judgment:'',prediction:null,prediction_saved:false,prediction_input:null,evidence:[],history:[]}},
  };
}

function controller({guest=false,session=null,href,storage={},storageThrows=false,reviewGenerate,learningGet,reflectionSave,transferStart}={}) {
  const nodes = new Map(), calls = [], listeners = new Map(), values = new Map(Object.entries(storage));
  let currentURL = new URL(href || `http://codelab.test/co-create.html?problem=${problem.id}&language=python`);
  const location = {
    get href() {return currentURL.href;}, set href(value) {currentURL=new URL(value,currentURL);},
    get pathname() {return currentURL.pathname;}, get search() {return currentURL.search;}, get origin() {return currentURL.origin;},
  };
  class Node {
    constructor(tag='div',id='') {
      this.tagName=tag.toUpperCase();this.id=id;this.value='';this.checked=false;this.disabled=false;
      this.hidden=false;this.readOnly=false;this.dataset={};this.attributes={};this.options=[];
      this.children=[];this.handlers=new Map();this._html='';this._text='';
    }
    get innerHTML() {return this._html;}
    set innerHTML(value) {
      this._html=String(value);this._text='';this.children=[];
      if(this.tagName==='SELECT') {
        this.options=[...this._html.matchAll(/<option\b[^>]*value="([^"]*)"[^>]*>([\s\S]*?)<\/option>/g)]
          .map(match=>new Option(plain(match[2]),plain(match[1])));
        this.value=this.options[0]?.value || '';
      }
      for(const match of this._html.matchAll(/<(input|select|textarea)\b[^>]*id="([^"]+)"[^>]*>/gi)) {
        const child=new Node(match[1],match[2]);nodes.set(child.id,child);
        if(child.tagName==='SELECT'){const select=new RegExp('<select\\b[^>]*id="'+child.id+'"[^>]*>([\\s\\S]*?)<\\/select>').exec(this._html);if(select)child.innerHTML=select[1];}
      }
    }
    get textContent() {return this._text+plain(this._html)+this.children.map(child=>child.textContent).join('');}
    set textContent(value) {this._text=String(value);this._html='';this.children=[];}
    append(...children) {this.children.push(...children.map(child=>typeof child==='string'?new TextNode(child):child));}
    prepend(child) {if(this.tagName==='SELECT')this.options.unshift(child);else this.children.unshift(child);}
    replaceChildren(...children) {this._text='';this._html='';this.children=[];this.append(...children);}
    add(option) {this.options.push(option);if(this.options.length===1)this.value=option.value;}
    setAttribute(key,value) {this.attributes[key]=String(value);}
    removeAttribute(key) {delete this.attributes[key];}
    addEventListener(name,handler) {if(!this.handlers.has(name))this.handlers.set(name,[]);this.handlers.get(name).push(handler);}
    dispatchEvent(event) {for(const handler of this.handlers.get(event.type)||[])handler(event);}
    click() {if(!this.disabled)return this.onclick?.({target:this,preventDefault(){}});}
    focus() {document.activeElement=this;}
  }
  class TextNode extends Node {constructor(value){super('#text');this.textContent=value;}}
  class Option extends Node {constructor(text,value){super('option');this.textContent=text;this.value=value;}}
  for(const match of template.matchAll(/<([a-z][a-z0-9-]*)\b([^>]*\bid="([^"]+)"[^>]*)>/gi)) {
    const node=new Node(match[1],match[3]);
    const mode=/data-mode="([^"]+)"/.exec(match[2]);if(mode)node.dataset.mode=mode[1];
    const stage=/data-stage="([^"]+)"/.exec(match[2]);if(stage)node.dataset.stage=stage[1];
    const go=/data-go-stage="([^"]+)"/.exec(match[2]);if(go)node.dataset.goStage=go[1];
    node.hidden=/\bhidden(?:\s|>|$)/.test(match[2]);nodes.set(node.id,node);
  }
  for(const match of template.matchAll(/<select\b[^>]*id="([^"]+)"[^>]*>([\s\S]*?)<\/select>/g))nodes.get(match[1]).innerHTML=match[2];
  const judgments=['correct','incorrect','unsure'].map(value=>{const node=new Node('input');node.value=value;return node;});
  const document = {
    activeElement:null,
    getElementById(id) {assert.ok(nodes.has(id),`Real controller requested missing element ${id}`);return nodes.get(id);},
    createElement(tag) {return new Node(tag);},createTextNode(value) {return new TextNode(value);},
    addEventListener(name,handler) {listeners.set(name,handler);},
    querySelector(selector) {
      if(selector==='[name=judgment]:checked')return judgments.find(node=>node.checked) || null;
      throw new Error(`DOM stub does not implement selector ${selector}`);
    },
    querySelectorAll(selector) {
      if(selector==='button')return [...nodes.values()].filter(node=>node.tagName==='BUTTON');
      if(selector==='[data-mode]')return [...nodes.values()].filter(node=>node.dataset.mode);
      if(selector==='[name=judgment]')return judgments;
      if(selector==='[name=judgment],.reference-option input')return [...judgments,nodes.get('compare-reference'),nodes.get('review-reference')];
      if(selector.startsWith('[data-candidate],[data-edit],[data-delete],[data-use-output]'))return [];
      throw new Error(`DOM stub does not implement selector ${selector}`);
    },
  };
  const localStorage = {
    getItem(key) {return values.has(key)?values.get(key):null;},
    setItem(key,value) {if(storageThrows)throw new Error('quota exceeded');values.set(key,String(value));},removeItem(key) {values.delete(key);},
  };
  function response(data,status=200) {return {ok:status>=200&&status<300,status,json:async()=>copy({success:status<400,data})};}
  function learningData(record) {
    return {session_id:record.id,revision:record.revision,learning:record.state.learning || {version:1,reflection:null},related:[],attempts:[],
      recap:{version:1,session:{id:record.id,title:record.title,problem_id:record.problem_id,language:record.language,mode:record.mode,revision:record.revision},
        baseline:{code:record.state.practice_context.code,source:'draft'},chosen:null,reflection:record.state.learning?.reflection || null,
        runs:record.state.runs,proposals:[],transfer_attempts:[],scope_notes:['已有用例通过不代表所有输入正确。']}};
  }
  const fetch = async (url,options={}) => {
    const parsed = new URL(url,location.href), method=options.method || 'GET';
    const body=options.body===undefined?undefined:JSON.parse(options.body);
    calls.push({url:parsed.pathname+parsed.search,method,body,headers:options.headers});
    if(parsed.pathname==='/api/co-create/catalog')return response({ai_available:true,languages:[{id:'python',label:'Python',version:'Python 3.11',starter_code:starter}]});
    if(parsed.pathname==='/api/current_user')return response({user:guest?null:user});
    if(parsed.pathname==='/api/csrf-token')return response({csrf_token:'test-csrf'});
    if(parsed.pathname==='/api/problems')return response({problems:[problem],categories:[],page:1,pages:1,total:1});
    if(parsed.pathname===`/api/problems/${problem.id}`)return response({problem});
    if(parsed.pathname==='/api/co-create/sessions'&&method==='GET')return response({sessions:session?[session]:[]});
    if(parsed.pathname==='/api/co-create/sessions'&&method==='POST'){session=sessionRecord({mode:body.mode,code:body.code,input:body.input_text});return response({session},201);}
    if(parsed.pathname===`/api/co-create/sessions/${session?.id}`&&method==='GET')return response({session});
    if(parsed.pathname===`/api/co-create/sessions/${session?.id}/learning`&&method==='GET')return response(learningGet?await learningGet(copy(session),learningData(session)):learningData(session));
    if(parsed.pathname===`/api/co-create/sessions/${session?.id}/learning/reflection`&&method==='POST') {
      if(reflectionSave)return reflectionSave(body,copy(session),response);
      assert.equal(body.revision,session.revision);session=copy(session);session.revision+=1;
      session.state.learning={version:1,reflection:{...body,code_hash:'saved-hash',stale:false,saved_at:'2026-10-18T01:00:00+00:00',run_ids:[]}};
      return response({session,...learningData(session)});
    }
    if(parsed.pathname===`/api/co-create/sessions/${session?.id}/learning/transfer`&&method==='POST'&&transferStart)return response(transferStart(body,copy(session),learningData(session)));
    if(parsed.pathname===`/api/co-create/sessions/${session?.id}/review`&&method==='POST') {
      assert.equal(body.revision,session.revision);
      const saved=copy(session),review=saved.state.review;
      saved.revision+=1;
      if(body.code!==undefined&&body.code!==review.code) {
        review.history.push({code:review.code,code_revision:review.code_revision,source:review.source,model:review.model});
        review.code=body.code;review.code_revision+=1;review.source='student';review.model=null;
      }
      for(const key of ['reflection','judgment','prediction','prediction_input'])if(Object.hasOwn(body,key))review[key]=body[key];
      if(Object.hasOwn(body,'prediction'))review.prediction_saved=true;
      session=saved;
      return response({session});
    }
    if(parsed.pathname===`/api/co-create/sessions/${session?.id}/review-generate`&&method==='POST'&&reviewGenerate)return response({session:reviewGenerate(body,copy(session))});
    throw new Error(`Unexpected mocked fetch ${method} ${parsed.pathname}`);
  };
  let timerId=0;
  const timers = new Map();
  const downloads=[];
  class BrowserURL extends URL {static createObjectURL(blob){downloads.push(blob);return 'blob:test-'+downloads.length;}static revokeObjectURL(){}}
  const context = vm.createContext({document,location,history:{replaceState(_state,_unused,url){location.href=String(url);}},
    localStorage,fetch,URL:BrowserURL,URLSearchParams,AbortController,Option,Blob,console,
    DOMParser:class {parseFromString(value){return {body:{textContent:plain(value)}};}},
    setTimeout(callback){const id=++timerId;timers.set(id,callback);return id;},clearTimeout(id){timers.delete(id);}});
  vm.runInContext(script,context,{filename:'problem-create.js'});
  return {node:id=>document.getElementById(id),calls,storage:values,location,downloads,
    async clickData(dataset){const node=new Node('button');node.dataset=dataset;node.closest=()=>node;listeners.get('click')({target:node});for(let i=0;i<8;i++)await new Promise(resolve=>setImmediate(resolve));},
    async submit(id){document.getElementById(id).onsubmit({preventDefault(){}});for(let i=0;i<8;i++)await new Promise(resolve=>setImmediate(resolve));},
    async settle(){for(let i=0;i<8;i++)await new Promise(resolve=>setImmediate(resolve));},
  };
}

test('guest session deep link survives the login next link and login action',async()=>{
  const page=controller({guest:true,href:`http://codelab.test/co-create.html?session=session-7&mode=review&problem=${problem.id}&language=python`});
  await page.settle();
  const login=new URL(page.node('account-link').href,'http://codelab.test');
  const next=new URL(login.searchParams.get('next'),'http://codelab.test');
  assert.equal(next.searchParams.get('session'),'session-7');
  assert.equal(next.searchParams.get('mode'),'review');
  assert.match(page.node('notice').textContent,/登录原账号后可恢复/);
  await page.node('new-session').click();
  const redirected=new URL(page.location.href);
  assert.equal(redirected.pathname,'/login.html');
  assert.equal(new URL(redirected.searchParams.get('next'),'http://codelab.test').searchParams.get('session'),'session-7');
  assert.equal(page.calls.filter(call=>call.method==='POST').length,0);
});

test('fresh examples send no echo template while real stored drafts remain the baseline',async()=>{
  const page=controller();await page.settle();await page.node('new-session').click();
  const created=page.calls.find(call=>call.method==='POST'&&call.url==='/api/co-create/sessions');
  assert.equal(created.body.mode,'examples');assert.equal(created.body.code,'');
  assert.notEqual(created.body.code,starter);
  assert.match(page.node('context-note').textContent,/从当前题目新建/);
  const draft={code:'print("student draft")',input:'9\n'};
  const saved=controller({storage:{[`codelab:draft:v2:${user.id}:${problem.id}:python`]:JSON.stringify(draft)}});
  await saved.settle();await saved.node('new-session').click();
  const withDraft=saved.calls.find(call=>call.method==='POST'&&call.url==='/api/co-create/sessions');
  assert.equal(withDraft.body.code,draft.code);assert.equal(withDraft.body.input_text,draft.input);
});

test('failed AI review generation preserves unsaved code and reflection at the new server revision',async()=>{
  const record=sessionRecord({mode:'review'});
  const page=controller({session:record,href:`http://codelab.test/co-create.html?session=${record.id}&mode=review`,
    reviewGenerate(_body,current){current.revision+=2;current.state.current_generation_id='failed-generation';current.state.generations.push({id:'failed-generation',status:'failed',candidates:[],error:'真实 AI 请求失败'});return current;}});
  await page.settle();
  assert.equal(page.node('review-code').value,'saved code');
  page.node('review-code').value='print("unsaved edit")';page.node('review-reflection').value='尚未保存的边界思考';
  page.node('review-input').value='10';page.node('review-prediction').value='11';
  await page.node('review-generate').click();
  assert.equal(page.node('review-code').value,'print("unsaved edit")');
  assert.equal(page.node('review-reflection').value,'尚未保存的边界思考');
  assert.equal(page.node('review-input').value,'10');assert.equal(page.node('review-prediction').value,'11');
  const stored=JSON.parse(page.storage.get(`codelab:co-create:forms:${user.id}:${record.id}`));
  assert.equal(stored.revision,7);assert.equal(stored.form['review-code'],'print("unsaved edit")');
  assert.equal(stored.form['review-reflection'],'尚未保存的边界思考');
  assert.match(page.node('notice').textContent,/真实 AI 请求失败/);
});

test('successful AI review generation first saves the current edited code as its baseline',async()=>{
  const record=sessionRecord({mode:'review'}),edited='print("latest student draft")';
  const page=controller({session:record,href:`http://codelab.test/co-create.html?session=${record.id}&mode=review`,
    reviewGenerate(body,current){
      assert.equal(body.revision,5);
      assert.equal(current.state.review.code,edited);
      assert.equal(current.state.review.reflection,'新的思路');
      current.revision+=2;
      current.state.current_generation_id='success-generation';
      current.state.generations.push({id:'success-generation',status:'ready',source:'ai',candidates:[]});
      current.state.review.history.push({code:current.state.review.code,code_revision:current.state.review.code_revision,source:'student',model:null});
      current.state.review.code='print("AI candidate")';current.state.review.source='ai';current.state.review.model='test-model';
      return current;
    }});
  await page.settle();
  page.node('review-code').value=edited;page.node('review-reflection').value='新的思路';
  await page.node('review-generate').click();
  const mutations=page.calls.filter(call=>call.method==='POST'&&call.url.startsWith('/api/co-create/sessions/'));
  assert.deepEqual(mutations.map(call=>call.url.split('/').at(-1)),['review','review-generate']);
  assert.equal(mutations[0].body.code,edited);
  assert.equal(page.node('review-code').value,'print("AI candidate")');
  assert.match(page.node('review-source').textContent,/AI 实时生成/);
});

test('official examples remain readonly and agreeing unknown outputs remain unverified',async()=>{
  const record=sessionRecord();
  record.state.runs.push({id:'unknown-comparison',kind:'compare',input:'7',expected:null,expected_source:'unknown',
    different:false,note:'没有已确认的标准输出；结果一致也不能证明正确。',created_at:'2026-10-16T01:02:00+00:00',
    results:[{candidate_id:'a',success:true,output:'7\n',passed:null,verdict:'unverified'},
      {candidate_id:'b',success:true,output:'7\n',passed:null,verdict:'unverified'}]});
  const page=controller({session:record,href:`http://codelab.test/co-create.html?session=${record.id}`});
  await page.settle();
  const examples=page.node('example-list').innerHTML;
  assert.doesNotMatch(examples,/data-(?:edit|delete)="official-1"/);
  assert.match(examples,/data-edit="custom-1"/);assert.match(examples,/data-delete="custom-1"/);
  const result=page.node('compare-results').textContent;
  assert.match(result,/本次输出没有差异/);assert.match(result,/正确性待验证/);
  assert.match(result,/结果一致也不能证明正确/);assert.doesNotMatch(result,/与题目依据相符|全部通过/);
});

test('learning stages allow return and skipping without saving or overwriting the edited review',async()=>{
  const record=sessionRecord({mode:'review'});
  const page=controller({session:record,href:`http://codelab.test/co-create.html?session=${record.id}&stage=verify`});
  await page.settle();
  page.node('review-code').value='unsaved original edit';
  page.node('review-input').value='42';
  page.node('reflection-reason').value='我自己的判断';
  page.node('reflection-reason').dispatchEvent({type:'input'});
  await page.node('stage-tab-explain').click();
  assert.equal(page.node('stage-verify').hidden,true);assert.equal(page.node('stage-explain').hidden,false);
  assert.equal(page.node('stage-tab-explain').attributes['aria-selected'],'true');
  await page.node('stage-tab-transfer').click();await page.settle();
  await page.node('stage-tab-verify').click();
  assert.equal(page.node('review-code').value,'unsaved original edit');
  assert.equal(page.node('review-input').value,'42');assert.equal(page.node('reflection-reason').value,'我自己的判断');
  assert.equal(page.calls.filter(c=>c.method==='POST').length,0);
  assert.equal(new URL(page.location.href).searchParams.get('stage'),'verify');
  const stored=JSON.parse(page.storage.get(`codelab:co-create:forms:${user.id}:${record.id}`));
  assert.equal(stored.form['review-code'],'unsaved original edit');
  assert.equal(stored.form['reflection-reason'],'我自己的判断');
});

test('saving an explanation binds the currently edited review code and preserves optional blanks',async()=>{
  const record=sessionRecord({mode:'review'});
  const page=controller({session:record,href:`http://codelab.test/co-create.html?session=${record.id}&stage=explain`});
  await page.settle();page.node('review-code').value='print("latest version")';
  page.node('reflection-reason').value='修改余数计算';page.node('reflection-boundary').value='';page.node('reflection-next-check').value='0 和 3600';
  await page.submit('reflection-form');
  const mutations=page.calls.filter(c=>c.method==='POST');
  assert.deepEqual(mutations.map(c=>c.url.split('/').at(-1)),['review','reflection']);
  assert.equal(mutations[0].body.code,'print("latest version")');
  assert.equal(mutations[1].body.candidate_id,'review');assert.equal(mutations[1].body.reason,'修改余数计算');
  assert.equal(mutations[1].body.boundary,'');assert.equal(mutations[1].body.next_check,'0 和 3600');
  assert.equal(mutations[1].body.revision,5);
  assert.equal(page.node('review-code').value,'print("latest version")');
  assert.match(page.node('reflection-saved-status').textContent,/已保存你的解释/);
  assert.match(page.node('recap-content').textContent,/修改余数计算/);
  assert.equal(page.calls.some(c=>/handoff|\/select|generate/.test(c.url)),false);
});

test('failed explanation save leaves student wording and unsaved work available for retry',async()=>{
  const record=sessionRecord({mode:'review'});
  const page=controller({session:record,href:`http://codelab.test/co-create.html?session=${record.id}&stage=explain`,
    reflectionSave(){return {ok:false,status:503,json:async()=>({success:false,error:{message:'记录暂时无法保存'}})};}});
  await page.settle();page.node('reflection-reason').value='不能被失败吞掉的解释';page.node('reflection-boundary').value='空输入不是合法输入';
  page.node('review-code').value='my edited version';
  await page.submit('reflection-form');
  assert.equal(page.node('reflection-reason').value,'不能被失败吞掉的解释');
  assert.equal(page.node('reflection-boundary').value,'空输入不是合法输入');
  assert.equal(page.node('review-code').value,'my edited version');
  assert.match(page.node('notice').textContent,/记录暂时无法保存/);
  assert.equal(page.node('save-learning-reflection').disabled,false);
});

test('learning refresh does not replace a local explanation with older server text',async()=>{
  let resolveRead;
  const gate=new Promise(resolve=>{resolveRead=resolve;});
  const record=sessionRecord({mode:'review'});
  record.state.learning={version:1,reflection:{candidate_id:'review',reason:'以前保存的解释',boundary:'',next_check:'',saved_at:'2026-10-18T01:00:00Z',stale:false}};
  const page=controller({session:record,href:`http://codelab.test/co-create.html?session=${record.id}&stage=explain`,
    async learningGet(_record,bundle){await gate;return bundle;}});
  await page.settle();page.node('reflection-reason').value='正在补充的新理由';
  page.node('reflection-reason').dispatchEvent({type:'input'});
  resolveRead();await page.settle();
  assert.equal(page.node('reflection-reason').value,'正在补充的新理由');
  assert.match(page.node('recap-content').textContent,/以前保存的解释/);
  assert.doesNotMatch(page.node('recap-content').textContent,/正在补充的新理由/);
});

test('stale explanations are visibly historical and unsaved review edits warn before rebinding',async()=>{
  const record=sessionRecord({mode:'review'});
  record.state.learning={version:1,reflection:{candidate_id:'review',reason:'旧版本理由',code_hash:'old',boundary:'',next_check:'',stale:true,saved_at:'2026-10-18T01:00:00Z'}};
  const page=controller({session:record,href:`http://codelab.test/co-create.html?session=${record.id}&stage=recap`});
  await page.settle();
  assert.equal(page.node('stage-recap').hidden,false);
  assert.match(page.node('reflection-saved-status').textContent,/较早代码/);
  assert.match(page.node('recap-content').textContent,/不作为当前代码解释/);
  page.node('review-code').value='uncommitted code';page.node('review-code').dispatchEvent({type:'input'});
  assert.match(page.node('reflection-binding').textContent,/存在未保存代码/);
  assert.equal(page.calls.filter(c=>c.method==='POST').length,0);
});

test('independent practice starts from an actual related question without carrying an answer',async()=>{
  const record=sessionRecord({mode:'review'});
  const page=controller({session:record,href:`http://codelab.test/co-create.html?session=${record.id}&stage=transfer`,
    learningGet(_record,bundle){bundle.related=[{problem_id:'CL-RELATED-01',title:'关联练习',focus:'取余',reason:'相同概念，改变输入条件'}];return bundle;},
    transferStart(body,current,bundle){assert.deepEqual(body,{revision:4,problem_id:'CL-RELATED-01'});return {...bundle,session:current,practice_url:'/practice.html?problem=CL-RELATED-01&language=python&co_create_session=session-7&transfer_attempt=attempt-1',attempt:{id:'attempt-1'}};}});
  await page.settle();assert.match(page.node('transfer-related').textContent,/人工配置关联题/);
  await page.clickData({transfer:'CL-RELATED-01'});
  const target=new URL(page.location.href);assert.equal(target.pathname,'/practice.html');
  assert.equal(target.searchParams.get('transfer_attempt'),'attempt-1');
  assert.equal(target.searchParams.has('code'),false);assert.equal(target.searchParams.has('co_create_proposal'),false);
  assert.equal(page.node('review-code').value,'saved code');
});

test('unavailable learning records leave the established verification flow usable',async()=>{
  const record=sessionRecord({mode:'review'});
  const page=controller({session:record,href:`http://codelab.test/co-create.html?session=${record.id}`,
    learningGet(){throw new Error('legacy endpoint unavailable');}});
  await page.settle();assert.equal(page.node('review-code').value,'saved code');
  assert.equal(page.node('run-review').disabled,false);
  assert.match(page.node('learning-status').textContent,/验证功能与本页草稿仍可使用/);
  assert.doesNotMatch(page.node('recap-content').textContent,/掌握百分比|能力提升|全部通过/);
});

test('nested actual transfer results and unavailable records stay truthful in the recap and exports',async()=>{
  const record=sessionRecord({mode:'review'});
  const attempts=[{id:'attempt-2',problem_id:'CL-RELATED-01',title:'关联题',language:'python',started_at:'2026-10-18T01:00:00Z',status:'submitted',
    submissions:[{submission_id:98,help_usage:'hint',record_available:true,submission:{id:98,status:'Accepted',created_at:'2026-10-18T02:00:00Z'}},
      {submission_id:99,help_usage:'none',record_available:false,submission:null}]}];
  const page=controller({session:record,href:`http://codelab.test/co-create.html?session=${record.id}&stage=recap`,
    learningGet(_record,bundle){bundle.attempts=attempts;bundle.recap.transfer_attempts=attempts;return bundle;}});
  await page.settle();
  assert.match(page.node('transfer-attempts').textContent,/提交 #98 · Accepted/);
  assert.match(page.node('recap-content').textContent,/使用过提示（本人自述）/);
  assert.match(page.node('recap-content').textContent,/原提交记录已不可用/);
  assert.doesNotMatch(page.node('recap-content').textContent,/状态未记录|已经掌握/);
  await page.node('download-recap-md').click();
  const markdown=await page.downloads.at(-1).text();
  assert.match(markdown,/提交 #98：Accepted；使用过提示（本人自述）/);
  assert.match(markdown,/提交 #99：原提交记录已不可用/);
  await page.node('download-recap-json').click();
  const exported=JSON.parse(await page.downloads.at(-1).text());
  assert.equal(exported.recap.transfer_attempts[0].submissions[0].submission.status,'Accepted');
  assert.equal(exported.recap.transfer_attempts[0].submissions[1].submission,null);
});

test('refresh and navigation retain unsaved attempt identifiers and assistance self reports',async()=>{
  const record=sessionRecord({mode:'review'});
  const attempt={id:'attempt-3',problem_id:'CL-RELATED-01',title:'关联题',language:'python',started_at:'2026-10-18T01:00:00Z',status:'in_progress',submissions:[]};
  const page=controller({session:record,href:`http://codelab.test/co-create.html?session=${record.id}&stage=transfer`,
    learningGet(_record,bundle){bundle.attempts=[attempt];bundle.recap.transfer_attempts=[attempt];return bundle;}});
  await page.settle();page.node('attempt-submission-attempt-3').value='123';page.node('attempt-help-attempt-3').value='hint';
  page.node('attempt-help-attempt-3').dispatchEvent({type:'change'});
  await page.node('refresh-learning').click();await page.settle();
  assert.equal(page.node('attempt-submission-attempt-3').value,'123');assert.equal(page.node('attempt-help-attempt-3').value,'hint');
  await page.node('stage-tab-verify').click();await page.node('stage-tab-transfer').click();await page.settle();
  assert.equal(page.node('attempt-submission-attempt-3').value,'123');
  assert.equal(page.calls.filter(c=>c.method==='POST').length,0);
});

test('a legacy summary missing verification totals never prints undefined counts',async()=>{
  const record=sessionRecord({mode:'review'});
  record.state.runs=[{id:'older-summary',kind:'verify',cases:[]}];
  const page=controller({session:record,href:`http://codelab.test/co-create.html?session=${record.id}&stage=recap`});
  await page.settle();
  assert.match(page.node('recap-content').textContent,/未记录 \/ 未记录 项通过/);
  assert.doesNotMatch(page.node('recap-content').textContent,/undefined|NaN/);
});

test('review explanation evidence only counts the exact saved code revision and none for an unsaved edit',async()=>{
  const record=sessionRecord({mode:'review'});
  record.state.review.code_revision=3;
  record.state.runs=[{id:'old-run',kind:'review',code_revision:2,success:true,output:'old'},
    {id:'current-run',kind:'review',code_revision:3,success:true,output:'current'}];
  const page=controller({session:record,href:`http://codelab.test/co-create.html?session=${record.id}&stage=explain`});
  await page.settle();
  assert.match(page.node('reflection-evidence').textContent,/已有 1 条相关运行/);
  page.node('review-code').value='not the saved version';page.node('review-code').dispatchEvent({type:'input'});
  assert.match(page.node('reflection-evidence').textContent,/尚无相关运行依据/);
  assert.doesNotMatch(page.node('reflection-evidence').textContent,/已有 [12] 条相关运行/);
});

test('observed site assistance remains separate from a student self report of none in screen and Markdown',async()=>{
  const record=sessionRecord({mode:'review'});
  const attempts=[{id:'attempt-help',problem_id:'CL-RELATED-01',title:'关联题',language:'python',started_at:'2026-10-18T01:00:00Z',status:'submitted',
    submissions:[{submission_id:101,help_usage:'none',record_available:true,submission:{id:101,status:'Accepted'},
      recorded_help:[{id:9,source:'ai',level:4,shown_at:'2026-10-18T01:20:00Z'}]}]}];
  const page=controller({session:record,href:`http://codelab.test/co-create.html?session=${record.id}&stage=recap`,
    learningGet(_record,bundle){bundle.attempts=attempts;bundle.recap.transfer_attempts=attempts;return bundle;}});
  await page.settle();
  assert.match(page.node('recap-content').textContent,/未使用 AI 帮助（本人自述）/);
  assert.match(page.node('recap-content').textContent,/AI 实时生成 \/ 完整参考 \/ 已展示/);
  assert.match(page.node('recap-content').textContent,/与本人自述分别保留/);
  await page.node('download-recap-md').click();
  assert.match(await page.downloads.at(-1).text(),/本站帮助记录：AI 实时生成 \/ 完整参考 \/ 已展示/);
});

test('persistent save feedback distinguishes local edits from an actual account save',async()=>{
  const record=sessionRecord({mode:'review'});
  const page=controller({session:record,href:`http://codelab.test/co-create.html?session=${record.id}`});
  await page.settle();
  assert.match(page.node('workspace-save-status').textContent,/账户记录 v4 · 本机草稿已保存/);
  page.node('review-code').value='edited by student';page.node('review-code').dispatchEvent({type:'input'});
  assert.match(page.node('workspace-save-status').textContent,/有修改尚未保存到账户/);
  assert.equal(page.calls.filter(c=>c.method==='POST').length,0);
  await page.node('save-review').click();await page.settle();
  assert.match(page.node('workspace-save-status').textContent,/账户记录 v5/);
  assert.doesNotMatch(page.node('workspace-save-status').textContent,/有修改尚未保存到账户/);
  page.node('review-input').value='local test input';page.node('review-input').dispatchEvent({type:'input'});
  assert.match(page.node('workspace-save-status').textContent,/测试输入单独保留在本机/);
});

test('failed local storage reports the failure without erasing the student input',async()=>{
  const record=sessionRecord({mode:'review'});
  const page=controller({session:record,storageThrows:true,href:`http://codelab.test/co-create.html?session=${record.id}`});
  await page.settle();
  page.node('reflection-reason').value='words I need to keep';page.node('reflection-reason').dispatchEvent({type:'input'});
  assert.match(page.node('workspace-save-status').textContent,/本机草稿保存失败/);
  assert.doesNotMatch(page.node('workspace-save-status').textContent,/本机草稿已保存/);
  assert.equal(page.node('reflection-reason').value,'words I need to keep');
  assert.equal(page.node('save-learning-reflection').disabled,false);
});

test('an older local draft survives a newer server revision and asks for reconciliation before a write',async()=>{
  const record=sessionRecord({mode:'review'});
  const stored={revision:3,form:{'review-code':'OLD LOCAL WORK','reflection-reason':'unsaved explanation'}};
  const page=controller({session:record,storage:{[`codelab:co-create:forms:${user.id}:${record.id}`]:JSON.stringify(stored)},href:`http://codelab.test/co-create.html?session=${record.id}`});
  await page.settle();
  assert.equal(page.node('review-code').value,'OLD LOCAL WORK');
  assert.equal(page.node('reflection-reason').value,'unsaved explanation');
  assert.equal(page.node('save-review').disabled,true);
  assert.match(page.node('notice').textContent,/较早版本/);
  assert.equal(page.node('draft-recovery').hidden,false);
  assert.match(page.node('draft-server-content').textContent,/账户记录 v4/);
  assert.match(page.node('draft-server-content').textContent,/saved code/);
  assert.doesNotMatch(page.node('draft-server-content').textContent,/OLD LOCAL WORK/);
  const recover=page.node('notice').children.find(n=>n.tagName==='BUTTON');assert.ok(recover);
  await recover.click();await page.settle();
  assert.equal(page.node('review-code').value,'OLD LOCAL WORK');
  assert.equal(page.node('save-review').disabled,false);
  assert.equal(page.calls.filter(c=>c.method==='POST').length,0);
});

test('the compact companion repeats local stage guidance without requesting a model',async()=>{
  const page=controller({guest:true});await page.settle();
  await page.node('stage-tab-explain').click();
  assert.equal(page.node('mobile-pet-message').textContent,page.node('pet-message').textContent);
  assert.match(page.node('mobile-pet-preview').textContent,/你自己的话/);
  await page.node('mobile-pet-encourage').click();
  assert.equal(page.node('mobile-pet-message').textContent,page.node('pet-message').textContent);
  assert.equal(page.calls.filter(c=>c.method==='POST').length,0);
});

test('a revision change outside the editable form preserves test input without a false stale-draft lock',async()=>{
  const record=sessionRecord({mode:'review'});
  const stored={revision:3,form:{'review-code':'saved code','review-reflection':'saved reflection','review-input':'local test only'}};
  const page=controller({session:record,storage:{[`codelab:co-create:forms:${user.id}:${record.id}`]:JSON.stringify(stored)},href:`http://codelab.test/co-create.html?session=${record.id}`});
  await page.settle();
  assert.equal(page.node('review-input').value,'local test only');
  assert.equal(page.node('save-review').disabled,false);
  assert.equal(page.node('draft-recovery').hidden,true);
  assert.doesNotMatch(page.node('workspace-save-status').textContent,/较早版本|需核对/);
  assert.equal(page.calls.filter(c=>c.method==='POST').length,0);
});

test('using a run output opens the optional test form and saves a local draft without posting an answer',async()=>{
  const record=sessionRecord();
  record.state.runs=[{id:'run-output',kind:'compare',input:'8',results:[{output:'16',success:true}]}];
  const page=controller({session:record,href:`http://codelab.test/co-create.html?session=${record.id}`});
  await page.settle();
  await page.clickData({useOutput:'0',run:'run-output'});
  assert.equal(page.node('example-compose').open,true);
  assert.equal(page.node('example-input').value,'8');
  assert.equal(page.node('example-expected').value,'16');
  assert.match(page.node('workspace-save-status').textContent,/有修改尚未保存到账户/);
  assert.equal(page.calls.filter(c=>c.method==='POST').length,0);
});

test('recap facts count actual available submissions and keep blank reflection blank',async()=>{
  const record=sessionRecord({mode:'review'});
  const page=controller({session:record,href:`http://codelab.test/co-create.html?session=${record.id}&stage=recap`,learningGet(_record,bundle){
    bundle.recap.reflection={reason:'',boundary:'',next_check:'',stale:false};
    bundle.recap.transfer_attempts=[{submissions:[{submission_id:1,record_available:true,submission:{status:'Accepted'}},{submission_id:2,record_available:false,submission:null}]}];
    return bundle;
  }});await page.settle();
  assert.match(page.node('recap-overview').textContent,/内容留空/);
  assert.match(page.node('recap-overview').textContent,/1 次提交/);
  assert.doesNotMatch(page.node('recap-overview').textContent,/已经掌握|100%|2 次提交/);
  await page.node('recap-next').click();assert.equal(page.node('stage-verify').hidden,false,'A record without a run returns to verification first');
});
