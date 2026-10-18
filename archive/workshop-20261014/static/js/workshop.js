(() => {
  'use strict';
  if(location.hash==='#leaderboard'){location.replace('/learning-records.html#leaderboard');return;}
  const $=id=>document.getElementById(id);
  let catalog=[],scene=null,user=null,csrf='',renderer=null,lastRun=null,lastKey='',baseline='',project=null;
  let revision=0,busy=false,candidate=null,candidateRevision=0,sourceSuggestion=null,undo=null,sessionEpoch=0;
  const symbols={ocean:'≋',sorting:'▥',route:'⌁'};
  const valueSnapshot=()=>({scene:scene.id,code:$('creationCode').value,params:parameters()});
  const key=()=>JSON.stringify(valueSnapshot());
  const undoKey=()=>JSON.stringify({...valueSnapshot(),title:$('creationTitle').value});
  const creationState=()=>JSON.stringify({...valueSnapshot(),title:$('creationTitle').value,palette:$('palette').value});
  function carryGuestDraft(){
    if(user||!scene)return;
    try{sessionStorage.setItem('codelab.workshop.login-draft',JSON.stringify({...valueSnapshot(),title:$('creationTitle').value,palette:$('palette').value,savedAt:Date.now()}));}catch{message('浏览器暂时无法保存登录前草稿，请先复制代码。','error');}
  }
  function resumeGuestDraft(){
    if(!user)return;
    try{
      const raw=sessionStorage.getItem('codelab.workshop.login-draft');if(!raw)return;
      sessionStorage.removeItem('codelab.workshop.login-draft');const draft=JSON.parse(raw);
      const spec=catalog.find(s=>s.id===draft.scene);
      if(!spec||Date.now()-draft.savedAt>1800000||typeof draft.code!=='string'||draft.code.length>12000||typeof draft.title!=='string'||draft.title.length>80||!draft.params)return;
      chooseScene(draft.scene,{force:true});$('creationCode').value=draft.code;$('creationTitle').value=draft.title;$('stageTitle').textContent=draft.title;
      for(const c of scene.controls){const value=draft.params[c.key];if(c.type==='select'){if(!Object.hasOwn(c.options,value))return;}else if(typeof value!=='number'||!Number.isFinite(value)||value<c.min||value>c.max)return;}
      setParameters(draft.params);if(['lagoon','sunrise','mint'].includes(draft.palette)){$('palette').value=draft.palette;renderer?.palette(draft.palette);}
      changed();message('已恢复你登录前的创作草稿。点击运行，查看自己的实际结果。','success');
    }catch{message('登录前草稿未能恢复，请重新选择主题。','error');}
  }
  function parameters(){const result={};for(const c of scene.controls){const v=$('param-'+c.key).value;result[c.key]=c.type==='select'?v:Number(v);}return result;}
  function message(text,kind='info'){$('workshopStatus').textContent=text;$('workshopStatus').parentElement.dataset.kind=kind;}
  function controlsState(){
    const fresh=lastRun&&lastKey===key();
    $('runCreation').disabled=busy;$('suggestCreation').disabled=busy;$('saveCreation').disabled=busy||!fresh;
    $('exportWork').disabled=busy||!fresh;$('exportImage').disabled=!renderer;
    $('runCreation').textContent=busy?'正在处理…':'▶ 运行我的规则';
    for(const button of $('sceneList').querySelectorAll('button'))button.disabled=busy;
    for(const id of ['newCreation','resetCode','versionSelect','palette','creationTitle'])$(id).disabled=busy;
    if(lastRun){$('traceSource').textContent=fresh?'你的运行 · Docker':'规则已改变 · 旧回放';$('traceSource').dataset.state=fresh?'live':'stale';}
    if(candidate){const stale=candidateRevision!==revision;$('candidateStale').hidden=!stale;$('applyCandidate').disabled=stale||busy;}
    if(undo)$('undoCandidate').disabled=undo.after!==undoKey();
  }
  function changed(){revision++;controlsState();if(lastRun&&lastKey!==key())message('规则已改变，画面仍是上一次运行。点击运行，看看新的变化。');}
  function setParameters(params){for(const c of scene.controls){const node=$('param-'+c.key);node.value=params[c.key];const out=$('value-'+c.key);if(out)out.textContent=String(params[c.key]);}}
  function buildControls(){
    $('parameterControls').replaceChildren();
    for(const c of scene.controls){
      const wrap=document.createElement('div');wrap.className='control';
      const head=document.createElement('div');head.className='control-head';const label=document.createElement('label');label.htmlFor='param-'+c.key;label.textContent=c.label;head.append(label);
      let input;
      if(c.type==='select'){input=document.createElement('select');for(const [value,name] of Object.entries(c.options)){const option=new Option(name,value);input.add(option);}}
      else {input=document.createElement('input');input.type=c.key==='seed'?'number':'range';input.min=c.min;input.max=c.max;input.step=c.step;if(c.key!=='seed'){const out=document.createElement('output');out.id='value-'+c.key;out.htmlFor='param-'+c.key;out.textContent=c.default;head.append(out);}}
      input.id='param-'+c.key;input.value=c.default;input.addEventListener('input',()=>{const out=$('value-'+c.key);if(out)out.textContent=input.value;changed();});wrap.append(head,input);$('parameterControls').append(wrap);
    }
  }
  function showTrace(trace,{example=false}={}){
    renderer?.destroy();renderer=null;
    if(!window.p5||!window.CodeLabCanvas){message('画面引擎未加载，请刷新页面重试。','error');return;}
    renderer=CodeLabCanvas.mount($('canvasHost'),trace,{palette:$('palette').value,autoPlay:!matchMedia('(prefers-reduced-motion: reduce)').matches,onFrame:(index,total,playing)=>{
      $('timeline').max=total-1;$('timeline').value=index;$('timeline').disabled=false;$('framePosition').textContent=`${index+1} / ${total}`;$('playPause').disabled=false;$('playPause').textContent=playing?'暂停':'播放';$('playPause').setAttribute('aria-label',playing?'暂停回放':'播放回放');
    }});
    renderer.setSpeed($('playbackSpeed').value);
    if(example){$('traceSource').textContent='内置代码 · 示例回放';$('traceSource').dataset.state='example';}
    const desc=trace.scene==='ocean'?`${trace.frames[0].length} 条鱼 · ${trace.frames.length} 帧程序轨迹`:trace.scene==='sorting'?`${trace.frames[0].values.length} 个数字 · ${trace.frames.length} 个记录步骤`:`探索 ${trace.visited.length} 个位置 · ${trace.path.length?`航线 ${trace.path.length-1} 步`:'程序未返回可行航线'}`;
    $('traceDescription').textContent=desc;controlsState();
  }
  function chooseScene(id,{force=false,updateURL=true}={}){
    if(!force&&scene&&creationState()!==baseline&&!confirm('切换主题会清空当前未保存的规则，继续吗？'))return false;
    const next=catalog.find(s=>s.id===id)||catalog[0];if(!next)return false;
    scene=next;revision++;candidate=null;sourceSuggestion=null;undo=null;lastRun=null;lastKey='';project=null;
    $('candidatePanel').hidden=true;$('undoCandidate').hidden=true;$('versionBar').hidden=true;
    $('creationTitle').value=scene.title;$('stageTitle').textContent=scene.title;$('creationCode').value=scene.code;$('creativePrompt').value=scene.prompt;
    $('studioHeading').textContent=scene.name+' · 创作台';$('sceneEyebrow').textContent=scene.eyebrow;$('traceContract').textContent=scene.contract;
    buildControls();setParameters(scene.params);$('sourceNote').textContent=scene.description;baseline=creationState();
    for(const card of $('sceneList').children)card.setAttribute('aria-pressed',String(card.dataset.scene===scene.id));
    $('studio').hidden=false;
    if(updateURL){const url=new URL(location.href);url.search='';url.searchParams.set('scene',scene.id);history.replaceState(null,'',url);}
    renderer?.destroy();renderer=null;$('canvasHost').replaceChildren();$('playPause').disabled=true;$('timeline').disabled=true;
    $('framePosition').textContent='0 / 0';$('traceSource').textContent='等待运行';$('traceDescription').textContent='运行代码，生成自己的回放。';
    if(scene.preview)showTrace(scene.preview.trace,{example:true});
    controlsState();message(user?'先改一个参数，再运行你的规则。':'可以浏览示例；登录后即可运行、请求 AI 和保存作品。');return true;
  }
  async function api(path,{method='GET',body}={}){
    const headers={};if(body!==undefined)headers['Content-Type']='application/json';if(method!=='GET')headers['X-CSRF-Token']=csrf;
    const response=await fetch('/api/workshop/'+path,{method,headers,body:body===undefined?undefined:JSON.stringify(body),credentials:'same-origin',cache:'no-store'});
    let packet;try{packet=await response.json();}catch{throw Error(response.status===413?'请求太大，请缩短代码或描述。':'服务暂时无法返回数据，请重试。');}
    if(!response.ok||!packet.success){if(response.status===401){$('loginToCreate').hidden=false;throw Error('请先登录，你当前的规则仍保留在创作台。');}throw Error(packet.error?.message||'操作未完成，请重试。');}
    return packet.data;
  }
  async function action(task){if(busy)return;busy=true;controlsState();try{await task();}catch(error){message(error.message||'网络连接失败，请稍后重试。','error');}finally{busy=false;controlsState();}}
  function needLogin(){if(user)return true;$('loginToCreate').hidden=false;message('请先登录，再运行或保存你的创作。当前代码仍然保留。');return false;}
  async function loadCatalog(){
    $('catalogError').hidden=true;$('retryCatalog').hidden=true;
    try{
      catalog=(await api('catalog')).scenes;$('sceneList').replaceChildren();
      for(const s of catalog){const button=document.createElement('button');button.type='button';button.className='scene-card';button.dataset.scene=s.id;button.setAttribute('aria-pressed','false');const num=document.createElement('span');num.className='scene-number';num.textContent=s.eyebrow;const title=document.createElement('h3');title.textContent=s.name;const concept=document.createElement('p');concept.className='scene-concept';concept.textContent=s.concept;const symbol=document.createElement('span');symbol.className='scene-symbol';symbol.textContent=symbols[s.id];symbol.setAttribute('aria-hidden','true');button.append(num,title,concept,symbol);button.addEventListener('click',()=>chooseScene(s.id));$('sceneList').append(button);}
      const url=new URL(location.href),requestedProject=Number(url.searchParams.get('project'));
      chooseScene(url.searchParams.get('scene')||'ocean',{force:true,updateURL:!requestedProject});
      if(requestedProject&&user)await openProject(requestedProject,{force:true});
      else resumeGuestDraft();
    }catch(error){$('catalogError').textContent=error.message;$('catalogError').hidden=false;$('retryCatalog').hidden=false;}
  }
  async function loadProjects(){
    $('retryProjects').hidden=true;if(!user){$('projectList').replaceChildren();$('collectionStatus').textContent='登录后，收藏你亲手创造的小小世界。';return;}
    try{const data=await api('projects');$('projectList').replaceChildren();$('collectionStatus').textContent=data.projects.length?'选择作品继续创作，或回看先前的版本。':'你的造物集还是空的。运行一次规则，再保存第一件作品。';
      for(const p of data.projects){const button=document.createElement('button');button.type='button';button.className='project-card';const icon=document.createElement('span');icon.className='project-icon';icon.textContent=symbols[p.scene];const text=document.createElement('div');const title=document.createElement('strong');title.textContent=p.title;const meta=document.createElement('small');meta.textContent=`${catalog.find(s=>s.id===p.scene)?.name||p.scene} · ${p.revision} 个版本`;text.append(title,meta);button.append(icon,text);button.addEventListener('click',()=>action(()=>openProject(p.id)));$('projectList').append(button);}
    }catch(error){$('collectionStatus').textContent=error.message;$('retryProjects').hidden=false;}
  }
  function restoreRun(run,palette){
    $('creationCode').value=run.code;$('creationTitle').value=run.title;$('stageTitle').textContent=run.title;setParameters(run.params);$('palette').value=palette||'lagoon';
    revision++;sourceSuggestion=run.provenance.suggestion_id||null;candidate=null;undo=null;$('candidatePanel').hidden=true;$('undoCandidate').hidden=true;
    lastRun=run;lastKey=key();baseline=creationState();showTrace(run.trace);controlsState();
  }
  async function openProject(id,{force=false}={}){
    if(!force&&scene&&creationState()!==baseline&&!confirm('打开作品会替换当前未保存的规则，继续吗？'))return;
    const data=await api('projects/'+id);chooseScene(data.project.scene,{force:true});restoreRun(data.run,data.palette);project=data.project;$('creationTitle').value=project.title;$('stageTitle').textContent=project.title;baseline=creationState();
    $('versionSelect').replaceChildren();for(const v of data.versions)$('versionSelect').add(new Option('版本 '+v.number,v.id));$('versionBar').hidden=false;$('versionNote').textContent='当前回放：最新版本';
    const url=new URL(location.href);url.searchParams.set('project',project.id);history.replaceState(null,'',url);message(`已打开「${project.title}」，可以继续修改并保存新版本。`,'success');
  }
  $('runCreation').addEventListener('click',()=>{if(!needLogin())return;action(async()=>{
    const snapshot=valueSnapshot(),snapshotKey=key(),epoch=sessionEpoch;
    message('正在隔离环境运行 Python，生成你的画面轨迹…');const data=await api('run',{method:'POST',body:{...snapshot,title:$('creationTitle').value,suggestion_id:sourceSuggestion}});
    if(epoch!==sessionEpoch||scene.id!==snapshot.scene)return;
    lastRun=data.run;lastKey=snapshotKey;showTrace(lastRun.trace);message(lastKey===key()?`运行完成 · ${lastRun.execution.elapsed_ms} ms（包含隔离环境启动） · 可以保存这次创作。`:'运行完成，但规则已继续改变。画面属于刚才提交的版本，请再次运行。',lastKey===key()?'success':'info');
  });});
  $('suggestCreation').addEventListener('click',()=>{if(!needLogin())return;action(async()=>{
    const snapshot=valueSnapshot(),startRevision=revision,epoch=sessionEpoch;message('AI 正在构思候选方案，当前规则继续保留…');
    const data=await api('suggest',{method:'POST',body:{...snapshot,prompt:$('creativePrompt').value}});
    if(epoch!==sessionEpoch||scene.id!==snapshot.scene)return;
    candidate=data.suggestion;candidateRevision=startRevision;$('candidateSummary').textContent=candidate.summary;$('candidateCode').textContent=candidate.code;
    $('candidateParameters').textContent='候选参数：'+scene.controls.map(c=>`${c.label} ${candidate.params[c.key]}`).join(' · ');$('candidatePanel').hidden=false;controlsState();message('候选已准备好。查看改动，决定是否应用；它还没有运行。');
  });});
  $('applyCandidate').addEventListener('click',()=>{
    if(!candidate||candidateRevision!==revision||busy)return;
    undo={code:$('creationCode').value,params:parameters(),title:$('creationTitle').value,suggestion:sourceSuggestion};
    $('creationCode').value=candidate.code;$('creationTitle').value=candidate.title;$('stageTitle').textContent=candidate.title;setParameters(candidate.params);sourceSuggestion=candidate.id;
    revision++;undo.after=undoKey();candidate=null;$('candidatePanel').hidden=true;$('undoCandidate').hidden=false;controlsState();message('已应用候选，尚未验证。点击运行我的规则，查看实际效果。');
  });
  $('discardCandidate').addEventListener('click',()=>{candidate=null;$('candidatePanel').hidden=true;message('保留了你的规则。你可以继续修改，或描述另一种可能。');});
  $('undoCandidate').addEventListener('click',()=>{if(!undo||undo.after!==undoKey())return;$('creationCode').value=undo.code;$('creationTitle').value=undo.title;$('stageTitle').textContent=undo.title;setParameters(undo.params);sourceSuggestion=undo.suggestion;undo=null;$('undoCandidate').hidden=true;changed();message('已撤销应用，恢复到应用前的规则。');});
  $('saveCreation').addEventListener('click',()=>{if(!needLogin()||!lastRun||key()!==lastKey)return;action(async()=>{
    const savedState=creationState();
    const data=await api('projects',{method:'POST',body:{run_id:lastRun.id,title:$('creationTitle').value,palette:$('palette').value,project_id:project?.id,revision:project?.revision}});
    project=data.project;baseline=savedState;await loadProjects();message(`「${project.title}」版本 ${project.revision} 已保存。`,'success');
    // Refresh version choices without replacing any edits made while saving.
    const details=await api('projects/'+project.id);$('versionSelect').replaceChildren();for(const v of details.versions)$('versionSelect').add(new Option('版本 '+v.number,v.id));$('versionBar').hidden=false;$('versionNote').textContent='已保存 '+project.revision+' 个版本';
    const url=new URL(location.href);url.searchParams.set('project',project.id);history.replaceState(null,'',url);
  });});
  $('versionSelect').addEventListener('change',()=>action(async()=>{
    if(!project)return;if(creationState()!==baseline&&!confirm('回看版本会替换当前未保存的规则，继续吗？'))return;
    const data=await api(`projects/${project.id}/versions/${$('versionSelect').value}`);restoreRun(data.run,data.palette);$('versionNote').textContent=`正在回看版本 ${data.number}；保存会新增版本，保留原记录。`;message('已恢复该版本的代码、参数与实际回放。');
  }));
  $('creationCode').addEventListener('input',changed);
  $('creationTitle').addEventListener('input',()=>{$('stageTitle').textContent=$('creationTitle').value;controlsState();});
  $('creationCode').addEventListener('keydown',event=>{if(event.key==='Tab'){event.preventDefault();const e=event.target,start=e.selectionStart,end=e.selectionEnd;e.setRangeText('    ',start,end,'end');changed();}if(event.key==='Enter'&&(event.ctrlKey||event.metaKey)){event.preventDefault();$('runCreation').click();}});
  $('palette').addEventListener('change',()=>renderer?.palette($('palette').value));
  $('playPause').addEventListener('click',()=>renderer?.toggle());$('timeline').addEventListener('input',()=>renderer?.seek($('timeline').value));$('playbackSpeed').addEventListener('change',()=>renderer?.setSpeed($('playbackSpeed').value));
  $('resetCode').addEventListener('click',()=>{if(!confirm('恢复内置代码和参数？当前修改将被替换。'))return;$('creationCode').value=scene.code;setParameters(scene.params);sourceSuggestion=null;undo=null;$('undoCandidate').hidden=true;changed();message('已恢复内置规则，请运行生成新的轨迹。');});
  $('newCreation').addEventListener('click',()=>chooseScene(scene.id));$('retryCatalog').addEventListener('click',loadCatalog);$('retryProjects').addEventListener('click',loadProjects);
  $('loginToCreate').addEventListener('click',carryGuestDraft);
  $('account').addEventListener('click',event=>{if(event.target.closest('a')?.getAttribute('href')?.startsWith('/login.html'))carryGuestDraft();});
  function download(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  const fileTitle=()=>$('creationTitle').value.replace(/[<>:"/\\|?*\u0000-\u001f]/g,'_').slice(0,60)||'CodeLab';
  $('exportImage').addEventListener('click',()=>{const image=renderer?.image();if(!image)return;const a=document.createElement('a');a.href=image;a.download=fileTitle()+'.png';a.click();});
  $('exportWork').addEventListener('click',()=>{if(!lastRun||key()!==lastKey)return;action(async()=>{
    const run=lastRun,title=$('creationTitle').value,palette=$('palette').value;
    const assets=await Promise.all(['/static/vendor/p5-1.11.10/p5.min.js','/static/js/workshop-renderer.js','/static/vendor/p5-1.11.10/LICENSE'].map(async url=>{const response=await fetch(url);if(!response.ok)throw Error('导出素材加载失败，请重试。');return response.text();}));
    const escape=text=>text.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const record={title,palette,run},json=JSON.stringify(record).replace(/</g,'\\u003c');
    const html=`<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escape(title)} · CodeLab</title><style>body{margin:0;background:#0c1924;color:#edf3f0;font:14px/1.7 sans-serif;padding:24px}main{max-width:1100px;margin:auto}h1{font-size:26px}#art{height:60vh;min-height:240px;border:1px solid #29414e;border-radius:12px;overflow:hidden}button,input,select{font:inherit;accent-color:#b6e8ce}button,select{background:#18323f;color:#edf3f0;border:1px solid #45645e;border-radius:5px;padding:5px 12px}.controls{display:flex;gap:16px;align-items:center;margin:16px 0}.controls input{flex:1;min-width:20px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#102431;padding:16px}small{color:#9aacb8}a{color:#b6e8ce}</style><main><h1>${escape(title)}</h1><p>智练 CodeLab · 实际运行轨迹回放</p><div id="art" role="img" aria-label="算法作品"></div><div class="controls"><button id="play">播放</button><input aria-label="回放进度" id="seek" type="range" value="0" min="0"><span id="pos"></span></div><small>画面使用保存的程序输出。本文件可离线回放，编辑后的代码需回到创作工坊运行。</small><details><summary>创作代码与参数</summary><pre id="code"></pre><pre id="params"></pre><pre id="origin"></pre></details><details><summary>开源引擎与许可</summary><p>p5.js 1.11.10 · Processing Foundation / p5.js contributors · LGPL-2.1 · <a href="https://github.com/processing/p5.js/tree/v1.11.10">对应版本源码</a>。工坊场景与渲染由智练 CodeLab 编写。</p><pre>${escape(assets[2])}</pre></details></main><script>${assets[0].replace(/<\/script/gi,'<\\/script')}</script><script>${assets[1].replace(/<\/script/gi,'<\\/script')}</script><script>const record=${json};document.getElementById('code').textContent=record.run.code;document.getElementById('params').textContent=JSON.stringify(record.run.params,null,2);document.getElementById('origin').textContent=JSON.stringify({execution:record.run.execution,provenance:record.run.provenance},null,2);const seek=document.getElementById('seek'),play=document.getElementById('play');const view=CodeLabCanvas.mount(document.getElementById('art'),record.run.trace,{palette:record.palette,autoPlay:false,onFrame:(i,n,on)=>{seek.max=n-1;seek.value=i;document.getElementById('pos').textContent=(i+1)+' / '+n;play.textContent=on?'暂停':'播放';}});play.onclick=()=>view.toggle();seek.oninput=()=>view.seek(seek.value);</script></html>`;
    download(new Blob([html],{type:'text/html;charset=utf-8'}),fileTitle()+'.html');message('交互作品已导出，包含画面、代码、参数与来源记录，可离线回放。','success');
  });});
  async function session(){
    try{const response=await fetch('/api/current_user',{cache:'no-store',credentials:'same-origin'});const result=await response.json();const next=response.ok?result.data.user:null;
      if((user?.id||null)!==(next?.id||null)&&scene){sessionEpoch++;chooseScene(scene.id,{force:true});}
      user=next;$('account').replaceChildren();
      if(user){const link=document.createElement('a');link.href='/profile.html';link.textContent=user.display_name||user.username;$('account').append(link);const token=await fetch('/api/csrf-token',{credentials:'same-origin',cache:'no-store'});const packet=await token.json();csrf=packet.data?.csrf_token||'';$('loginToCreate').hidden=true;}
      else {csrf='';for(const [name,href] of [['登录','/login.html?next=/workshop.html'],['注册','/register.html']]){const a=document.createElement('a');a.textContent=name;a.href=href;$('account').append(a);}}
    }catch{message('账号状态暂时无法确认，请刷新页面重试。','error');}
  }
  (async()=>{await session();await loadCatalog();await loadProjects();})();
  window.addEventListener('focus',async()=>{const previous=user?.id;await session();if(previous!==user?.id)await loadProjects();});
})();
