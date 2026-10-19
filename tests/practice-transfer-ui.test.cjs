'use strict';

// Exercise the shipped controller and its requests with a minimal browser DOM.
// Actual layout and judging are covered by the project's separate browser/API checks.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const script = fs.readFileSync(path.join(root, 'static/js/practice-transfer.js'), 'utf8');
const template = fs.readFileSync(path.join(root, 'templates/practice.html'), 'utf8');
const styles = fs.readFileSync(path.join(root, 'static/css/practice-transfer.css'), 'utf8');
const pairs = JSON.parse(fs.readFileSync(path.join(root, 'data/co_create_learning_pairs.json'), 'utf8'));
const library = JSON.parse(fs.readFileSync(path.join(root, 'data/problem_library.json'), 'utf8'));
const copy = data => JSON.parse(JSON.stringify(data));
const owned = () => ({session_id:'session-7',revision:4,
    source:{session_id:'session-7',problem_id:'CL-BASICS-01',title:'秒数换算',language:'cpp'},
    attempt:{id:'attempt-9',problem_id:'CL-BASICS-02',title:'数位之和',language:'cpp',submissions:[]},
    recap_url:'/co-create.html?session=session-7&learning=recap'});

function page({href,record=owned(),draft,latest=false,getStatus=200,postStatuses=[],deferRead=false}={}) {
    let currentURL = new URL(href || 'http://codelab.test/practice.html?problem=CL-BASICS-02&language=cpp&co_create_session=session-7&transfer_attempt=attempt-9');
    const nodes = new Map(), calls = [], handlers = new Map(), documentHandlers = new Map();
    const storage = new Map();
    if (draft) storage.set('codelab:draft:v2:42:CL-BASICS-02:cpp',JSON.stringify(draft));
    class Node {
        constructor(id) {this.id=id;this.value='';this.hidden=false;this.disabled=false;this.dataset={};this.textContent='';this.attributes={};this.handlers=new Map();}
        addEventListener(type,callback) {if(!this.handlers.has(type))this.handlers.set(type,[]);this.handlers.get(type).push(callback);}
        setAttribute(key,value) {this.attributes[key]=String(value);}
        getAttribute(key) {return this.attributes[key] ?? null;}
        trigger(type) {if(type==='click' && this.disabled)return;for(const callback of this.handlers.get(type)||[])callback({target:this,preventDefault(){},stopImmediatePropagation(){}});}
    }
    for (const match of template.matchAll(/\bid="([^"]+)"/g)) nodes.set(match[1],new Node(match[1]));
    nodes.get('languageSelector').value=currentURL.searchParams.get('language') || 'python';
    nodes.get('codeInput').value=draft?.code || 'public class Main { /* untouched starter */ }';
    nodes.get('codeInput').dataset.untouchedTemplate=draft?'':'true';
    nodes.get('customInput').value=draft?.input || '';
    nodes.get('transferHelpUsage').value='unspecified';
    nodes.get('aiToggleBtn').setAttribute('aria-label','打开达菲郁编程助手');
    const bodyClasses = new Set();
    const document = {
        getElementById(id) {assert.ok(nodes.has(id),`Missing real template element ${id}`);return nodes.get(id);},
        body:{classList:{toggle(name,value){if(value)bodyClasses.add(name);else bodyClasses.delete(name);}}},
        addEventListener(type,callback) {documentHandlers.set(type,callback);},
    };
    const location = {get href(){return currentURL.href;},get origin(){return currentURL.origin;},get search(){return currentURL.search;}};
    const window = {
        addEventListener(type,callback) {if(!handlers.has(type))handlers.set(type,[]);handlers.get(type).push(callback);},
        dispatchEvent(event) {for(const callback of handlers.get(event.type)||[])callback(event);},
    };
    const events=[];
    window.addEventListener('practice:transfer-mode',event=>events.push(copy(event.detail)));
    const response = (data,status=200) => ({ok:status>=200&&status<300,status,json:async()=>copy({success:status<400,data,error:status>=400?'fixture failure':undefined})});
    let pendingRead;
    async function fetch(url,options={}) {
        calls.push({url,method:options.method||'GET'});
        if(url.includes('/latest-submission'))return response(latest?{submission_id:17}:null);
        if(deferRead) {await new Promise(resolve=>{pendingRead=resolve;});deferRead=false;}
        return response(record,getStatus);
    }
    const UserSession = {
        apiErrorMessage:(data,fallback)=>data.error || fallback,
        async csrfFetch(url,options) {
            const body=JSON.parse(options.body);calls.push({url,method:options.method,body});
            const status=postStatuses.shift() || 200;
            if(status===409)record.revision+=1;
            if(status>=400)return response(null,status);
            assert.equal(body.revision,record.revision,'Uses current server revision');
            record.revision+=1;
            return response({revision:record.revision,attempt:record.attempt});
        },
    };
    window.UserSession=UserSession;
    const context=vm.createContext({window,document,location,history:{replaceState(_a,_b,url){currentURL=new URL(url,currentURL);}},
        localStorage:{getItem:key=>storage.get(key) ?? null},UserSession,fetch,URL,URLSearchParams,AbortController,setTimeout,clearTimeout,
        CustomEvent:class{constructor(type,options={}){this.type=type;this.detail=options.detail;}},console});
    vm.runInContext(script,context,{filename:'practice-transfer.js'});
    return {
        node:id=>nodes.get(id),calls,events,storage,bodyClasses,
        get api(){return window.PracticeTransfer;},get url(){return currentURL;},
        emit(type,detail){window.dispatchEvent({type,detail});},
        ready(user={id:42}) {this.emit('practice:user',user);this.emit('practice:problem',{id:'CL-BASICS-02'});},
        release(){pendingRead?.();},
        async settle(){for(let i=0;i<12;i++)await new Promise(resolve=>setImmediate(resolve));},
    };
}

test('curated manifest covers all sixty canonical problems once and has symmetric, answer-free links',()=>{
    assert.equal(pairs.pairs.length,60);
    const catalog=new Map(library.map(item=>[item.id,item]));
    const sources=new Set();
    for(const item of pairs.pairs) {
        assert.equal(item.source_title,catalog.get(item.source_id)?.title);
        assert.equal(item.target_title,catalog.get(item.target_id)?.title);
        assert.equal(catalog.get(item.source_id).category,catalog.get(item.target_id).category);
        assert.notEqual(item.source_id,item.target_id);
        assert.ok(item.reason && item.concept);
        assert.ok(pairs.pairs.some(reverse=>reverse.source_id===item.target_id && reverse.target_id===item.source_id));
        assert.equal(Object.keys(item).sort().join(','),'concept,reason,source_id,source_title,target_id,target_title');
        sources.add(item.source_id);
    }
    assert.equal(sources.size,60);
});

test('mode styles retain the typed-code mirror and pet while putting AI history and ghost suggestions away',()=>{
    assert.ok(!/\.practice-transfer-active\s+#ghostLayer\s*[,\{]/.test(styles),
        'The transparent editor relies on the full typed-code mirror');
    assert.match(styles,/\.practice-transfer-active #ghostLayer \.ghost/);
    assert.match(styles,/\.practice-transfer-active #practiceReview/);
    assert.ok(!/\.practice-transfer-active\s+#(?:aiToggleBtn|petActionMenu)\s*[,\{]/.test(styles));
    assert.ok(template.indexOf("js/practice-transfer.js")>template.indexOf("js/evidence.js"));
});

test('ordinary practice and guest or invalid attempt links retain normal AI access',async()=>{
    const ordinary=page({href:'http://codelab.test/practice.html?problem=CL-BASICS-02&language=cpp'});
    ordinary.ready();await ordinary.settle();
    assert.equal(ordinary.api.blocksAI,false);assert.equal(ordinary.calls.length,0);
    const guest=page();assert.equal(guest.api.pending,true);
    guest.ready(null);await guest.settle();
    assert.equal(guest.api.blocksAI,false);assert.equal(guest.calls.length,0);
    assert.equal(guest.url.searchParams.has('transfer_attempt'),false);
    const invalid=page({getStatus:403});invalid.ready();await invalid.settle();
    assert.equal(invalid.api.active,false);assert.equal(invalid.api.blocksAI,false);
    assert.match(invalid.node('transferStatus').textContent,/普通练习与原草稿仍可使用/);
});

test('only owned matching problem/language activates; safe recap and prior draft notice preserve original work',async()=>{
    const draft={code:'MY EXISTING CPP CODE',input:'203\n'};
    const record=owned();record.recap_url='https://evil.example/leak';
    const app=page({draft,latest:true,record});app.ready();await app.settle();
    assert.equal(app.api.active,true);assert.equal(app.api.pending,false);
    assert.equal(app.node('codeInput').value,draft.code);assert.equal(app.node('customInput').value,draft.input);
    assert.equal(app.node('transferPriorWork').hidden,false);
    assert.match(app.node('transferRecap').href,/^\/co-create.html\?/);
    assert.equal(app.bodyClasses.has('practice-transfer-active'),true);
    assert.equal(app.node('aiToggleBtn').hidden,false,'The companion is still present');
    assert.deepEqual(copy(app.api.context),{session_id:'session-7',attempt_id:'attempt-9',problem_id:'CL-BASICS-02',language:'cpp'});
    assert.ok(app.events.some(event=>event.active && !event.pending));
    const mismatch=owned();mismatch.attempt.language='python';
    const rejected=page({record:mismatch});rejected.ready();await rejected.settle();
    assert.equal(rejected.api.blocksAI,false);assert.equal(rejected.bodyClasses.size,0);
});

test('language change or explicit exit restores ordinary UI without losing per-language draft',async()=>{
    const app=page({draft:{code:'SAVED',input:'-91'}});app.ready();await app.settle();
    app.node('languageSelector').value='python';app.node('languageSelector').trigger('change');
    assert.equal(app.api.blocksAI,false);assert.equal(app.url.searchParams.has('co_create_session'),false);
    assert.equal(app.node('codeInput').value,'SAVED');
    app.emit('practice:submission',{submission_id:39,language:'cpp',problem_id:'CL-BASICS-02'});
    await app.settle();assert.equal(app.calls.filter(call=>call.method==='POST').length,0);
    const exited=page();exited.ready();await exited.settle();exited.node('transferExit').trigger('click');
    assert.equal(exited.api.blocksAI,false);assert.equal(exited.node('aiToggleBtn').getAttribute('aria-label'),'打开达菲郁编程助手');
});

test('actual submission association defaults to unspecified; self-report can be updated without another judge call',async()=>{
    const app=page();app.ready();await app.settle();
    app.emit('practice:submission',{submission_id:31,language:'cpp',problem_id:'CL-BASICS-02'});await app.settle();
    let posts=app.calls.filter(call=>call.method==='POST');
    assert.equal(posts.length,1);assert.deepEqual(posts[0].body,{revision:4,submission_id:31,help_usage:'unspecified'});
    app.node('transferHelpUsage').value='none';app.node('transferHelpUsage').trigger('change');
    app.node('transferLinkSubmission').trigger('click');await app.settle();
    posts=app.calls.filter(call=>call.method==='POST');
    assert.deepEqual(posts[1].body,{revision:5,submission_id:31,help_usage:'none'});
    assert.ok(posts.every(call=>call.url.endsWith('/learning/transfer/attempt-9/submission')));
    assert.match(app.node('transferStatus').textContent,/自述未使用帮助/);
    assert.match(app.node('transferStatus').textContent,/不代表已掌握/);
});

test('one CAS refresh retry uses latest revision; network failure retries linking rather than judging',async()=>{
    const app=page({postStatuses:[409,200]});app.ready();await app.settle();
    app.emit('practice:submission',{submission_id:32});await app.settle();
    const posts=app.calls.filter(call=>call.method==='POST');
    assert.equal(posts.length,2);assert.equal(posts[0].body.revision,4);assert.equal(posts[1].body.revision,5);
    const failed=page({postStatuses:[503,200]});failed.ready();await failed.settle();
    failed.emit('practice:submission',{submission_id:33});await failed.settle();
    assert.match(failed.node('transferStatus').textContent,/无需重新提交判题/);
    assert.equal(failed.node('transferLinkSubmission').disabled,false);
    failed.node('transferLinkSubmission').trigger('click');await failed.settle();
    assert.equal(failed.calls.filter(call=>call.method==='POST').length,2);
    assert.match(failed.node('transferStatus').textContent,/提交 #33 已关联/);
});

test('a late ownership response cannot reactivate after leaving and foreign submissions are ignored',async()=>{
    const delayed=page({deferRead:true});delayed.ready();await delayed.settle();
    delayed.node('languageSelector').value='python';delayed.node('languageSelector').trigger('change');
    delayed.release();await delayed.settle();assert.equal(delayed.api.blocksAI,false);
    const app=page();app.ready();await app.settle();
    app.emit('practice:submission',{submission_id:41,language:'python',problem_id:'CL-BASICS-02'});
    app.emit('practice:submission',{submission_id:42,language:'cpp',problem_id:'CL-BASICS-01'});
    await app.settle();assert.equal(app.calls.filter(call=>call.method==='POST').length,0);
});

test('updated source or target restores ordinary practice, including a CAS refresh after activation',async()=>{
    for(const kind of ['target','source']) {
        const record=owned();
        if(kind==='target')record.attempt.status='target_changed';
        else record.recap={session:{problem_changed:true}};
        const app=page({record,draft:{code:'PRESERVED',input:'203'}});app.ready();await app.settle();
        assert.equal(app.api.blocksAI,false);
        assert.equal(app.url.searchParams.has('transfer_attempt'),false);
        assert.equal(app.node('codeInput').value,'PRESERVED');
        assert.match(app.node('transferStatus').textContent,/题面、用例已更新/);
        assert.equal(app.calls.filter(call=>call.method==='POST').length,0);
    }
    const record=owned();
    const app=page({record,postStatuses:[409,200]});app.ready();await app.settle();
    assert.equal(app.api.active,true);
    record.attempt.status='target_changed';
    app.emit('practice:submission',{submission_id:51});await app.settle();
    assert.equal(app.api.blocksAI,false);
    assert.equal(app.calls.filter(call=>call.method==='POST').length,1,'Changed context is never retried');
    assert.match(app.node('transferStatus').textContent,/题面、用例已更新/);
});

test('post-submission self-report restores only this owned attempt and never claims a generic latest submission',async()=>{
    const ordinaryLatest=page({latest:true});ordinaryLatest.ready();await ordinaryLatest.settle();
    assert.equal(ordinaryLatest.node('transferFollowup').hidden,true);
    assert.equal(ordinaryLatest.node('transferLinkSubmission').disabled,true);
    const record=owned();record.attempt.submissions=[{submission_id:61,record_available:true,help_usage:'hint',submission:{id:61,status:'Accepted'}}];
    const app=page({record});app.ready();await app.settle();
    assert.equal(app.node('transferFollowup').hidden,false);
    assert.equal(app.node('transferHelpUsage').value,'hint');
    assert.match(app.node('transferSubmissionSummary').textContent,/#61 · Accepted/);
    assert.equal(app.calls.filter(call=>call.method==='POST').length,0);
    app.node('transferHelpUsage').value='none';app.node('transferLinkSubmission').trigger('click');await app.settle();
    assert.equal(app.calls.filter(call=>call.method==='POST')[0].body.submission_id,61);
    app.emit('practice:submission',{submission_id:62,language:'cpp',problem_id:'CL-BASICS-02'});await app.settle();
    const second=app.calls.filter(call=>call.method==='POST')[1];
    assert.equal(second.body.submission_id,62);assert.equal(second.body.help_usage,'unspecified','A new submission never inherits the previous self report');
    app.node('transferExit').trigger('click');assert.equal(app.node('transferFollowup').hidden,true);
});
