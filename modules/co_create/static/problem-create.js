(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const params = new URLSearchParams(location.search);
  const state = {user:null,csrf:null,ai:false,languages:[],problems:[],page:1,pages:1,sessions:[],session:null,
    mode:params.get('mode') === 'review' ? 'review' : 'examples',busy:false,conflict:false,editing:null,queryTicket:0,topicTicket:0,
    stage:['verify','explain','transfer','recap'].includes(params.get('stage'))?params.get('stage'):'verify',learning:null,learningTicket:0,renderedAttempts:[],attemptDrafts:{},localSaved:null,olderDraft:false};
  const names = {python:'Python',cpp:'C++'};
  const sources = {ai:'AI 实时生成',student:'你的代码',draft:'带入草稿',submission:'历史提交',official:'题目公开样例',user:'你的期望',reference:'内置参考程序',unknown:'正确性待验证',teaching:'原教学样例'};
  const fields = ['example-input','example-expected','compare-input','compare-expected','review-code','review-input','review-prediction','review-expected','review-reflection','reflection-target','reflection-reason','reflection-boundary','reflection-next-check'];
  const currentGeneration = () => state.session?.state.generations?.find(g => g.id === state.session.state.current_generation_id);
  const problemId = () => $('problem-select').value;
  const language = () => $('language-select').value;
  const text = value => typeof value === 'string' ? value : JSON.stringify(value,null,2) ?? '';
  const time = value => value ? new Date(value).toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}) : '';
  function practiceURL(id,lang,proposal=null) {
    let target=new URL('/practice.html',location.origin);
    try {const original=new URL(params.get('return_to') || '',location.origin);if(original.origin===location.origin && original.pathname==='/practice.html' && original.searchParams.get('problem')===id)target=original;}catch(_){}
    target.searchParams.set('problem',id);target.searchParams.set('language',lang);
    target.searchParams.delete('co_create_proposal');
    if(proposal)target.searchParams.set('co_create_proposal',proposal);
    return target.pathname+target.search;
  }
  const inputBody = prefix => ({input:$(prefix+'-input').value,input_validated:$(prefix+'-reference').checked,
    ...($(prefix+'-expected').value !== '' ? {expected:$(prefix+'-expected').value} : {})});
  function account() {
    $('account-link').textContent = state.user ? `${state.user.username} ↗` : '登录后保存记录 ↗';
    const target=new URL(location.href);
    if(!state.user && params.get('session') && !state.session)target.searchParams.set('session',params.get('session'));
    $('account-link').href = state.user ? '/profile.html' : '/login.html?next='+encodeURIComponent(target.pathname+target.search);
  }
  async function request(path, options={}) {
    const controller = new AbortController(), timer = setTimeout(()=>controller.abort(),180000);
    try {
      const headers = {Accept:'application/json'};
      if (options.method && options.method !== 'GET') {
        if (!state.csrf) {
          const response = await fetch('/api/csrf-token',{credentials:'same-origin',signal:controller.signal});
          const result = await response.json(); state.csrf = result.data?.csrf_token || result.csrf_token;
          if (!response.ok || !state.csrf) throw new Error('登录状态未确认，请重新登录后继续。');
        }
        headers['Content-Type']='application/json'; headers['X-CSRF-Token']=state.csrf;
      }
      const response = await fetch(path.startsWith('/api/') ? path : '/api/co-create'+path,
        {...options,headers,credentials:'same-origin',signal:controller.signal,body:options.body === undefined ? undefined : JSON.stringify(options.body)});
      const result = await response.json();
      if (!response.ok || result.success === false) {
        const error = new Error(result.error?.message || '请求未完成，请重试。'); error.status=response.status; error.code=result.error?.code;
        if (response.status===401) state.csrf=null;
        throw error;
      }
      return result.data || result;
    } catch (error) {
      if (controller.signal.aborted || error.name==='TypeError') {
        const unknown = new Error('连接或等待已中断，服务器任务的完成状态尚不确定。输入已保留，请读取最新记录再决定是否重试。'); unknown.code='NETWORK_STATE_UNKNOWN'; throw unknown;
      }
      throw error;
    } finally { clearTimeout(timer); }
  }
  function capture() {
    const attemptForms={...state.attemptDrafts};state.renderedAttempts.forEach(id=>{const submission=$('attempt-submission-'+id),help=$('attempt-help-'+id);if(submission && help)attemptForms[id]={submission:submission.value,help:help.value};});
    return {...Object.fromEntries(fields.map(id=>[id,$(id).value])),judgment:document.querySelector('[name=judgment]:checked')?.value || '',editing:state.editing,compareReference:$('compare-reference').checked,reviewReference:$('review-reference').checked,attemptForms};
  }
  function restore(draft) {
    if (!draft) return;
    fields.forEach(id=>{if(Object.hasOwn(draft,id)) $(id).value=draft[id];});
    document.querySelectorAll('[name=judgment]').forEach(node=>{node.checked=node.value===draft.judgment;});
    state.editing=draft.editing || null;
    $('compare-reference').checked=!!draft.compareReference;$('review-reference').checked=!!draft.reviewReference;
    state.attemptDrafts=draft.attemptForms || {};restoreAttemptForms();
  }
  function formKey() { return state.session ? `codelab:co-create:forms:${state.user?.id}:${state.session.id}` : null; }
  function accountChangesPending() {
    if(!state.session)return false;
    const review=state.session.state.review || {},reflection=state.session.state.learning?.reflection || state.learning?.learning?.reflection;
    if(state.mode==='review' && ($('review-code').value!==(review.code || '') || $('review-reflection').value!==(review.reflection || '') || (document.querySelector('[name=judgment]:checked')?.value || '')!==(review.judgment || '')))return true;
    if($('example-input').value || $('example-expected').value)return true;
    if(reflection && $('reflection-target').value!==reflection.candidate_id && ['reason','boundary','next-check'].some(key=>$('reflection-'+key).value.trim()))return true;
    return ['reason','boundary','next-check'].some(key=>$('reflection-'+key).value!==(reflection?.[key.replace('-','_')] || ''));
  }
  function renderSaveStatus() {
    const node=$('workspace-save-status');
    let message=state.user?'选择「选题 / 新建」开始，或恢复自己的账户记录。':'选择「选题 / 新建」开始，登录后可保存到账户。',kind='idle';
    if(state.session){
      const pending=accountChangesPending();
      message=`账户记录 v${state.session.revision} · ${state.localSaved===false?'本机草稿保存失败，请勿直接关闭页面':state.localSaved===true?'本机草稿已保存':'输入暂留本页'}`;
      if(state.conflict){message+=' · 需核对最新记录后继续';kind='warning';}
      else if(pending){message+=' · 有修改尚未保存到账户';kind='pending';}
      else message+=' · 测试输入单独保留在本机';
      if(state.localSaved===false)kind='warning';
      if(state.olderDraft)message+=' · 已保留较早版本的本机输入';
    }
    if(node.textContent!==message)node.textContent=message;
    node.dataset.state=kind;
    $('draft-recovery').hidden=!state.session || !state.olderDraft;
    if(state.session && state.olderDraft){
      const saved=state.session.state,reflection=saved.learning?.reflection;
      $('draft-server-content').textContent=`账户记录 v${state.session.revision}\n\n当前已保存代码：\n${saved.review?.code || currentGeneration()?.candidates?.[0]?.code || '未保存代码'}\n\n本人已保存的解释：\n${reflection?['reason','boundary','next_check'].map(k=>reflection[k] || '未填写').join('\n'):'尚未保存'}`;
    }
  }
  function saveForm() {
    try {const key=formKey();if(key){localStorage.setItem(key,JSON.stringify({revision:state.session.revision,olderDraft:state.olderDraft,form:capture()}));state.localSaved=true;}}
    catch(_){state.localSaved=false;}
    renderSaveStatus();
  }
  function notice(message='',recover=false) {
    $('notice').replaceChildren(); $('notice').hidden=!message;
    if(!message) return;
    $('notice').append(document.createTextNode(message));
    if(recover && state.session) {
      const button=document.createElement('button');button.type='button';button.className='button button-outline';button.textContent='读取最新记录，保留本页输入';
      button.onclick=()=>perform('正在读取最新记录…',async()=>{const draft=capture();setSession((await request('/sessions/'+state.session.id)).session);restore(draft);state.conflict=false;notice('已读取最新版本，请核对代码和用例后继续。');});
      $('notice').append(document.createElement('br'),button);
    }
  }
  function toast(message) { $('toast').textContent=message;$('toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>{$('toast').hidden=true;},4000); }
  function controls() {
    const present=!!state.session && !state.session.legacy, locked=state.busy || state.conflict;
    document.querySelectorAll('button').forEach(node=>{node.disabled=state.busy;});
    ['problem-query','problem-category','problem-select','language-select'].forEach(id=>{$(id).disabled=state.busy;});
    $('new-session').disabled=state.busy || !problemId();
    $('new-session').textContent=state.user ? `新建${state.mode==='review'?'代码质检':'题目共创'} →` : '登录并开始 →';
    ['save-example','save-review','run-review','verify-review','return-review'].forEach(id=>{$(id).disabled=locked || !present;});
    ['generate-ai','review-generate'].forEach(id=>{$(id).disabled=locked || !present;});
    $('run-compare').disabled=locked || !present || !currentGeneration()?.candidates?.length;
    $('export-session').disabled=state.busy || !state.session;
    ['save-learning-reflection','refresh-learning','refresh-recap'].forEach(id=>{$(id).disabled=locked || !present;});
    $('save-learning-reflection').disabled=locked || !present || !reflectionTarget();
    ['download-recap-json','download-recap-md'].forEach(id=>{$(id).disabled=state.busy || !state.learning?.recap;});
    $('reflection-target').disabled=state.busy || !present;
    $('refresh-sessions').disabled=state.busy || !state.user;
    $('problem-prev').disabled=state.busy || state.page<=1;$('problem-next').disabled=state.busy || state.page>=state.pages;
    document.querySelectorAll('[data-candidate],[data-edit],[data-delete],[data-use-output],[data-sample],[data-transfer],[data-record-attempt]').forEach(node=>{node.disabled=locked || !present;});
    fields.forEach(id=>{$(id).readOnly=state.busy || !present;});
    document.querySelectorAll('[name=judgment],.reference-option input').forEach(node=>{node.disabled=state.busy || !present;});
    $('recap-next').disabled=state.busy || !state.session;
    renderSaveStatus();
  }
  async function perform(label,operation) {
    if(state.busy) return;
    saveForm();state.busy=true;notice();$('busy-status').hidden=false;$('busy-message').textContent=label;$('main-content').setAttribute('aria-busy','true');controls();
    try { await operation(); }
    catch(error){if(state.session && (error.code==='STALE_REVISION' || error.code==='NETWORK_STATE_UNKNOWN'))state.conflict=true;notice(error.message,state.conflict);if(error.status===401){state.user=null;account();}}
    finally {state.busy=false;$('busy-status').hidden=true;$('main-content').removeAttribute('aria-busy');controls();}
  }
  async function mutate(suffix,body={},method='POST') {
    if(!state.session || state.conflict) throw new Error('请先打开有效记录并核对最新状态。');
    return request('/sessions/'+state.session.id+suffix,{method,body:{revision:state.session.revision,...body}});
  }
  function modeUI() {
    ['examples','review'].forEach(mode=>{const active=state.mode===mode;$('tab-'+mode).setAttribute('aria-selected',String(active));$('tab-'+mode).tabIndex=active?0:-1;$(mode+'-panel').hidden=!active || !!state.session?.legacy;});
    const url=new URL(location.href);url.searchParams.set('mode',state.mode);
    if(state.session)url.searchParams.set('session',state.session.id);else url.searchParams.delete('session');
    if(problemId())url.searchParams.set('problem',problemId());url.searchParams.set('language',language());history.replaceState(null,'',url);account();
    stageUI();
  }
  function describe(problem) {
    $('topic-summary-title').textContent=problem ? `${problem.id} · ${problem.title}` : '选择一道题，开始共创';
    $('topic-summary-lang').textContent=names[language()] || language();
    $('problem-heading').textContent=problem ? `${problem.id} · ${problem.title} · ${names[language()]} · 查看题意` : '查看本次题意与输入输出要求';
    const parsed=new DOMParser().parseFromString((problem?.description || '').replace(/<\/(p|div|h[1-6]|pre|li)>/gi,'</$1>\n'),'text/html');
    $('problem-description').textContent=parsed.body.textContent;
    $('back-practice').href=problem ? practiceURL(problem.id,language()) : '/problem_selector.html';
  }
  async function loadProblems(page=1) {
    const ticket=++state.queryTicket;
    const data=await request('/api/problems?'+new URLSearchParams({q:$('problem-query').value,category:$('problem-category').value,page,page_size:20}));
    if(ticket!==state.queryTicket)return;
    state.problems=data.problems || [];state.page=data.page || 1;state.pages=data.pages || 1;
    const previous=problemId() || params.get('problem');
    $('problem-select').innerHTML=state.problems.map(p=>`<option value="${esc(p.id)}">${esc(p.id+' · '+p.title)}</option>`).join('') || '<option value="">没有匹配的题目</option>';
    if(previous && state.problems.some(p=>p.id===previous))$('problem-select').value=previous;
    else if(previous && (state.session?.problem_id===previous || params.get('problem')===previous)) {
      try {const p=(await request('/api/problems/'+encodeURIComponent(previous))).problem;const opt=new Option(p.id+' · '+p.title,p.id);$('problem-select').prepend(opt);$('problem-select').value=p.id;}catch(_){/* Deleted questions remain in historical records. */}
    }
    if($('problem-category').options.length===1)(data.categories || []).forEach(c=>$('problem-category').add(new Option(c.name,c.id)));
    $('problem-page-label').textContent=`${data.total || 0} 道题 · 第 ${state.page} / ${state.pages} 页`;
    await loadTopic();controls();
  }
  async function loadTopic() {
    const id=problemId(),ticket=++state.topicTicket;if(!id){describe(null);return;}
    const data=await request('/api/problems/'+encodeURIComponent(id));
    if(ticket===state.topicTicket && id===problemId())describe(data.problem);
  }
  function setSession(session,preserve=false,restoreLocal=true) {
    const previousId=state.session?.id;
    const previousRevision=state.session?.revision ?? -1;
    let draft=preserve?capture():null;
    let older=false;
    if(!preserve){if(restoreLocal)try{const saved=JSON.parse(localStorage.getItem(`codelab:co-create:forms:${state.user?.id}:${session.id}`)||'null');if(saved?.form && typeof saved.form==='object'){draft=saved.form;older=saved.revision!==session.revision || !!saved.olderDraft;}}catch(_){}fields.forEach(id=>{$(id).value='';});$('compare-reference').checked=false;$('review-reference').checked=false;}
    state.session=session;state.mode=session.mode;state.editing=null;state.conflict=false;
    state.olderDraft=preserve?state.olderDraft && session.revision<=previousRevision:older;
    if(previousId!==session.id){state.learning=null;state.renderedAttempts=[];state.attemptDrafts={};}
    if(!session.legacy){if(![...$('problem-select').options].some(o=>o.value===session.problem_id))$('problem-select').add(new Option(session.title,session.problem_id));$('problem-select').value=session.problem_id;$('language-select').value=session.language;describe(session.problem);}
    state.sessions=state.sessions.filter(s=>s.id!==session.id);state.sessions.unshift(session);
    modeUI();render();if(previousId!==session.id)fillReflection(session.state.learning?.reflection);if(draft)restore(draft);
    if(older && !accountChangesPending()){older=false;state.olderDraft=false;}
    renderReflectionBinding();saveForm();controls();
    $('topic-disclosure').open=false;
    if(older){state.conflict=true;notice('本机输入来自较早版本，已为你保留。请读取最新记录并核对，再保存修改。',true);controls();}
    if(!session.legacy)loadLearning();
  }
  function render() {
    const session=state.session, data=session?.state;
    $('legacy-panel').hidden=!session?.legacy;
    if(session?.legacy){$('legacy-content').textContent=JSON.stringify(data,null,2);$('session-label').textContent=session.title+' · 旧场景记录';renderSaved();return;}
    $('session-label').textContent=session ? `${session.problem_id} · ${session.title} · ${names[session.language]}` : '选择题目与语言，新建或恢复共创';
    $('revision-label').textContent=session ? `记录版本 ${session.revision} · ${time(session.updated_at)}` : '按账号、题目和语言保存';
    $('context-note').textContent=session ? `${data.practice_context?.submission_id ? '承接提交 #'+data.practice_context.submission_id : data.practice_context?.code ? '已承接创建时的编辑器草稿' : '从当前题目新建'}。回填代码前会先查看差异，采纳后仍需正式提交。` : '可以从刷题页带入草稿，也可以在这里选题开始。';
    if(session?.problem?.changed)notice('原题目已更新。旧证据保留，请针对新题意新建共创。');
    const examples=data?.examples || [];$('example-count').textContent=examples.length+' 个用例';
    $('example-list').innerHTML=examples.map((e,i)=>`<div class="example-row"><span class="example-index">${i+1}</span><pre><span class="example-meta">${esc(sources[e.source] || e.source)} · 输入</span>${esc(text(e.input))}</pre><span class="output-arrow" aria-hidden="true">→</span><pre><span class="example-meta">${e.expected===null?'没有标准答案':'输出'}</span>${esc(text(e.expected))}</pre><div class="example-actions"><button type="button" data-sample="${esc(e.id)}">使用此输入</button>${e.readonly?'':`<button type="button" data-edit="${esc(e.id)}">编辑</button><button type="button" data-delete="${esc(e.id)}">删除</button>`}</div></div>`).join('') || '<p class="empty-state">新建后带入题目公开样例，也可自己补充测试。</p>';
    const generation=currentGeneration(),selected=data?.selected;$('generation-source').textContent=generation ? (sources[generation.source] || generation.source) : '尚未生成';
    $('candidate-grid').innerHTML=(generation?.candidates || []).map((c,i)=>`<article class="candidate-card ${selected?.candidate_id===c.id?'selected':''}"><div class="candidate-top"><span class="candidate-letter">${String.fromCharCode(65+i)}</span><div><h3>${esc(c.label)}</h3><p class="candidate-meta">${esc(sources[c.source] || c.source)} · ${esc(names[c.language || session.language])}${c.model?' · '+esc(c.model):''}</p><span class="candidate-check">${c.verification?.official_total>0?'公开样例 '+c.verification.passed+' / '+c.verification.official_total+' 项通过':'尚无公开样例验证'}</span></div></div><pre aria-label="${esc(c.label)}的代码"><code>${esc(c.code)}</code></pre><div class="candidate-bottom"><details class="candidate-explanation"><summary>查看实现说明</summary><p>${esc(c.explanation || '未保存实现说明')}</p></details><details><summary>查看本轮用例依据</summary>${(c.verification?.cases || []).map(v=>`<div class="run-record"><small>${esc(sources[v.expected_source] || '运行记录')} · ${esc(v.status || '')}</small><pre>输入：${esc(text(v.input))}\n输出：${esc(text(v.output))}${v.expected!=null?'\n对照：'+esc(text(v.expected)):''}</pre></div>`).join('')}</details><div class="action-row"><button class="button button-primary" data-candidate="${esc(c.id)}" data-action="verify" type="button">检验题库用例</button><button class="button button-outline" data-candidate="${esc(c.id)}" data-action="select" type="button">${selected?.candidate_id===c.id?'已选择':'选择此实现'}</button><button class="button button-outline" data-candidate="${esc(c.id)}" data-action="handoff" type="button">查看差异并带回 ↗</button></div></div></article>`).join('') || '<p class="empty-state">候选会按当前题意与语言生成。你已有的代码也会作为对照保留。</p>';
    if(generation?.error)notice(generation.error);
    $('selection-result').hidden=!selected;$('selection-result').textContent=selected?'已选择：'+selected.label+'。选择本身不代表正式判题通过。':'';
    const review=data?.review;$('review-code').value=review?.code || '';$('review-source').textContent=sources[review?.source] || '等待带入代码';$('review-language').textContent=names[session?.language || language()];
    $('review-code-status').textContent=review ? `代码版本 ${review.code_revision} · ${names[session.language]}` : '新建后载入草稿或起始模板';
    $('review-input').value=review?.prediction_saved?(review.prediction_input ?? ''):(data?.practice_context?.input_text || examples[0]?.input || '');
    $('compare-input').value=[...(data?.runs || [])].reverse().find(r=>r.kind==='compare')?.input ?? (data?.practice_context?.input_text || examples[0]?.input || '');
    $('review-prediction').value=review?.prediction_saved?text(review.prediction):'';$('review-reflection').value=review?.reflection || '';
    document.querySelectorAll('[name=judgment]').forEach(node=>{node.checked=node.value===review?.judgment;});
    $('review-save-status').textContent=review?'已保存版本 '+review.code_revision+'；新增修改后请保存或运行。':'';
    ['compare','review'].forEach(prefix=>{$(prefix+'-reference-label').hidden=!session?.problem?.reference_available;});
    const runs=data?.runs || [];$('evidence-count').textContent=runs.length+' 次运行';
    const candidateCheck=[...runs].reverse().find(r=>r.kind==='verify' && r.candidate_id && generation?.candidates?.some(c=>c.id===r.candidate_id));
    $('candidate-verification').innerHTML=candidateCheck?runHTML(candidateCheck):'';
    renderRun([...runs].reverse().find(r=>r.kind==='compare'),'compare-results');
    $('review-results').innerHTML=(review?.evidence || []).slice(-6).reverse().map(runHTML).join('') || '<p class="empty-state">可以直接运行；想训练推理时，再先写下判断与预测。</p>';
    $('run-history').innerHTML=runs.slice(-12).reverse().map(runHTML).join('') || '<p class="empty-state">运行后，证据会保存在这里。</p>';
    renderSaved();renderLearning();
  }
  function runHTML(run) {
    if(run.kind==='verify')return `<article class="run-record"><h3>题库验证 · ${Number.isFinite(run.passed_count)?run.passed_count:'未记录'} / ${Number.isFinite(run.total)?run.total:'未记录'} 项通过</h3><p class="run-note">${esc(run.message || '')} 隐藏用例 ${Number.isFinite(run.hidden_passed)?run.hidden_passed:'未记录'} / ${Number.isFinite(run.hidden_total)?run.hidden_total:'未记录'} 项通过。</p>${(run.cases || []).map(c=>`<details><summary>用例 ${c.index} · ${esc(c.status)}${c.is_public?'':' · 隐藏'}</summary>${c.is_public?`<pre>输入：${esc(c.input)}\n预期：${esc(c.expected)}\n实际：${esc(c.actual)}${c.error?'\n'+esc(c.error):''}</pre>`:'仅显示验证状态，输入与答案不公开。'}</details>`).join('')}<small>${time(run.created_at)}${run.code_revision!=null?' · 代码版本 '+run.code_revision:''}</small></article>`;
    const results=run.results || [run];
    const verdicts={passed:'与题目依据相符',failed:'与题目依据不符',matches_user:'符合你的期望',differs_user:'与你的期望不同',unverified:'正确性待验证',execution_failed:'执行未成功'};
    const comparison = results.some(r=>!r.success || r.output_truncated) ? '部分执行未完成或输出被截断，暂不能判断差异' : run.different ? '本次输出存在差异' : '本次输出没有差异';
    return `<article class="run-record"><h3>${run.kind==='compare'?comparison:'代码质检运行'} · ${esc(sources[run.expected_source] || '实际运行')}</h3><pre>输入：${esc(text(run.input))}</pre><div class="result-grid">${results.map((r,i)=>`<div class="result-cell"><b>${results.length>1?String.fromCharCode(65+i)+' · ':''}${esc(verdicts[r.verdict] || r.status || '')}</b><span class="result-label">实际输出</span><pre>${esc(text(r.output ?? r.actual))}</pre>${r.error?'<p class="run-note">'+esc(r.error)+'</p>':''}${r.expected!=null?'<span class="result-label">对照输出 · '+esc(sources[run.expected_source] || '已有依据')+'</span><pre>'+esc(text(r.expected))+'</pre>':''}${run.kind==='compare'&&r.success?'<button class="text-button" type="button" data-use-output="'+i+'" data-run="'+esc(run.id)+'">作为自己的期望补充用例</button>':''}</div>`).join('')}</div>${run.prediction!=null?`<p class="run-note">你的预测：${esc(text(run.prediction))} · ${run.prediction_matched===true?'与实际一致':run.prediction_matched===false?'与实际不同':'尚未比较'}</p>`:''}<p class="run-note">${esc(run.note || '输出一致不等于证明正确。')}</p><small>${time(run.created_at)}${run.code_revision!=null?' · 代码版本 '+run.code_revision:''}</small></article>`;
  }
  function renderRun(run,id) {$(id).innerHTML=run?runHTML(run):'<p class="empty-state">生成候选后，使用同一个输入观察实际结果。</p>';}
  function renderSaved() {
    $('session-list').innerHTML=state.user ? state.sessions.slice(0,16).map(s=>`<button type="button" data-session="${esc(s.id)}"><b>${esc(s.title)}</b><small>${s.problem_id?esc(s.problem_id)+' · '+esc(names[s.language] || s.language):'旧场景记录'} · ${s.mode==='review'?'代码质检':'用例共创'} · ${time(s.updated_at)}</small></button>`).join('') || '<p class="empty-state">从当前题目开始你的第一次共创。</p>' : '<p class="empty-state">登录后可恢复自己的记录。</p>';
  }
  const stageNames={verify:'验证 AI 代码',explain:'解释修改',transfer:'独立再做一次',recap:'共创复盘卡'};
  function petMessage(message) {
    $('pet-message').textContent=message;
    $('mobile-pet-message').textContent=message;
    $('mobile-pet-preview').textContent=message;
  }
  function stageUI(focus=false) {
    ['verify','explain','transfer','recap'].forEach(stage=>{
      $('stage-'+stage).hidden=stage!==state.stage;
      if(stage!=='recap'){const button=$('stage-tab-'+stage);button.setAttribute('aria-selected',String(stage===state.stage));button.tabIndex=stage===state.stage || (state.stage==='recap' && stage==='verify')?0:-1;}
    });
    $('open-recap').setAttribute('aria-pressed',String(state.stage==='recap'));
    const url=new URL(location.href);url.searchParams.set('stage',state.stage);history.replaceState(null,'',url);account();
    $('pet-stage-label').textContent='本地引导 · '+stageNames[state.stage];
    const hasRuns=!!state.session?.state.runs?.length;
    const messages={verify:hasRuns?'已经留下实际运行记录。挑一个你仍不放心的边界，再看看证据够不够。':'先看题意，再试一个最小合法输入。运行成功与答案正确，记得分别判断。',
      explain:'用你自己的话说说：改了哪里，为什么这样改？没有想清楚也可以留空，返回验证。',
      transfer:'这次先试着自己做。需要帮助也没关系，把是否用过提示如实记下来。',
      recap:'把实际做过的步骤串起来看看。空白不是失败，它告诉我们下一步还能从哪里开始。'};
    petMessage(messages[state.stage]);
    if(focus){const panel=$('stage-'+state.stage);panel.setAttribute('tabindex','-1');panel.focus();}
  }
  function goStage(stage) {
    if(!Object.hasOwn(stageNames,stage))return;
    saveForm();state.stage=stage;stageUI(true);renderReflectionBinding();
    if(['transfer','recap'].includes(stage))loadLearning();
  }
  function fillReflection(reflection) {
    $('reflection-target').value=reflection?.candidate_id || (state.session?.mode==='review'?'review':state.session?.state.selected?.candidate_id || currentGeneration()?.candidates?.[0]?.id || 'review');
    $('reflection-reason').value=reflection?.reason || '';$('reflection-boundary').value=reflection?.boundary || '';$('reflection-next-check').value=reflection?.next_check || '';
  }
  function reflectionTarget() {
    const id=$('reflection-target').value;
    if(id==='review')return state.session?.mode==='review' && state.session?.state.review ? {id,code:$('review-code').value,source:state.session.state.review.source,model:state.session.state.review.model,label:'当前待检代码'} : null;
    const candidate=currentGeneration()?.candidates?.find(c=>c.id===id);
    return candidate?{...candidate,label:candidate.label || '候选实现'}:null;
  }
  function renderReflectionBinding() {
    const target=reflectionTarget(),saved=state.learning?.learning?.reflection || state.session?.state.learning?.reflection;
    const unsavedReview=target?.id==='review' && target.code!==state.session?.state.review?.code;
    $('reflection-code').textContent=target?.code || '尚无可绑定代码。先新建记录或生成候选。';
    $('reflection-binding').textContent=target?`${target.label} · ${sources[target.source] || target.source || '来源未记录'}${target.model?' · '+target.model:''}${unsavedReview?' · 存在未保存代码，保存解释时先保存这份代码。':' · 保存解释时绑定代码快照及已有运行。'}`:'选择记录后，解释可以绑定一份实际代码。';
    const runs=(state.session?.state.runs || []).filter(run=>target?.id==='review'?!unsavedReview && run.code_revision===state.session?.state.review?.code_revision:run.candidate_id===target?.id || run.results?.some(r=>r.candidate_id===target?.id));
    $('reflection-evidence').innerHTML=runs.length?`<p class="helper-text">这份实现已有 ${runs.length} 条相关运行；保存时记录具体依据，后续新运行不会自动改写旧解释。</p>`:'<p class="helper-text">尚无相关运行依据，可以返回验证，也可以先保存自己的想法。</p>';
    const stale=!!saved && (saved.stale || unsavedReview || saved.candidate_id!==target?.id);
    $('reflection-saved-status').className='reflection-status'+(stale?' stale':'');
    $('reflection-saved-status').textContent=saved ? stale?'已保存解释绑定的是另一份或较早代码。旧解释仍保留，不作为当前代码的解释；核对后可重新保存。':`已保存你的解释 · ${time(saved.saved_at)}${saved.is_current_target===false?' · 解释对象与当前复盘对象不同':''} · 仅表示你填写的理由，不代表已掌握。`:'尚未保存解释。三个输入都可以留空，也可以直接继续下一步。';
  }
  async function loadLearning() {
    const id=state.session?.id;if(!id || state.session.legacy || !state.user)return;
    const ticket=++state.learningTicket;
    try {
      const data=await request('/sessions/'+id+'/learning');
      if(ticket!==state.learningTicket || id!==state.session?.id)return;
      const draft=capture();state.learning=data;$('learning-status').textContent='复盘卡来自已保存记录；本页未保存输入只留在草稿中。';renderLearning();restore(draft);renderReflectionBinding();controls();
    } catch(_){
      if(ticket===state.learningTicket && id===state.session?.id)$('learning-status').textContent='学习记录暂未读取。验证功能与本页草稿仍可使用，可稍后刷新。';
    }
  }
  function learningResult(data) {
    const draft=capture();if(data.session)setSession(data.session,true);state.learning=data;renderLearning();restore(draft);renderReflectionBinding();saveForm();
  }
  function restoreAttemptForms() {
    state.renderedAttempts.forEach(id=>{const values=state.attemptDrafts[id];if(!values)return;const submission=$('attempt-submission-'+id),help=$('attempt-help-'+id);if(submission)submission.value=values.submission || '';if(help)help.value=values.help || 'unspecified';});
  }
  function renderLearning() {
    const data=state.learning,record=state.session;
    const previous=$('reflection-target').value;
    const candidates=currentGeneration()?.candidates || [];
    $('reflection-target').innerHTML=(record?.mode==='review'?'<option value="review">当前待检代码</option>':candidates.length?'':'<option value="">先生成候选，再选择解释对象</option>')+(record?.mode==='review'?[]:candidates).map(c=>`<option value="${esc(c.id)}">${esc(c.label || '候选实现')} · ${esc(sources[c.source] || c.source)}</option>`).join('');
    $('reflection-target').value=(record?.mode==='review' && previous==='review') || candidates.some(c=>c.id===previous)?previous:(record?.mode==='review'?'review':record?.state.selected?.candidate_id || candidates[0]?.id || '');
    renderReflectionBinding();
    const attempts=data?.attempts || [],related=data?.related || [];
    $('stage-verify-state').textContent=record?.state.runs?.length?record.state.runs.length+' 次运行':'可开始';
    $('stage-explain-state').textContent=(data?.learning?.reflection || record?.state.learning?.reflection)?'有保存记录':'可跳过';
    $('stage-transfer-state').textContent=attempts.length?attempts.length+' 次练习':'可稍后';
    $('transfer-related').innerHTML=related.length?related.map(p=>`<article class="related-card"><span class="quiet-badge">人工配置关联题</span><h3>${esc(p.problem_id)} · ${esc(p.title)}</h3><p>${esc(p.reason || '')}</p><p class="helper-text">练习关注：${esc(p.focus || '运用本题涉及的方法')} · ${esc(names[record?.language] || '')}</p><button type="button" class="button button-primary" data-transfer="${esc(p.problem_id)}">开始这道独立练习 →</button></article>`).join(''):'<p class="empty-state">'+(record?'这道题暂时没有可用的人工关联题；可以保留复盘，稍后从题库选择其他题。':'先打开一道题的共创记录，再查看关联练习。')+'</p>';
    $('transfer-attempts').innerHTML=attempts.length?attempts.map(a=>attemptHTML(a)).join(''):'<p class="empty-state">还没有开始独立练习。开始后会保存题目、语言和时间；正式提交后才有结果。</p>';
    state.renderedAttempts=attempts.map(a=>a.id);restoreAttemptForms();state.renderedAttempts.forEach(id=>{['attempt-submission-','attempt-help-'].forEach(prefix=>{$(prefix+id).addEventListener('input',saveForm);$(prefix+id).addEventListener('change',saveForm);});});
    renderRecap(data?.recap);
  }
  const helpNames={none:'未使用 AI 帮助（本人自述）',hint:'使用过提示（本人自述）',full:'看过完整答案（本人自述）',unspecified:'尚未自述帮助使用情况'};
  function helpEvidenceText(saved) {
    const records=saved.recorded_help || [],levels={1:'概念线索',2:'定位与解释',3:'局部修改',4:'完整参考'};
    return records.length?`本站帮助记录：${records.map(h=>`${sources[h.source] || h.source || '来源未记录'} / ${levels[h.level] || '层级未记录'} / ${h.shown_at?'已展示 '+time(h.shown_at):'未记录展示'}`).join('；')}。仅覆盖本站，与本人自述分别保留。`:'此卡暂无本站帮助记录；不能证明未借助站外帮助。';
  }
  function attemptHTML(attempt,editable=true) {
    const statuses={in_progress:'已开始，尚无正式结果',submitted:'已有正式提交记录',target_changed:'关联题已更新，请核对题意'};
    return `<article class="attempt-card"><h3>${esc(attempt.problem_id)} · ${esc(attempt.title)}</h3><p class="helper-text">${esc(names[attempt.language] || attempt.language)} · ${time(attempt.started_at)} · ${esc(statuses[attempt.status] || attempt.status)}</p>${(attempt.submissions || []).map(s=>`<p class="attempt-result">正式提交 #${esc(s.submission_id ?? s.id)} · ${esc(s.record_available===false?'原提交记录已不可用':s.submission?.status || s.status || '状态未记录')}<br><small>${esc(helpNames[s.help_usage] || helpNames.unspecified)}<br>${esc(helpEvidenceText(s))}</small></p>`).join('')}<a class="text-button" href="${esc(practiceURL(attempt.problem_id,attempt.language)+'&co_create_session='+encodeURIComponent(state.session.id)+'&transfer_attempt='+encodeURIComponent(attempt.id))}">继续这道练习 ↗</a>${editable?`<details><summary>补记一条正式提交与帮助情况</summary><p class="helper-text">仅可关联本账号在这次练习开始后、同题同语言的实际提交。帮助情况为自述，不推断独立能力。</p><label for="attempt-submission-${esc(attempt.id)}">正式提交编号<input id="attempt-submission-${esc(attempt.id)}" type="number" min="1" inputmode="numeric"></label><label for="attempt-help-${esc(attempt.id)}">这次使用了什么帮助？<select id="attempt-help-${esc(attempt.id)}"><option value="unspecified">暂不填写</option><option value="none">没有使用 AI 帮助</option><option value="hint">使用过提示</option><option value="full">看过完整答案</option></select></label><button type="button" class="button button-outline" data-record-attempt="${esc(attempt.id)}">保存实际提交与自述</button></details>`:''}</article>`;
  }
  function renderRecap(recap) {
    const reflection=recap?.reflection,attempts=recap?.transfer_attempts || [];
    const actualSubmissions=attempts.flatMap(a=>a.submissions || []).filter(s=>s.record_available!==false && s.submission);
    const explained=reflection && ['reason','boundary','next_check'].some(k=>reflection[k]?.trim());
    $('recap-overview').innerHTML=recap?[
      ['实际运行',`${recap.runs?.length || 0} 次`,'已保存的运行记录'],
      ['我的解释',!reflection?'尚未保存':reflection.stale?'需重新核对':explained?'已保存':'内容留空',reflection?.stale?'绑定的是较早代码':'理由由本人填写'],
      ['关联练习',`${actualSubmissions.length} 次提交`,`${attempts.length} 次练习尝试 · 以实际判题为准`],
    ].map(([label,value,note])=>`<div class="recap-fact"><span>${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(note)}</small></div>`).join(''):'';
    const next=!(recap?.runs?.length)?'verify':!reflection || reflection.stale || !explained?'explain':!actualSubmissions.length?'transfer':'verify';
    $('recap-next').dataset.stage=next;
    $('recap-next').textContent={verify:'继续检查代码 →',explain:'回到我的解释 →',transfer:'进入关联练习 →'}[next];
    $('recap-next-note').textContent=recap?({verify:'可以再检查一个不放心的输入。',explain:'留下自己的理由，或核对旧解释对应的代码。',transfer:'带着这次的理解，尝试另一道关联题。'})[next]:'打开一条共创记录，回看实际做过的步骤。';
    if(!recap){$('recap-content').innerHTML='<p class="empty-state">打开共创记录后可刷新复盘卡。这里不会把未运行的代码、空白解释或未提交的练习补成结果。</p>';return;}
    const r=recap.reflection,chosen=recap.chosen;
    $('recap-content').innerHTML=`<div class="recap-identity"><h3>${esc(recap.session.problem_id)} · ${esc(recap.session.title)}</h3><p>${esc(names[recap.session.language] || recap.session.language)} · 记录版本 ${esc(recap.session.revision)}${recap.session.problem_changed?' · 原题已更新，旧记录仅供回看':''}</p></div>
      <section class="recap-section"><h3><span>01</span> 代码来自哪里</h3><p>起点：${esc(sources[recap.baseline?.source] || recap.baseline?.source || '未记录')}；当前复盘对象：${chosen?esc(sources[chosen.source] || chosen.source)+(chosen.model?' · '+esc(chosen.model):''):'尚无可对照实现'}。</p><details><summary>查看已保存代码快照</summary><h4>起点代码</h4><pre>${esc(recap.baseline?.code || '未保存起点代码')}</pre><h4>当前复盘对象</h4><pre>${esc(chosen?.code || '尚无可对照实现')}</pre></details></section>
      <section class="recap-section"><h3><span>02</span> 实际验证了什么</h3><p>${recap.runs?.length || 0} 次已保存运行。公开样例、用户期望和参考程序依据分别标明；已有用例通过不代表所有输入正确。</p><details><summary>展开运行依据</summary>${(recap.runs || []).map(runHTML).join('') || '<p class="empty-state">尚无实际运行记录</p>'}</details></section>
      <section class="recap-section"><h3><span>03</span> 我的解释</h3>${r?`<p class="${r.stale?'stale':'helper-text'}">${r.stale?'绑定较早代码，保留回看，不作为当前代码解释。':'已绑定保存时的代码与运行依据。'}${r.is_current_target===false?' 解释对象与当前复盘对象不同，分别保留。':''} ${time(r.saved_at)} · 代码标识 ${esc((r.code_hash || '').slice(0,12))}</p><dl><dt>修改理由</dt><dd>${esc(r.reason || '未填写')}</dd><dt>边界检查</dt><dd>${esc(r.boundary || '未填写')}</dd><dt>下一次验证</dt><dd>${esc(r.next_check || '未填写')}</dd></dl>`:'<p class="empty-state">尚未保存学生解释</p>'}${(recap.reflection_history || []).length?'<details><summary>回看先前 '+recap.reflection_history.length+' 条本人解释</summary>'+recap.reflection_history.slice().reverse().map(old=>'<article class="run-record"><small>历史解释 · '+time(old.saved_at)+' · 代码标识 '+esc((old.code_hash || '').slice(0,12))+'</small><p>修改理由：'+esc(old.reason || '未填写')+'</p><p>边界检查：'+esc(old.boundary || '未填写')+'</p><p>下一次验证：'+esc(old.next_check || '未填写')+'</p></article>').join('')+'</details>':''}</section>
      <section class="recap-section"><h3><span>04</span> 采纳与正式复测</h3>${(recap.proposals || []).map(p=>`<article class="run-record"><b>代码提案 #${esc(p.id)} · ${esc(({accepted:'已采纳',rejected:'已拒绝',undone:'已撤销',pending:'待决定'})[p.state] || p.state)}</b><p class="helper-text">${(p.events || []).map(e=>esc(({accept:'采纳',reject:'拒绝',undo:'撤销',co_create:'从共创带回',retest:'正式复测'})[e.kind] || e.kind)+' · '+time(e.created_at)).join(' / ') || '暂无操作记录'}</p>${(p.formal_submissions || []).map(s=>`<p>正式提交 #${esc(s.id)} · ${esc(s.status)} · ${time(s.created_at)}</p>`).join('') || '<p class="helper-text">尚无关联正式复测</p>'}</article>`).join('') || '<p class="empty-state">尚未带回或采纳代码</p>'}</section>
      <section class="recap-section"><h3><span>05</span> 独立再做一次</h3>${(recap.transfer_attempts || []).map(a=>attemptHTML(a,false)).join('') || '<p class="empty-state">尚未开始关联练习</p>'}</section><div class="recap-scope">${(recap.scope_notes || []).map(n=>'<p>'+esc(n)+'</p>').join('')}</div>`;
  }
  function download(name,content,type) {
    const url=URL.createObjectURL(new Blob([content],{type}));const link=document.createElement('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  function recapMarkdown(recap) {
    const r=recap.reflection,lines=['# 共创复盘卡',`题目：${recap.session.problem_id} · ${recap.session.title}`,`语言：${names[recap.session.language] || recap.session.language}；记录版本：${recap.session.revision}`,'','## 代码来源',`起点：${sources[recap.baseline?.source] || recap.baseline?.source || '未记录'}`,`当前复盘对象：${recap.chosen?(sources[recap.chosen.source] || recap.chosen.source)+(recap.chosen.model?' / '+recap.chosen.model:''):'尚未选择'}`,'','## 实际运行'];
    (recap.runs || []).forEach(run=>lines.push(`- ${run.kind} · ${time(run.created_at)} · ${sources[run.expected_source] || '题库验证'}${run.total!=null?' · '+run.passed_count+'/'+run.total+' 项通过':''}`));if(!recap.runs?.length)lines.push('尚无实际运行记录。');
    lines.push('','## 我的解释',r?.stale?'绑定较早代码，仅供回看。':'',`修改理由：${r?.reason || '未填写'}`,`边界检查：${r?.boundary || '未填写'}`,`下一次验证：${r?.next_check || '未填写'}`,'','## 采纳与正式复测');
    (recap.proposals || []).forEach(p=>{lines.push(`- 提案 #${p.id}：${p.state}`);(p.events || []).forEach(e=>lines.push(`  - ${e.kind} · ${time(e.created_at)}`));(p.formal_submissions || []).forEach(s=>lines.push(`  - 正式提交 #${s.id}：${s.status}`));});if(!recap.proposals?.length)lines.push('尚无采纳与正式复测记录。');
    lines.push('','## 独立再做一次');(recap.transfer_attempts || []).forEach(a=>{lines.push(`- ${a.problem_id} · ${a.title} · ${names[a.language] || a.language} · ${a.status}`);(a.submissions || []).forEach(s=>lines.push(`  - 正式提交 #${s.submission_id ?? s.id}：${s.record_available===false?'原提交记录已不可用':s.submission?.status || s.status || '状态未记录'}；${helpNames[s.help_usage] || helpNames.unspecified}；${helpEvidenceText(s)}`));});if(!recap.transfer_attempts?.length)lines.push('尚未开始关联练习。');
    lines.push('','## 范围说明',...(recap.scope_notes || []).map(n=>'- '+n),'','完整已保存证据可另行下载 JSON。未保存输入不包含在此卡中。');return lines.filter(line=>line!==undefined).join('\n\n');
  }
  async function loadSessions() {state.sessions=(await request('/sessions')).sessions || [];renderSaved();}
  async function saveReview() {
    const body={code:$('review-code').value,reflection:$('review-reflection').value};
    const judgment=document.querySelector('[name=judgment]:checked')?.value;if(judgment)body.judgment=judgment;
    if($('review-prediction').value!==''){body.prediction=$('review-prediction').value;body.prediction_input=$('review-input').value;}else body.clear_prediction=true;
    setSession((await mutate('/review',body)).session,true);
  }
  async function handoff(id) {
    const data=await mutate('/handoff',{candidate_id:id});
    location.href=practiceURL(data.problem_id,data.language,data.proposal.id);
  }
  function bind() {
    $('recap-next').onclick=()=>goStage($('recap-next').dataset.stage || 'verify');
    const stageButtons=['verify','explain','transfer'].map(stage=>$('stage-tab-'+stage));
    stageButtons.forEach((button,index)=>{button.onclick=()=>goStage(button.dataset.stage);button.onkeydown=e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();const i=e.key==='Home'?0:e.key==='End'?2:(index+(e.key==='ArrowRight'?1:2))%3;stageButtons[i].click();stageButtons[i].focus();}};});
    ['verify-next','explain-next','explain-back','transfer-back','transfer-recap','recap-back'].forEach(id=>{$(id).onclick=()=>goStage($(id).dataset.goStage);});
    $('open-recap').onclick=()=>goStage('recap');
    ['refresh-learning','refresh-recap'].forEach(id=>{$(id).onclick=()=>perform('正在读取已保存学习记录…',loadLearning);});
    $('reflection-target').onchange=()=>{saveForm();renderReflectionBinding();};
    $('reflection-form').onsubmit=e=>{e.preventDefault();perform('正在保存你自己的解释与代码依据…',async()=>{const candidateId=$('reflection-target').value;if(candidateId==='review')await saveReview();const data=await mutate('/learning/reflection',{candidate_id:candidateId,reason:$('reflection-reason').value,boundary:$('reflection-boundary').value,next_check:$('reflection-next-check').value});learningResult(data);toast('已保存你的解释。可以继续检查，也可以独立再做一次。');});};
    $('download-recap-json').onclick=()=>{if(state.learning?.recap)download('codelab-learning-'+state.session.id+'.json',JSON.stringify({format:'codelab-learning-recap',version:1,recap:state.learning.recap},null,2),'application/json');};
    $('download-recap-md').onclick=()=>{if(state.learning?.recap)download('codelab-learning-'+state.session.id+'.md',recapMarkdown(state.learning.recap),'text/markdown;charset=utf-8');};
    $('problem-search').onsubmit=e=>{e.preventDefault();perform('正在查找题目…',()=>loadProblems());};
    $('problem-prev').onclick=()=>perform('正在读取题库…',()=>loadProblems(state.page-1));$('problem-next').onclick=()=>perform('正在读取题库…',()=>loadProblems(state.page+1));
    ['problem-select','language-select'].forEach(id=>{$(id).onchange=()=>perform('正在切换题目与语言…',async()=>{saveForm();state.session=null;state.learning=null;state.localSaved=null;state.olderDraft=false;state.conflict=false;modeUI();render();await loadTopic();});});
    document.querySelectorAll('[data-mode]').forEach(button=>{button.onclick=()=>perform('正在切换共创方式…',async()=>{saveForm();state.mode=button.dataset.mode;const record=state.sessions.find(s=>s.mode===state.mode&&s.problem_id===problemId()&&s.language===language());state.session=null;state.learning=null;state.localSaved=null;state.olderDraft=false;if(record)setSession((await request('/sessions/'+record.id)).session);else{modeUI();render();}});button.onkeydown=e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();const target=$('tab-'+(button.dataset.mode==='examples'?'review':'examples'));target.click();target.focus();}};});
    $('new-session').onclick=()=>perform('正在创建题目共创…',async()=>{if(!state.user){location.href=$('account-link').href;return;}let draft=null;try{draft=JSON.parse(localStorage.getItem(`codelab:draft:v2:${state.user.id}:${problemId()}:${language()}`)||'null');}catch(_){}const spec=state.languages.find(l=>l.id===language());setSession((await request('/sessions',{method:'POST',body:{mode:state.mode,problem_id:problemId(),language:language(),code:typeof draft?.code==='string'?draft.code:state.mode==='review'?(spec?.starter_code || ''):'',input_text:draft?.input || ''}})).session);});
    $('example-form').onsubmit=e=>{e.preventDefault();perform('正在保存测试用例…',async()=>{const body={action:'upsert_example',example:{input:$('example-input').value,expected:$('example-expected').value || null,...(state.editing?{id:state.editing}:{})}};setSession((await mutate('',body,'PATCH')).session,true);state.editing=null;$('example-input').value='';$('example-expected').value='';$('cancel-edit').hidden=true;$('example-form-title').textContent='补充测试用例';saveForm();});};
    $('cancel-edit').onclick=()=>{state.editing=null;$('example-input').value='';$('example-expected').value='';$('cancel-edit').hidden=true;$('example-form-title').textContent='补充测试用例';saveForm();};
    $('generate-ai').onclick=()=>perform('AI 正在生成候选，随后按现有用例实际检查…',async()=>{setSession((await mutate('/generate',{source:'ai'})).session,true);});
    $('compare-form').onsubmit=e=>{e.preventDefault();perform('正在隔离环境中对比候选…',async()=>{setSession((await mutate('/compare',inputBody('compare'))).session,true);});};
    $('review-generate').onclick=()=>perform('AI 正在按本题生成待检实现…',async()=>{const draft=capture();await saveReview();const data=await mutate('/review-generate',{source:'ai'});setSession(data.session,false,false);if(data.session.state.generations.at(-1)?.status!=='ready')restore(draft);else ['reflection-reason','reflection-boundary','reflection-next-check'].forEach(id=>{$(id).value=draft[id];});saveForm();});
    $('save-review').onclick=()=>perform('正在保存代码与判断…',saveReview);
    $('run-review').onclick=()=>perform('正在保存并运行当前输入…',async()=>{const input=inputBody('review');await saveReview();setSession((await mutate('/review-run',input)).session,true);});
    $('verify-review').onclick=()=>perform('正在检验当前代码的题库用例…',async()=>{await saveReview();setSession((await mutate('/verify')).session,true);});
    $('return-review').onclick=()=>perform('正在准备代码差异…',async()=>{await saveReview();await handoff('review');});
    $('refresh-sessions').onclick=()=>perform('正在读取共创记录…',loadSessions);
    $('export-session').onclick=()=>{const payload={format:'codelab-problem-co-create',version:2,exported_at:new Date().toISOString(),note:'仅包含已保存记录。隐藏用例输入和答案未包含，已有用例通过不等于证明所有输入下正确。',session:state.session};const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download='codelab-co-create-'+state.session.id+'.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
    document.addEventListener('click',e=>{
      const node=e.target.closest('[data-session],[data-edit],[data-delete],[data-candidate],[data-use-output],[data-sample],[data-transfer],[data-record-attempt]');if(!node || state.busy)return;
      if(node.dataset.session)perform('正在恢复记录…',async()=>{setSession((await request('/sessions/'+node.dataset.session)).session);});
      else if(node.dataset.sample){const example=state.session.state.examples.find(v=>v.id===node.dataset.sample);if(example){$('compare-input').value=example.input;$('compare-expected').value='';$('compare-input').focus();saveForm();toast('已带入这组输入，运行时会自动识别题目公开答案。');}}
      else if(node.dataset.edit){const example=state.session.state.examples.find(v=>v.id===node.dataset.edit);$('example-compose').open=true;state.editing=example.id;$('example-input').value=example.input;$('example-expected').value=example.expected ?? '';$('cancel-edit').hidden=false;$('example-form-title').textContent='编辑自己的用例';$('example-input').focus();}
      else if(node.dataset.delete)perform('正在删除自己的用例…',async()=>{setSession((await mutate('',{action:'delete_example',example_id:node.dataset.delete},'PATCH')).session,true);});
      else if(node.dataset.candidate)perform(node.dataset.action==='verify'?'正在检验题库用例…':'正在准备候选操作…',async()=>{if(node.dataset.action==='handoff')await handoff(node.dataset.candidate);else setSession((await mutate(node.dataset.action==='verify'?'/verify':'/select',{candidate_id:node.dataset.candidate,generation_id:currentGeneration().id})).session,true);});
      else if(node.dataset.useOutput){const run=state.session.state.runs.find(r=>r.id===node.dataset.run),outcome=run?.results?.[Number(node.dataset.useOutput)];if(outcome){$('example-compose').open=true;state.editing=null;$('example-input').value=run.input;$('example-expected').value=outcome.output;$('example-input').focus();saveForm();toast('已放入用例表单，请核对题意后保存；该输出仍标记为你的期望。');}}
      else if(node.dataset.transfer)perform('正在保存独立练习起点…',async()=>{const data=await mutate('/learning/transfer',{problem_id:node.dataset.transfer});learningResult(data);const target=new URL(data.practice_url,location.origin);if(target.origin!==location.origin || target.pathname!=='/practice.html')throw new Error('练习地址不正确，请刷新后重试。');location.href=target.pathname+target.search;});
      else if(node.dataset.recordAttempt)perform('正在关联实际提交与帮助自述…',async()=>{const id=node.dataset.recordAttempt,submissionId=Number($('attempt-submission-'+id).value);if(!Number.isSafeInteger(submissionId) || submissionId<=0)throw new Error('请填写这次练习的正式提交编号。');learningResult(await mutate('/learning/transfer/'+encodeURIComponent(id)+'/submission',{submission_id:submissionId,help_usage:$('attempt-help-'+id).value}));});
    });
    fields.forEach(id=>{$(id).addEventListener('input',()=>{saveForm();if(id==='review-code'){$('review-save-status').textContent='代码已有未保存修改；运行或带回前会保存新版本。';renderReflectionBinding();}});});
    document.querySelectorAll('[name=judgment],.reference-option input').forEach(node=>node.addEventListener('change',saveForm));
    const encouragement=['不用急着相信任何一个答案。你补充的每个测试，都能让判断更扎实。','卡住时，先用一组最小输入手算。本鱼等你想明白再继续。','你来作判断，代码来给证据。慢一点，也是在前进。'];let petIndex=0;
    const encourage=()=>petMessage(encouragement[petIndex++%encouragement.length]);
    const hint=()=>{if(state.stage==='verify')petMessage(state.mode==='review'?'先试最小合法输入，再检查临界值。注意：运行成功和答案正确是两件事。':'先读数据范围，试试题目允许的最小值、重复数据和顺序变化。');else stageUI();};
    $('pet-encourage').onclick=encourage;$('mobile-pet-encourage').onclick=encourage;
    $('pet-hint').onclick=hint;$('mobile-pet-hint').onclick=hint;
  }
  async function init() {
    bind();if(names[params.get('language')])$('language-select').value=params.get('language');modeUI();render();controls();
    const results=await Promise.allSettled([request('/catalog'),request('/api/current_user')]);
    if(results[0].status==='fulfilled'){state.ai=!!results[0].value.ai_available;state.languages=results[0].value.languages || [];$('ai-status').textContent=state.ai?'AI 已配置 · 按需实时调用':'AI 未配置 · 可检验自己的代码';if(state.languages.length)$('language-select').innerHTML=state.languages.map(l=>`<option value="${esc(l.id)}">${esc(l.version || l.label)}</option>`).join('');if(names[params.get('language')])$('language-select').value=params.get('language');}
    else notice(results[0].reason.message);
    if(results[1].status==='fulfilled')state.user=results[1].value.user;account();
    try {await loadProblems();if(state.user){await loadSessions();const id=params.get('session');if(id){setSession((await request('/sessions/'+encodeURIComponent(id))).session);try{const saved=JSON.parse(localStorage.getItem(formKey())||'null');if(saved?.revision===state.session.revision)restore(saved.form);}catch(_){}}}else if(params.get('session'))notice('登录原账号后可恢复这条共创记录。');}
    catch(error){notice(error.message);}finally{controls();}
  }
  init();
})();
