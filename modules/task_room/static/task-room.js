(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const apiRoot = '/api/task-room';
  const state = { user: null, csrf: null, scenarios: [], aiAvailable: false, project: null,
    intent: 'customer', selectedScenario: null, ruleChoices: {}, busy: false, saving: false,
    savePromise: null, saveTimer: null, conflict: false, selectedRun: null, chatOperation: null, catalogLevel: '' };
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
  const json = value => JSON.stringify(value, null, 2) ?? 'null';
  const labels = { discovery: '需求确认中', development: '开发与验收', delivered: '已交付' };
  const intentLabels = { customer: 'AI 客户', coach: '开发教练', review: '项目复盘' };
  const languageLabels = {python:'Python',cpp:'C++'};
  const sourceFiles = {python:'solution.py',cpp:'solution.cpp'};
  const avatar = client => String(client?.avatar || client?.name || '客').slice(0, 2);
  const sameId = (a, b) => String(a ?? '') === String(b ?? '');
  const date = value => {
    if (!value) return '';
    const parsed = new Date(value.endsWith?.('Z') || /[+-]\d\d:\d\d$/.test(value) ? value : value + 'Z');
    return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString('zh-CN',
      { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false });
  };
  const newId = () => crypto.randomUUID ? crypto.randomUUID() :
    'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, char => {
      const n = crypto.getRandomValues(new Uint8Array(1))[0] & 15;
      return (char === 'x' ? n : (n & 3) | 8).toString(16);
    });
  function notice(message) {
    $('notice').textContent = message || '';
    $('notice').hidden = !message;
  }
  let toastTimer;
  function toast(message) {
    clearTimeout(toastTimer);
    $('toast').textContent = message;
    $('toast').hidden = false;
    toastTimer = setTimeout(() => { $('toast').hidden = true; }, 4000);
  }
  async function request(path, options = {}) {
    const method = options.method || 'GET';
    const headers = { Accept: 'application/json' };
    if (method !== 'GET') {
      if (!state.csrf) {
        const response = await fetch('/api/csrf-token', { credentials: 'same-origin' });
        const result = await response.json().catch(() => ({}));
        if (!response.ok) { const error = new Error('请先登录后继续，当前编辑内容仍保留在页面中。'); error.status = response.status; throw error; }
        state.csrf = result.data?.csrf_token || result.csrf_token;
        if (!state.csrf) throw new Error('无法验证登录状态，请重新登录后继续。');
      }
      headers['X-CSRF-Token'] = state.csrf;
      headers['Content-Type'] = 'application/json';
    }
    let response;
    try { response = await fetch(path.startsWith('/api/') ? path : apiRoot + path,
      { ...options, headers: { ...headers, ...options.headers }, credentials: 'same-origin',
        body: options.body === undefined ? undefined : JSON.stringify(options.body) }); }
    catch (_) { throw new Error('连接中断。你的编辑内容仍在当前页面，请检查网络后重试。'); }
    const result = await response.json().catch(() => ({}));
    if (!response.ok || result.success === false) {
      const error = new Error(result.error?.message || result.message ||
        (response.status === 401 ? '登录状态已过期，请重新登录。' : '请求失败，请稍后重试。'));
      error.status = response.status;
      error.code = result.error?.code;
      if (error.code === 'CSRF_INVALID') state.csrf = null;
      throw error;
    }
    return result.data || result;
  }
  const dirty = () => Boolean(state.project && $('code-editor').value !== (state.project.code || ''));
  function saveStatus(text, kind = '') {
    $('save-status').textContent = text;
    $('save-status').className = kind;
  }
  function updateLines() {
    const editor = $('code-editor');
    $('line-numbers').textContent = Array.from({ length: editor.value.split('\n').length }, (_, i) => i + 1).join('\n');
    $('line-numbers').scrollTop = editor.scrollTop;
    $('code-length').textContent = editor.value.length.toLocaleString('en-US') + ' / 20,000';
    if (dirty()) saveStatus(state.conflict ? '草稿冲突 · 请手动保存' : '尚未保存', state.conflict ? 'failed' : 'unsaved');
    updateControls();
  }
  function latestRuns() {
    return [...(state.project?.runs || [])].sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)) || String(b.id).localeCompare(String(a.id)));
  }
  function currentPassedRun() {
    const project = state.project;
    if (!project?.contract) return null;
    // Only the latest acceptance of this exact code and contract certifies delivery.
    const match = latestRuns().find(run => run.kind === 'acceptance' && sameId(run.contract_id, project.contract.id)
      && (run.language || 'python') === (project.language || 'python') && run.code === $('code-editor').value);
    return match?.status === 'passed' ? match : null;
  }
  function updateControls() {
    const project = state.project;
    if (!project) return;
    const locked = !project.contract || project.archived;
    $('code-editor').readOnly = locked;
    $('editor-lock').hidden = Boolean(project.contract);
    ['save-code', 'reset-code', 'run-acceptance', 'run-custom'].forEach(id => {
      $(id).disabled = locked || state.busy || state.saving;
    });
    $('freeze-contract').disabled = state.busy || Boolean(project.archived);
    $('deliver-project').disabled = locked || project.state === 'delivered' || state.busy || state.saving ||
      !currentPassedRun() || dirty();
    $('send-message').disabled = state.busy || state.saving || project.archived ||
      (state.intent !== 'customer' && !project.contract) ||
      (state.intent === 'review' && !(project.runs || []).length);
    $('chat-input').disabled = project.archived;
    $('archive-project').disabled = state.busy || state.saving;
    $('export-project').disabled = state.busy;
    $('room-language').disabled = state.busy || state.saving || Boolean(project.archived);
    document.querySelectorAll('[data-change]').forEach(button => {
      button.disabled = state.busy || state.saving || project.state !== 'delivered' || project.archived || button.dataset.fulfilled === 'true';
    });
    document.querySelectorAll('[data-candidate-apply],[data-candidate-undo]').forEach(button => {
      button.disabled = state.busy || state.saving || locked || button.dataset.stale === 'true';
    });
    document.querySelectorAll('[data-intent]').forEach(button => {
      const intent = button.dataset.intent;
      button.setAttribute('aria-selected', String(intent === state.intent));
      button.disabled = state.busy || (intent !== 'customer' && !project.contract) ||
        (intent === 'review' && !(project.runs || []).length);
    });
  }
  async function recoverConflict(message = '项目已在另一处更新。') {
    const projectId = state.project?.id;
    if (!projectId) return;
    try {
      const data = await request('/projects/' + projectId);
      if (!sameId(state.project?.id, projectId)) return;
      setProject(data.project, { preserveCode: true });
      state.conflict = dirty();
      if (state.conflict) {
        saveStatus('草稿冲突 · 请手动保存', 'failed');
        notice(message + ' 本页代码保留在编辑器中，自动保存已暂停；请核对最新需求和记录，再点击“保存”决定是否覆盖服务器草稿。');
      } else { saveStatus('草稿已保存'); notice(message + ' 已读取最新项目状态，请核对后重试。'); }
    } catch (error) { notice(error.message); }
  }
  async function action(button, operation, busyLabel = null) {
    if (state.busy) return;
    state.busy = true;
    notice('');
    const previousText = button?.textContent;
    if (button) { button.classList.add('is-busy'); if (busyLabel) button.textContent = busyLabel; }
    updateControls();
    try { return await operation(); }
    catch (error) {
      if (error.code === 'AI_UNAVAILABLE' && error.status === 503) state.chatOperation = null;
      if (error.status === 409 && state.project) await recoverConflict(error.message);
      else notice(error.message);
      if (error.status === 401) state.csrf = null;
    } finally {
      state.busy = false;
      if (button) { button.classList.remove('is-busy'); if (busyLabel) button.textContent = previousText; }
      if (state.project) renderEvidence();
      updateControls();
      if (dirty() && !state.conflict) scheduleSave();
    }
  }
  function scheduleSave() {
    clearTimeout(state.saveTimer);
    if (!state.project?.contract || state.project.archived || state.conflict) return;
    state.saveTimer = setTimeout(() => {
      if (state.busy || state.saving) return;
      saveCode().catch(error => notice(error.message));
    }, 1000);
  }
  async function saveCode({ manual = false } = {}) {
    clearTimeout(state.saveTimer);
    if (state.saving) { await state.savePromise; if (dirty()) return saveCode({ manual }); return; }
    if (!state.project?.contract || !dirty()) return;
    if (state.project.archived) throw new Error('请先恢复归档项目，再保存代码。');
    if (state.conflict) {
      if (!manual) throw new Error('草稿发生冲突，请核对最新需求后点击“保存”。');
      if (!window.confirm('服务器已有更新。本页代码仍保留，是否用当前编辑器的代码覆盖服务器草稿？'))
        throw new Error('已保留本页代码，尚未覆盖服务器草稿。');
      state.conflict = false;
    }
    const projectId = state.project.id;
    const code = $('code-editor').value;
    if (code.length > 20000) throw new Error('代码超过 20,000 字符，请精简后保存。');
    const revision = state.project.draft_revision;
    state.saving = true;
    saveStatus('保存中…');
    updateControls();
    state.savePromise = (async () => {
      try {
        const data = await request('/projects/' + projectId, { method: 'PATCH', body: { code, draft_revision: revision } });
        if (!sameId(state.project?.id, projectId)) return;
        const changedWorkflow = state.project.state !== data.project.state || state.project.revision !== data.project.revision;
        setProject(data.project, { preserveCode: true, redraw: changedWorkflow });
        if ($('code-editor').value === code) saveStatus('草稿已保存');
        else { saveStatus('尚未保存', 'unsaved'); scheduleSave(); }
        if (manual) toast('草稿已保存');
      } catch (error) {
        if (error.status === 409) await recoverConflict(error.message);
        else saveStatus('保存失败 · 草稿仍在本页', 'failed');
        throw error;
      } finally { state.saving = false; state.savePromise = null; updateControls(); }
    })();
    await state.savePromise;
  }
  function renderCatalog() {
    const visible = state.scenarios.filter(scenario => !state.catalogLevel || scenario.level === state.catalogLevel);
    $('catalog-meta').textContent = visible.length + ' 份任务 · 从小项目开始';
    document.querySelectorAll('[data-task-level]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.taskLevel === state.catalogLevel)));
    $('mission-grid').innerHTML = visible.map((scenario, index) => `
      <article class="mission-card"><div class="mission-top"><span class="mission-number">${String(index + 1).padStart(2, '0')}</span><span class="mission-tag">${esc(scenario.difficulty || '业务实战')}</span></div>
      <h3>${esc(scenario.title)}</h3><p class="mission-subtitle">${esc(scenario.subtitle || scenario.deliverable)}</p>
      <div class="mission-client"><span class="mini-avatar">${esc(avatar(scenario.client))}</span><span>${esc(scenario.client?.name)} · ${esc(scenario.client?.role)}</span></div>
      <footer><span class="muted">${esc(scenario.duration || '按自己的节奏完成')}</span><button type="button" class="mission-open" data-scenario="${esc(scenario.id)}">查看任务 <span aria-hidden="true">↗</span></button></footer></article>`).join('');
  }
  async function loadProjects() {
    if (!state.user) return;
    $('project-list').innerHTML = '<p class="empty-state">正在读取项目…</p>';
    try {
      const data = await request('/projects?archived=' + ($('show-archived').checked ? '1' : '0'));
      $('project-list').innerHTML = (data.projects || []).map(project => `<article class="project-row">
        <div class="project-row-main"><div class="project-row-title">${esc(project.title || project.scenario?.title || '实战项目')} · ${esc(languageLabels[project.language || 'python'])}</div><p class="project-row-meta">${esc(project.scenario_title || '')}${project.contract?.version ? '需求 v' + esc(project.contract.version) : '需求待确认'} · 更新于 ${esc(date(project.updated_at))}</p></div>
        <span class="state-badge ${esc(project.archived ? 'archived' : project.state)}">${project.archived ? '已归档' : esc(labels[project.state] || project.state)}</span>
        <button class="button button-outline" data-project="${esc(project.id)}" type="button">${project.archived ? '查看档案' : '继续项目'} <span aria-hidden="true">→</span></button></article>`).join('') ||
        `<p class="empty-state">${$('show-archived').checked ? '没有已归档的项目。' : '还没有进行中的项目。选择上面的一份任务开始吧。'}</p>`;
    } catch (error) { $('project-list').innerHTML = `<p class="empty-state">${esc(error.message)} <button type="button" id="retry-projects" class="text-button">重新读取</button></p>`; }
  }
  function previewScenario(id) {
    const scenario = state.scenarios.find(item => sameId(item.id, id));
    if (!scenario) return;
    state.selectedScenario = scenario;
    $('scenario-preview').innerHTML = `<p class="eyebrow">YOUR NEXT ASSIGNMENT</p><h2>${esc(scenario.title)}</h2><p class="muted">${esc(scenario.subtitle)}</p>
      <div class="preview-facts"><span>${esc(scenario.client?.name)} / ${esc(scenario.client?.role)}</span><span>${esc(scenario.difficulty)}</span><span>${esc(scenario.duration)}</span></div>
      <p class="brief-text">${esc(scenario.brief)}</p><h3>需要你问清楚的事情</h3>${(scenario.rule_groups || []).map(group => `<div class="preview-rule"><b>${esc(group.label)}</b><span>${esc(group.question)}</span></div>`).join('')}
      <p class="helper-text">${esc(scenario.deliverable)} · 三种语言均提供 JSON 解析工具 · 隔离环境验收</p>`;
    $('create-project').textContent = state.user ? '领取任务，进入任务室 →' : '登录后领取任务 →';
    $('scenario-dialog').showModal();
  }
  function navigateProject(id) {
    const url = new URL(location.href);
    if (id) url.searchParams.set('project', id); else url.searchParams.delete('project');
    if (state.project) url.searchParams.set('language', state.project.language || 'python');
    history.replaceState(null, '', url.pathname + url.search + url.hash);
  }
  async function canLeave() {
    clearTimeout(state.saveTimer);
    if (state.saving) await state.savePromise.catch(() => {});
    if (!dirty()) return true;
    try { await saveCode(); return !dirty(); }
    catch (_) { return window.confirm('当前代码尚未保存。离开会丢失本页未保存的编辑，确定离开吗？'); }
  }
  async function openProject(id) {
    if (!(await canLeave())) return;
    await action(null, async () => {
      const data = await request('/projects/' + id);
      state.selectedRun = null; state.conflict = false; state.intent = 'customer';
      state.ruleChoices = {};
      setProject(data.project, { forceCode: true });
      $('catalog-view').hidden = true; $('room-view').hidden = false;
      navigateProject(data.project.id);
      window.scrollTo({ top: 0, behavior: 'instant' });
    });
  }
  function setProject(project, { forceCode = false, preserveCode = false, redraw = true } = {}) {
    if (!project) return;
    const keep = !forceCode && (preserveCode || (sameId(state.project?.id, project.id) && dirty()));
    state.project = project;
    if (!keep) $('code-editor').value = project.code || project.contract?.starter_code || project.scenario?.starter_code || '';
    if (!Object.keys(state.ruleChoices).length) {
      state.ruleChoices = { ...(project.contract?.rules || {}) };
      for (const group of project.scenario?.rule_groups || [])
        if (!state.ruleChoices[group.key]) state.ruleChoices[group.key] = group.recommended || group.options?.[0]?.value;
    }
    if (redraw) renderProject(); else { renderEvidence(); renderTimeline(); }
    updateLines();
    if (!dirty()) saveStatus('草稿已保存');
  }
  function renderProject() {
    const project = state.project;
    const scenario = project.scenario || state.scenarios.find(item => sameId(item.id, project.scenario_id)) || {};
    const contract = project.contract;
    const language = project.language || 'python';
    $('room-language').value = language;
    $('create-language').value = language;
    $('source-filename').textContent = sourceFiles[language];
    $('code-language-label').textContent = languageLabels[language] + ' 项目代码';
    $('code-guide').textContent = project.language_guide || '实现 solve(data)，返回约定 JSON 结果。';
    $('room-title').textContent = project.title || scenario.title || '实战任务';
    document.title = (project.title || scenario.title || '实战任务室') + ' · 智练 CodeLab';
    $('room-client').textContent = 'PROJECT ' + String(project.id).slice(0, 8).toUpperCase() + ' / ' + (scenario.client?.name || '客户任务');
    $('room-subtitle').textContent = scenario.subtitle || '';
    $('room-state').className = 'state-badge ' + (project.archived ? 'archived' : project.state);
    $('room-state').textContent = project.archived ? '已归档 · 只读' : labels[project.state] || project.state;
    $('archive-project').textContent = project.archived ? '恢复项目' : '归档';
    $('client-initial').textContent = avatar(scenario.client);
    $('client-name').textContent = [scenario.client?.name, scenario.client?.role].filter(Boolean).join(' · ');
    $('client-brief').textContent = (scenario.client?.initial ? '“' + scenario.client.initial + '”\n\n' : '') + (scenario.brief || '');
    $('input-schema').textContent = contract?.input_schema || scenario.input_schema || '';
    $('output-schema').textContent = contract?.output_schema || scenario.output_schema || '';
    const steps = ['discovery', 'development', 'delivered'];
    document.querySelectorAll('.workflow [data-step]').forEach(item => {
      const stepIndex = steps.indexOf(item.dataset.step), currentIndex = steps.indexOf(project.state);
      item.className = stepIndex === currentIndex ? 'current' : stepIndex < currentIndex ? 'done' : '';
      if (stepIndex === currentIndex) item.setAttribute('aria-current', 'step'); else item.removeAttribute('aria-current');
    });
    $('rules-form').hidden = Boolean(contract);
    $('contract-spec').hidden = !contract;
    $('rules-title').textContent = contract ? '已确认的需求' : '把模糊变明确';
    $('contract-number').textContent = contract ? '需求 v' + contract.version : '待确认';
    $('rules-hint').textContent = contract ? '本版本已经锁定。交付后接收需求变更，会生成新的版本，旧记录会保留。' : '先与客户讨论，再选择你要落实的规则。AI 的回复不会自动改变你的选择。';
    if (!contract) renderRules(scenario);
    else {
      $('contract-description').textContent = contract.spec || '';
      $('rule-summary').innerHTML = (contract.rule_labels || []).map(rule => `<div class="rule-summary-row"><b>${esc(rule.label)}</b><span>${esc(rule.text || rule.value)}</span></div>`).join('');
      $('contract-history').innerHTML = [...(project.contracts || [])].reverse().map(item => `<div class="contract-history-row"><b>需求 v${esc(item.version)}${sameId(item.id, contract.id) ? ' · 当前版本' : ''}</b><span>${esc(date(item.created_at))}</span><p>${esc((item.rule_labels || []).map(rule => rule.label + '：' + (rule.text || rule.value)).join('；'))}</p></div>`).join('');
    }
    $('cases-count').textContent = contract ? (contract.cases || []).length + ' 条公开验收' : '待确认需求';
    $('acceptance-cases').innerHTML = contract ? (contract.cases || []).map((item, index) => `
      <details class="case-detail"><summary>${esc(item.name)}<span>${String(index + 1).padStart(2, '0')}</span></summary>
      <p class="case-json-label">输入</p><pre class="json-block">${esc(json(item.input))}</pre><p class="case-json-label">预期结果</p><pre class="json-block">${esc(json(item.expected))}</pre></details>`).join('') : '<p class="empty-state compact">确认需求后生成验收样例。</p>';
    if (!$('custom-input').value || $('custom-input').dataset.project !== String(project.id)) {
      $('custom-input').value = json(contract?.example_input || scenario.example_input || {});
      $('custom-input').dataset.project = project.id;
    }
    $('ai-status').textContent = state.aiAvailable ? 'AI 接口已配置' : 'AI 接口未配置';
    renderChat(); renderEvidence(); renderChanges(); renderTimeline(); updateControls();
  }
  function renderRules(scenario) {
    $('rule-groups').innerHTML = (scenario.rule_groups || []).map(group => `<fieldset class="rule-group"><legend>${esc(group.label)}</legend><p class="rule-question">${esc(group.question)}</p>
      ${(group.options || []).map(option => `<label class="rule-option"><input type="radio" name="rule_${esc(group.key)}" data-rule="${esc(group.key)}" value="${esc(option.value)}" ${state.ruleChoices[group.key] === option.value ? 'checked' : ''} required><span><b>${esc(option.label)}</b><small>${esc(option.description)}</small></span></label>`).join('')}</fieldset>`).join('');
  }
  function renderChat() {
    const project = state.project;
    const messages = (project.messages || []).filter(message => message.intent === state.intent || message.role === 'system');
    const hints = {
      customer: '询问边界条件、处理方式或业务优先级。最终规则由你确认。',
      coach: '教练会读取当前需求与编辑器代码。代码建议先供你查看，只有点击应用才会进入草稿。',
      review: '依据本项目实际的需求、运行和变更记录复盘；不把一次通过包装成能力评估。'
    };
    $('chat-hint').textContent = state.aiAvailable ? hints[state.intent] : '当前未配置 AI 接口。任务资料、规则确认、开发与真实验收仍可使用。';
    $('chat-context').textContent = state.intent === 'coach' ? '发送需求、对话与当前编辑器代码' : state.intent === 'review' ? '发送项目记录与当前代码' : '发送任务资料与当前对话';
    $('chat-input').placeholder = state.intent === 'customer' ? '例如：同一个人重复报名，应该保留哪一条？' : state.intent === 'coach' ? '例如：帮我定位为什么这条验收没有通过。' : '例如：回顾这次变更，哪些边界条件是我忽略的？';
    const wasAtBottom = $('chat-messages').scrollHeight - $('chat-messages').scrollTop - $('chat-messages').clientHeight < 80;
    $('chat-messages').innerHTML = messages.map(message => {
      const payload = message.payload || {};
      const candidate = payload.code && message.role === 'assistant';
      const stale = candidate && payload.contract_id && !sameId(payload.contract_id, project.contract?.id);
      const candidateState = payload.state || 'pending';
      const candidateBlock = candidate ? `<div class="candidate-box"><details><summary>查看代码建议 · ${candidateState === 'applied' ? '已应用' : candidateState === 'undone' ? '已撤销' : '待你决定'}</summary><pre>${esc(payload.code)}</pre>${payload.base_code ? `<details><summary>对照应用前的代码</summary><pre>${esc(payload.base_code)}</pre></details>` : ''}</details>
        <div class="candidate-actions">${candidateState === 'applied' ? `<button type="button" class="button button-outline" data-candidate-undo="${esc(message.id)}" data-stale="${stale}">撤销这次应用</button>` : ['pending', 'undone'].includes(candidateState) ? `<button type="button" class="button button-outline" data-candidate-apply="${esc(message.id)}" data-stale="${stale}">${candidateState === 'undone' ? '再次应用建议' : '应用到编辑器'}</button>` : ''}<span class="candidate-state">${stale ? '需求版本已变更，请重新请求建议' : candidateState === 'undone' ? '原代码已恢复' : '保留代码版本校验'}</span></div></div>` : '';
      return `<article class="chat-message ${esc(message.role)}"><div class="message-meta"><b>${message.role === 'user' ? '你' : message.role === 'system' ? '任务记录' : esc(intentLabels[message.intent] || 'AI 助手')}</b><span>${esc(date(message.created_at))}</span>${message.model ? `<span class="message-model">${esc(message.model)}</span>` : ''}</div><div class="message-content">${esc(message.content)}</div>${candidateBlock}</article>`;
    }).join('') || `<p class="empty-state compact">${state.intent === 'customer' ? '客户的初始需求在左侧任务资料里。先问一个关键问题。' : state.intent === 'coach' ? '写下代码后，告诉教练你遇到了什么问题。' : '完成一次运行后，回顾自己的决策与修改。'}</p>`;
    if (wasAtBottom) $('chat-messages').scrollTop = $('chat-messages').scrollHeight;
  }
  function renderEvidence() {
    const project = state.project;
    if (!project) return;
    const runs = latestRuns();
    const run = state.selectedRun ? runs.find(item => sameId(item.id, state.selectedRun)) :
      runs.find(item => sameId(item.contract_id, project.contract?.id));
    $('evidence-version').textContent = run ? (run.kind === 'custom' ? '自定义试运行' : '需求 v' + run.contract_version) :
      project.contract ? '需求 v' + project.contract.version : '—';
    $('run-score').innerHTML = run ? `<b>${esc(run.passed ?? 0)}<span style="font-size:25px;opacity:.6"> / ${esc(run.total ?? 0)}</span></b><span>${run.status === 'passed' ? '本次全部通过' : run.status === 'running' ? '隔离环境运行中' : '本次尚未通过'}</span>` : '<b>—</b><span>尚未运行验收</span>';
    const execution = run?.execution || {};
    const old = run && !sameId(run.contract_id, project.contract?.id);
    const codeDifferent = run && run.code !== $('code-editor').value;
    let summary = run ? `${execution.execution_backend === 'docker' ? 'Docker 隔离执行' : execution.execution_backend || '运行记录'}${execution.time !== undefined ? ' · ' + (Number(execution.time) / 1000).toFixed(2) + ' 秒' : ''}` : '确认规则，写出代码，再检查每一条业务约定。';
    if (old) summary += '\n这是旧需求版本的记录，不代表当前版本验收。';
    if (codeDifferent) summary += '\n编辑器代码与本次运行快照不同，请重新验收。';
    if (run?.kind === 'custom') summary += '\n自定义试运行结果不会作为交付依据。';
    if (execution.error) summary += '\n' + execution.error;
    $('run-summary').textContent = summary;
    $('run-results').innerHTML = (run?.results || []).map(item => `<details class="result-row"><summary><span class="result-check ${item.passed ? '' : 'fail'}">${item.passed ? '✓' : '×'}</span>${esc(item.name || item.id)}</summary>
      <p class="case-json-label">输入</p><pre class="json-block">${esc(json(item.input))}</pre>${Object.prototype.hasOwnProperty.call(item, 'expected') ? `<p class="case-json-label">预期结果</p><pre class="json-block">${esc(json(item.expected))}</pre>` : ''}<p class="case-json-label">实际结果</p><pre class="json-block">${esc(json(item.actual))}</pre>${item.error ? `<p class="result-error">${esc(item.error)}</p>` : ''}</details>`).join('');
    $('deliver-project').textContent = project.state === 'delivered' ? '本版本已交付 ✓' : '确认交付 ✓';
    $('delivery-hint').textContent = project.delivery ? '交付于 ' + date(project.delivery.at) + ' · 当前需求与代码快照已留档。' :
      currentPassedRun() ? (dirty() ? '代码尚未保存，请保存后确认交付。' : '当前代码已通过全部验收，可以确认交付。') : '当前需求的全部验收通过，且代码保存后，才能交付。';
    $('run-history').innerHTML = runs.map(item => `<button type="button" class="run-history-button" data-run="${esc(item.id)}"><span>${item.kind === 'custom' ? '试运行' : '需求 v' + esc(item.contract_version)} · ${esc(item.passed ?? 0)}/${esc(item.total ?? 0)}</span><b>${item.status === 'passed' ? '通过' : item.status === 'running' ? '运行中' : '未通过'}</b><small>${esc(date(item.created_at))}</small></button>`).join('') || '<p class="empty-state compact">还没有运行记录。</p>';
  }
  function renderChanges() {
    const project = state.project;
    const groups = project.scenario?.rule_groups || [];
    $('changes-intro').textContent = project.state === 'delivered' ? '选择要接收的需求。确认后生成新版本，重新开发与验收。' : '完成一次交付后，接住客户提出的需求变更。';
    $('change-list').innerHTML = (project.scenario?.changes || []).map(change => {
      const fulfilled = Object.entries(change.patch || {}).every(([key, value]) => project.contract?.rules?.[key] === value);
      const diffs = Object.entries(change.patch || {}).map(([key, value]) => {
        const group = groups.find(item => item.key === key);
        const old = group?.options?.find(item => item.value === project.contract?.rules?.[key]);
        const next = group?.options?.find(item => item.value === value);
        return esc(group?.label || key) + '：' + esc(old?.label || '待确认') + ' → ' + esc(next?.label || value);
      });
      return `<article class="change-card"><h3>${esc(change.title)}</h3><p>${esc(change.message)}</p><div class="change-diff">${diffs.join('<br>')}</div><button type="button" class="button button-outline" data-change="${esc(change.id)}" data-fulfilled="${fulfilled}">${fulfilled ? '当前需求已包含' : '接收这项变更 →'}</button></article>`;
    }).join('') || '<p class="empty-state compact">本任务没有新的变更要求。</p>';
  }
  function renderTimeline() {
    const project = state.project;
    const stats = project.stats || {};
    $('project-stats').innerHTML = [['需求版本', stats.contracts ?? project.contracts?.length ?? 0], ['实际运行', stats.runs ?? project.runs?.length ?? 0], ['通过次数', stats.passed ?? (project.runs || []).filter(item => item.status === 'passed').length]].map(([label, number]) => `<div class="project-stat"><b>${esc(number)}</b><span>${label}</span></div>`).join('');
    $('history-count').textContent = (project.events || []).length + ' 条';
    $('event-timeline').innerHTML = [...(project.events || [])].reverse().map(event => `<li><b>${esc(event.title || event.kind)}</b><small>${esc(date(event.created_at))}</small></li>`).join('');
  }

  $('mission-grid').addEventListener('click', event => { const button = event.target.closest('[data-scenario]'); if (button) previewScenario(button.dataset.scenario); });
  $('create-project').addEventListener('click', () => action($('create-project'), async () => {
    if (!state.user) { location.href = '/login.html?next=' + encodeURIComponent(location.pathname + location.search); return; }
    const data = await request('/projects', { method: 'POST', body: { scenario_id: state.selectedScenario.id, language: $('create-language').value } });
    $('scenario-dialog').close();
    state.ruleChoices = {}; state.conflict = false; state.selectedRun = null; state.intent = 'customer';
    setProject(data.project, { forceCode: true });
    $('catalog-view').hidden = true; $('room-view').hidden = false;
    navigateProject(data.project.id); window.scrollTo({ top: 0, behavior: 'instant' });
  }, '正在创建任务…'));
  $('project-list').addEventListener('click', event => {
    const button = event.target.closest('[data-project]');
    if (button) openProject(button.dataset.project);
    else if (event.target.closest('#retry-projects')) loadProjects();
  });
  $('show-archived').addEventListener('change', loadProjects);
  $('room-language').addEventListener('change', async () => {
    const language = $('room-language').value, source = state.project;
    $('room-language').value = source.language || 'python';
    if (state.busy || !(await canLeave())) return;
    await action(null, async () => {
      const listed = await request('/projects');
      const previous = (listed.projects || []).find(project => project.scenario_id === source.scenario_id && (project.language || 'python') === language);
      const data = previous ? await request('/projects/' + previous.id) : await request('/projects', {method:'POST',body:{scenario_id:source.scenario_id,language}});
      state.ruleChoices = {}; state.conflict = false; state.selectedRun = null; state.intent = 'customer';
      setProject(data.project,{forceCode:true}); navigateProject(data.project.id);
      toast(previous ? '已恢复此语言的项目。其他语言草稿和证据仍保留。' : '已创建此语言的独立项目，请确认本项目需求。原项目仍保留。');
    });
  });
  $('back-catalog').addEventListener('click', async () => {
    if (state.busy) { toast('当前操作仍在进行，请等待完成。'); return; }
    if (!(await canLeave())) return;
    state.project = null; state.conflict = false; state.ruleChoices = {};
    $('room-view').hidden = true; $('catalog-view').hidden = false; notice('');
    document.title = '实战任务室 · 智练 CodeLab'; navigateProject(null); await loadProjects();
  });
  $('rules-form').addEventListener('change', event => { if (event.target.dataset.rule) state.ruleChoices[event.target.dataset.rule] = event.target.value; });
  $('rules-form').addEventListener('submit', event => {
    event.preventDefault();
    action($('freeze-contract'), async () => {
      const data = await request('/projects/' + state.project.id + '/freeze', { method: 'POST',
        body: { rules: state.ruleChoices, revision: state.project.revision } });
      setProject(data.project, { forceCode: true });
      toast('需求已确认，开始开发。所有验收样例现已生成。');
      $('code-editor').focus();
    }, '正在确认需求…');
  });
  $('code-editor').addEventListener('input', () => { updateLines(); renderEvidence(); scheduleSave(); });
  $('code-editor').addEventListener('scroll', () => { $('line-numbers').scrollTop = $('code-editor').scrollTop; });
  $('code-editor').addEventListener('keydown', event => {
    if (event.key === 'Tab' && !$('code-editor').readOnly) {
      event.preventDefault(); const editor = $('code-editor'), start = editor.selectionStart, end = editor.selectionEnd;
      editor.setRangeText('    ', start, end, 'end'); editor.dispatchEvent(new Event('input'));
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
      event.preventDefault(); saveCode({ manual: true }).catch(error => notice(error.message));
    }
  });
  $('save-code').addEventListener('click', () => saveCode({ manual: true }).catch(error => notice(error.message)));
  $('reset-code').addEventListener('click', () => {
    if (!window.confirm('恢复起始代码会替换编辑器中的当前代码，确定恢复吗？')) return;
    $('code-editor').value = state.project.contract?.starter_code || state.project.scenario.starter_code || '';
    updateLines(); renderEvidence(); scheduleSave();
  });
  async function runCode(kind, button) {
    await action(button, async () => {
      let input;
      if (kind === 'custom') { try { input = JSON.parse($('custom-input').value); } catch (_) { throw new Error('自定义输入不是有效的 JSON，请检查逗号、引号与括号。'); } }
      await saveCode();
      const data = await request('/projects/' + state.project.id + '/run', { method: 'POST',
        body: { kind, code: $('code-editor').value, contract_id: state.project.contract.id, ...(kind === 'custom' ? { input } : {}) } });
      state.selectedRun = data.run?.id || null;
      setProject(data.project, { preserveCode: true });
      toast(data.run?.status === 'passed' ? (kind === 'custom' ? '试运行完成，请查看实际输出。' : '当前代码通过全部验收。') : '运行完成，请查看验收证据。');
    }, kind === 'custom' ? '正在隔离试运行…' : '正在隔离验收…');
  }
  $('run-acceptance').addEventListener('click', () => runCode('acceptance', $('run-acceptance')));
  $('run-custom').addEventListener('click', () => runCode('custom', $('run-custom')));
  $('deliver-project').addEventListener('click', () => action($('deliver-project'), async () => {
    await saveCode();
    const data = await request('/projects/' + state.project.id + '/deliver', { method: 'POST', body: {
      code: $('code-editor').value, contract_id: state.project.contract.id, revision: state.project.revision } });
    setProject(data.project, { preserveCode: true });
    toast('本版本交付完成。可以导出作品，或接收客户的下一项变更。');
  }, '正在确认交付…'));
  $('change-list').addEventListener('click', event => {
    const button = event.target.closest('[data-change]');
    if (!button || button.disabled) return;
    const change = state.project.scenario.changes.find(item => sameId(item.id, button.dataset.change));
    if (!window.confirm('接收“' + change.title + '”？\n\n' + change.message + '\n\n将创建新的需求版本，保留当前代码与历史记录。新版本需要重新验收和交付。')) return;
    action(button, async () => {
      await saveCode();
      const data = await request('/projects/' + state.project.id + '/changes', { method: 'POST', body: { change_id: change.id, revision: state.project.revision } });
      state.selectedRun = null; state.ruleChoices = {}; setProject(data.project, { preserveCode: true });
      toast('新需求版本已建立。请查看规则变化，再修改代码重新验收。');
    }, '正在接收变更…');
  });
  document.querySelectorAll('[data-intent]').forEach(button => button.addEventListener('click', () => {
    state.intent = button.dataset.intent; state.chatOperation = null; renderChat(); updateControls();
  }));
  $('chat-form').addEventListener('submit', event => {
    event.preventDefault();
    if ($('send-message').disabled) return;
    const message = $('chat-input').value.trim();
    if (!message) { $('chat-input').focus(); return; }
    const signature = state.project.id + ':' + state.intent + ':' + message + ':' + $('code-editor').value;
    if (state.chatOperation?.signature !== signature) state.chatOperation = { signature, id: newId() };
    action($('send-message'), async () => {
      const data = await request('/projects/' + state.project.id + '/messages', { method: 'POST', body: {
        intent: state.intent, message, code: $('code-editor').value, operation_id: state.chatOperation.id } });
      setProject(data.project, { preserveCode: true });
      $('chat-input').value = ''; state.chatOperation = null;
      $('chat-messages').scrollTop = $('chat-messages').scrollHeight;
    }, 'AI 正在回复…');
  });
  $('chat-messages').addEventListener('click', event => {
    const button = event.target.closest('[data-candidate-apply],[data-candidate-undo]');
    if (!button || button.disabled) return;
    const undo = Boolean(button.dataset.candidateUndo);
    const messageId = undo ? button.dataset.candidateUndo : button.dataset.candidateApply;
    if (dirty() && !window.confirm('编辑器有尚未保存的修改。先保存当前代码，再' + (undo ? '撤销这次应用' : '应用代码建议') + '？代码版本发生变化时操作会被阻止。')) return;
    action(button, async () => {
      await saveCode();
      const data = await request('/projects/' + state.project.id + '/messages/' + messageId + (undo ? '/undo' : '/apply'),
        { method: 'POST', body: { draft_revision: state.project.draft_revision } });
      setProject(data.project, { forceCode: true });
      toast(undo ? '已恢复应用前的代码，请重新验收。' : '代码建议已应用并保存，请运行验收。');
    }, undo ? '正在撤销…' : '正在应用…');
  });
  $('run-history').addEventListener('click', event => {
    const button = event.target.closest('[data-run]');
    if (button) { state.selectedRun = button.dataset.run; renderEvidence(); $('evidence-title').scrollIntoView({ behavior: 'smooth', block: 'center' }); }
  });
  $('archive-project').addEventListener('click', () => {
    const archived = !state.project.archived;
    if (!window.confirm(archived ? '归档这个项目？代码、需求与运行记录都会保留，之后可以恢复。' : '恢复这个项目并继续开发？')) return;
    action($('archive-project'), async () => {
      if (archived) await saveCode();
      const data = await request('/projects/' + state.project.id, { method: 'PATCH', body: { archived, revision: state.project.revision } });
      setProject(data.project, { preserveCode: true }); toast(archived ? '项目已归档，所有记录保留。' : '项目已恢复。');
      if (archived) {
        state.project = null; state.ruleChoices = {}; state.conflict = false;
        $('room-view').hidden = true; $('catalog-view').hidden = false;
        document.title = '实战任务室 · 智练 CodeLab'; navigateProject(null);
        await loadProjects();
      }
    });
  });
  $('export-project').addEventListener('click', () => action($('export-project'), async () => {
    await saveCode();
    const response = await fetch(apiRoot + '/projects/' + state.project.id + '/export', { credentials: 'same-origin' });
    if (!response.ok) { const result = await response.json().catch(() => ({})); throw new Error(result.error?.message || '交付包导出失败，请重新登录或稍后重试。'); }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob); const link = document.createElement('a');
    link.href = url; link.download = 'task-room-' + String(state.project.id).slice(0, 8) + '.zip'; document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 5000); toast('交付包已导出，包含需求、代码和真实验收记录。');
  }, '正在打包…'));
  window.addEventListener('beforeunload', event => { if (dirty() || state.saving || state.busy) { event.preventDefault(); event.returnValue = ''; } });
  document.querySelector('.site-header').addEventListener('click', event => {
    if (!dirty()) return;
    const link = event.target.closest('a');
    if (link && !window.confirm('当前代码尚未保存，离开页面会丢失这些编辑。确定离开吗？')) event.preventDefault();
  });

  async function init() {
    const preferred = new URLSearchParams(location.search).get('language');
    if (languageLabels[preferred]) $('create-language').value = preferred;
    const results = await Promise.allSettled([request('/catalog'), request('/api/current_user')]);
    if (results[0].status === 'fulfilled') {
      const catalog = results[0].value;
      const levels = {starter: 0, basic: 1, applied: 2};
      state.scenarios = [...(catalog.scenarios || [])].sort((a, b) => (levels[a.level] ?? 2) - (levels[b.level] ?? 2) || (a.estimated_minutes || 45) - (b.estimated_minutes || 45));
      state.aiAvailable = Boolean(catalog.ai_available); renderCatalog();
    } else {
      $('mission-grid').innerHTML = '<p class="empty-state">任务资料暂时无法读取。<button class="text-button" id="reload-catalog">重新加载</button></p>';
      $('catalog-meta').textContent = '连接暂时不可用'; notice(results[0].reason.message);
      $('reload-catalog').addEventListener('click', () => location.reload());
    }
    if (results[1].status === 'fulfilled') {
      state.user = results[1].value.user || results[1].value;
      $('account-link').textContent = state.user.display_name || state.user.username || '个人中心';
      $('account-link').href = '/profile.html';
      await loadProjects();
    }
    const projectId = new URLSearchParams(location.search).get('project');
    if (projectId) {
      if (state.user) await openProject(projectId);
      else notice('请登录后打开已保存的项目。');
    } else {
      const scenarioId = new URLSearchParams(location.search).get('scenario');
      if (scenarioId && state.scenarios.some(scenario => scenario.id === scenarioId)) {
        previewScenario(scenarioId);
        notice('这是学习推荐中的项目。先查看任务资料，再决定是否领取。');
      }
    }
  }
  document.querySelectorAll('[data-task-level]').forEach(button => button.addEventListener('click', () => {
    state.catalogLevel = button.dataset.taskLevel;
    renderCatalog();
  }));
  init().catch(error => notice(error.message));
})();
