'use strict';

// Exercise the shipped history controller and its nested details tree. This
// catches a hidden handoff card without replacing browser/layout verification.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, '../static/js/practice-review.js'), 'utf8');

function controller({state='pending',draft='current saved draft',untouched=false}={}) {
    const listeners = new Map();
    class Node {
        constructor(tag='div') {
            this.tagName=tag.toUpperCase();this.children=[];this.parentElement=null;
            this.dataset={};this.attributes={};this.handlers=new Map();
            this.textContent='';this.value='';this.className='';this.open=false;this.hidden=false;
        }
        append(...nodes) { for(const node of nodes){node.parentElement=this;this.children.push(node);} }
        replaceChildren(...nodes) {for(const node of this.children)node.parentElement=null;this.children=[];this.append(...nodes);}
        setAttribute(name,value) {this.attributes[name]=String(value);}
        addEventListener(name,handler) {if(!this.handlers.has(name))this.handlers.set(name,[]);this.handlers.get(name).push(handler);}
        dispatchEvent(event) {for(const handler of this.handlers.get(event.type)||[])handler(event);}
        querySelector(selector) {return this.querySelectorAll(selector)[0] || null;}
        querySelectorAll(selector) {
            const matches = node => {
                if(selector==='details[open]')return node.tagName==='DETAILS'&&node.open;
                if(selector==='[data-proposal-card]')return Object.hasOwn(node.dataset,'proposalCard');
                if(selector==='[data-proposal-status]')return Object.hasOwn(node.dataset,'proposalStatus');
                if(selector==='[data-proposal-action]')return Object.hasOwn(node.dataset,'proposalAction');
                const card=/^\[data-proposal-card="(\d+)"\]$/.exec(selector);
                if(card)return node.dataset.proposalCard===card[1];
                if(selector==='.review-message')return node.className.split(' ').includes('review-message');
                throw new Error(`DOM fixture does not implement selector ${selector}`);
            };
            const found=[];
            const visit = parent => {for(const child of parent.children){if(matches(child))found.push(child);visit(child);}};
            visit(this);return found;
        }
    }
    const body=new Node('body'),section=new Node('details'),timeline=new Node('div'),status=new Node('p');
    body.append(section);section.append(status,timeline);
    const editor=new Node('textarea'),language=new Node('select'),older=new Node('button');
    editor.value=draft;language.value='cpp';if(untouched)editor.dataset.untouchedTemplate='true';
    body.append(editor,language,older);
    const elements={codeInput:editor,languageSelector:language,practiceReview:section,practiceTimeline:timeline,
        reviewStatus:status,reviewOlder:older,reviewReload:new Node('button')};
    const proposal={id:7,source:'co_create',state,revision:0,base_code:'original base',candidate_code:'AI candidate',
        diff:['-original base','+AI candidate'],latest_test:null};
    let ghostRenders=0;
    const context=vm.createContext({document:{getElementById:id=>elements[id],createElement:tag=>new Node(tag),querySelectorAll:selector=>body.querySelectorAll(selector)},
        window:{addEventListener(name,handler){listeners.set(name,handler);}},
        location:{search:'?problem=CL-TEST-01&language=cpp&co_create_proposal=7'},URLSearchParams,Event,
        getCurrentProblemId:()=> 'CL-TEST-01',renderGhostLayer(){ghostRenders+=1;},
        queueMicrotask,LearningHelpUI:{labels:{}},
        fetch:async()=>({ok:true,json:async()=>({success:true,data:{submissions:[],helps:[],proposals:[proposal],
            active_proposal_id:state==='accepted'?7:null,next_before:null,
            events:[{id:12,kind:'co_create',proposal_id:7,submission_id:null,created_at:'2026-10-17T01:00:00Z',data:{}}]}})})});
    vm.runInContext(script,context,{filename:'practice-review.js'});
    return {section,timeline,editor,status,listeners,get ghostRenders(){return ghostRenders;},
        async load(){listeners.get('practice:user')({detail:{id:42}});for(let i=0;i<6;i++)await new Promise(resolve=>setImmediate(resolve));}};
}

test('handoff reveals its card and every closed details ancestor without replacing an existing draft',async()=>{
    const page=controller();await page.load();
    const card=page.timeline.querySelector('[data-proposal-card="7"]');
    assert.ok(card,'The real controller must render the requested proposal');
    let details=0;
    for(let node=card;node;node=node.parentElement) {
        if(node.tagName==='DETAILS'){assert.equal(node.open,true);details+=1;}
        if(node===page.section)break;
    }
    assert.equal(details,3,'Card, event, and outer practice section all need to be open');
    assert.equal(page.section.hidden,false);
    assert.equal(page.editor.value,'current saved draft');
    assert.equal(page.ghostRenders,0);
    assert.match(page.status.textContent,/核对差异后选择采纳/);
});

test('an untouched template restores only the original baseline and never adopts the candidate',async()=>{
    const page=controller({draft:'language starter',untouched:true});await page.load();
    assert.equal(page.editor.value,'original base');
    assert.notEqual(page.editor.value,'AI candidate');
    assert.equal(page.ghostRenders,1);
});

test('restoring an already accepted handoff reports its saved state without changing edited code',async()=>{
    const page=controller({state:'accepted',draft:'AI candidate with further edits'});await page.load();
    assert.match(page.status.textContent,/已采纳/);assert.match(page.status.textContent,/实际复测记录/);
    assert.doesNotMatch(page.status.textContent,/尚未替换|原代码没有自动替换/);
    assert.equal(page.editor.value,'AI candidate with further edits');
    assert.equal(page.section.open,true);
});
