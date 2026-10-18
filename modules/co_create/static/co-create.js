(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const json = value => JSON.stringify(value, null, 2) ?? 'null';
  const compact = value => JSON.stringify(value) ?? 'null';
  const modeNames = {examples: '以例造程序', review: 'AI 代码质检'};
  const state = {mode: new URLSearchParams(location.search).get('mode') === 'review' ? 'review' : 'examples',
    user: null, csrf: null, scenarios: [], sessions: [], session: null, active: {}, drafts: {},
    busy: false, conflict: false, ai: false, editing: null, currentCompare: null};
  const formIds = ['example-input','example-expected','compare-input','review-input','review-prediction','review-reflection','review-code'];
  const sources = {ai: 'AI 实时生成', teaching: '预置教学样例', student: '你修订的代码'};
  const date = value => value ? new Date(value).toLocaleString('zh-CN', {month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}) : '';
  const scenario = () => state.scenarios.find(s => s.id === $('scenario-select').value);
  const generation = () => state.session?.state.generations.find(g => g.id === state.session.state.current_generation_id);
  const draftKey = () => state.session?.id || state.mode + ':' + $('scenario-select').value;
  function capture() {
    const draft = Object.fromEntries(formIds.map(id => [id, $(id).value]));
    draft.judgment = document.querySelector('[name=judgment]:checked')?.value || '';
    draft.editing = state.editing;
    return draft;
  }
  function restore(draft) {
    if (!draft) return;
    formIds.forEach(id => { if (Object.hasOwn(draft, id)) $(id).value = draft[id]; });
    document.querySelectorAll('[name=judgment]').forEach(input => { input.checked = input.value === draft.judgment; });
    state.editing = draft.editing || null;
    $('example-form-title').textContent = state.editing ? '编辑这个例子' : '补充一个例子';
    $('cancel-edit').hidden = !state.editing;
  }
  function stash() { state.drafts[draftKey()] = capture(); }
  function notice(message, reload = false) {
    $('notice').replaceChildren();
    $('notice').hidden = !message;
    if (!message) return;
    $('notice').append(document.createTextNode(message));
    if (reload) {
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'button button-outline'; button.textContent = '读取最新记录，保留本页表单';
      button.addEventListener('click', () => perform('正在读取最新记录…', async () => {
        const draft = capture();
        const data = await request('/sessions/' + state.session.id);
        state.conflict = false; setSession(data.session); restore(draft);
        notice('已读取最新记录；本页表单仍保留，请核对例子、代码和最新状态，再重新提交。');
      }));
      $('notice').append(document.createElement('br'), button);
    }
    if (!state.user && message) {
      const link = document.createElement('a'); link.href = '/login.html?next=' + encodeURIComponent(location.pathname + location.search); link.textContent = ' 去登录';
      $('notice').append(link);
    }
  }
  let toastTimer;
  function toast(message) {
    clearTimeout(toastTimer); $('toast').textContent = message; $('toast').hidden = false;
    toastTimer = setTimeout(() => { $('toast').hidden = true; }, 4000);
  }
  async function request(path, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 125000);
    const readResult = response => response.json().catch(error => {
      if (controller.signal.aborted) throw error;
      return {};
    });
    try {
      const method = options.method || 'GET';
      const headers = {Accept:'application/json'};
      if (method !== 'GET') {
        if (!state.csrf) {
          const response = await fetch('/api/csrf-token', {credentials:'same-origin',signal:controller.signal});
          const result = await readResult(response);
          if (!response.ok) { const error = new Error('请先登录后继续；本页输入仍然保留。'); error.status = response.status; throw error; }
          state.csrf = result.data?.csrf_token || result.csrf_token;
          if (!state.csrf) throw new Error('无法验证登录状态，请重新登录后继续。');
        }
        headers['X-CSRF-Token'] = state.csrf; headers['Content-Type'] = 'application/json';
      }
      const response = await fetch(path.startsWith('/api/') ? path : '/api/co-create' + path,
        {...options, headers, credentials:'same-origin', signal:controller.signal,
          body: options.body === undefined ? undefined : JSON.stringify(options.body)});
      const result = await readResult(response);
      if (!response.ok || result.success === false) {
        const error = new Error(result.error?.message || (response.status === 401 ? '登录已过期，请重新登录；本页输入仍然保留。' : '请求未完成，请稍后重试。'));
        error.status = response.status; error.code = result.error?.code;
        if (error.code === 'CSRF_INVALID' || response.status === 401) state.csrf = null;
        throw error;
      }
      return result.data || result;
    } catch (cause) {
      if (!controller.signal.aborted && cause.name !== 'TypeError') throw cause;
      const error = new Error(controller.signal.aborted
        ? '等待响应超时，本页输入仍保留。服务器任务可能仍在进行或已经完成；请先读取最新记录，再决定是否重试。'
        : '连接中断，本页输入仍保留。请求可能已在服务器完成；请先读取最新记录，再决定是否重试。');
      error.code = 'NETWORK_STATE_UNKNOWN'; throw error;
    } finally { clearTimeout(timeout); }
  }
  function readJson(id, label) {
    const value = $(id).value.trim();
    if (!value) { $(id).focus(); throw new Error('请填写' + label + '，格式为 JSON。'); }
    try { return JSON.parse(value); }
    catch (_) { $(id).focus(); throw new Error(label + '不是有效 JSON。字符串请使用英文双引号，数组使用方括号。'); }
  }
  async function perform(label, operation) {
    if (state.busy) return;
    state.busy = true; notice(''); $('busy-message').textContent = label; $('busy-status').hidden = false;
    $('main-content').setAttribute('aria-busy','true'); controls();
    try { await operation(); }
    catch (error) {
      if (state.session && ((error.status === 409 && error.code === 'STALE_REVISION') || error.code === 'NETWORK_STATE_UNKNOWN')) {
        state.conflict = true; notice(error.message + ' 本页输入没有被覆盖。', true);
      } else notice(error.message);
      if (error.status === 401) { state.user = null; updateAccount(); }
    } finally {
      state.busy = false; $('busy-status').hidden = true; $('main-content').removeAttribute('aria-busy'); controls();
    }
  }
  async function mutate(suffix, body, method = 'POST') {
    if (!state.session) throw new Error('请先新建或打开一条共创记录。');
    if (state.conflict) throw new Error('请先读取最新记录并核对，再提交修改。');
    return request('/sessions/' + state.session.id + suffix, {method, body:{revision:state.session.revision,...body}});
  }
  function updateAccount() {
    const link = $('account-link');
    link.textContent = state.user ? (state.user.username || state.user.name || '我的账号') + ' ↗' : '登录后保存共创记录 ↗';
    link.href = state.user ? '/profile.html' : '/login.html?next=' + encodeURIComponent(location.pathname + location.search);
  }
  function controls() {
    const locked = state.busy || state.conflict;
    const present = !!state.session;
    const validCandidates = generation()?.status === 'verified';
    document.querySelectorAll('[data-mode]').forEach(button => { button.disabled = state.busy; });
    $('scenario-select').disabled = state.busy;
    $('new-session').disabled = state.busy || !scenario();
    $('new-session').textContent = state.user ? '新建共创 →' : '登录并新建 →';
    ['save-example','generate-teaching','review-generate-teaching','save-review','run-review'].forEach(id => { $(id).disabled = locked || !present; });
    ['generate-ai','review-generate-ai'].forEach(id => { $(id).disabled = locked || !present || !state.ai; $(id).title = state.ai ? '' : '尚未配置 AI 接口，可明确选择教学样例'; });
    $('run-compare').disabled = locked || !present || !validCandidates;
    $('export-session').disabled = state.busy || !present;
    $('refresh-sessions').disabled = state.busy || !state.user;
    document.querySelectorAll('[data-edit-example],[data-delete-example],[data-select-candidate]').forEach(button => { button.disabled = locked || (button.hasAttribute('data-select-candidate') && button.dataset.verified !== 'true'); });
    document.querySelectorAll('[data-open-session]').forEach(button => { button.disabled = state.busy; });
    ['example-input','example-expected','review-code','review-input','review-prediction','review-reflection','compare-input'].forEach(id => { $(id).readOnly = state.busy || !present; });
    document.querySelectorAll('[name=judgment]').forEach(input => { input.disabled = state.busy || !present; });
    $('cancel-edit').disabled = locked;
    $('clarify-example').disabled = locked;
  }
  function renderScenario() {
    const item = scenario(); if (!item) return;
    $('scenario-description').textContent = item.description + ' 本轮规则范围：' + (item.rule_options || []).map(r => r.label).join(' / ') + '。';
    $('example-guide').textContent = (item.input_hint || '') + ' · 最多 12 个例子';
    $('review-rule').textContent = item.review_rule?.label || '';
    $('review-input-hint').textContent = item.input_hint || '';
    if (!state.session) { $('compare-input').value = json(item.probe); $('review-input').value = json(item.probe); }
  }
  function renderModes({preserveSession = false} = {}) {
    ['examples','review'].forEach(mode => {
      $('tab-' + mode).setAttribute('aria-selected', String(state.mode === mode));
      $('tab-' + mode).tabIndex = state.mode === mode ? 0 : -1;
      $(mode + '-panel').hidden = state.mode !== mode;
    });
    const url = new URL(location.href);
    url.searchParams.set('mode', state.mode);
    if (state.session) url.searchParams.set('session', state.session.id);
    else if (!preserveSession) url.searchParams.delete('session');
    history.replaceState(null,'',url);
    updateAccount();
  }
  function setSession(session, preserve = false) {
    const draft = preserve ? capture() : null;
    state.session = session; state.active[session.mode] = session; state.mode = session.mode; state.editing = null;
    $('scenario-select').value = session.scenario_id; state.currentCompare = null;
    renderModes(); renderScenario(); renderSession(); if (draft) restore(draft); renderSaved(); controls();
    const index = state.sessions.findIndex(s => s.id === session.id);
    if (index >= 0) state.sessions[index] = session; else state.sessions.unshift(session);
    state.sessions.sort((a,b) => String(b.updated_at).localeCompare(String(a.updated_at))); renderSaved();
  }
  function renderExamples() {
    const examples = state.session?.state.examples || [];
    $('example-count').textContent = examples.length + ' 个例子';
    $('example-list').innerHTML = examples.length ? examples.map((e,i) => `<div class="example-row"><span class="example-index">${String(i+1).padStart(2,'0')}</span><pre>${esc(compact(e.input))}</pre><span class="output-arrow" aria-hidden="true">→</span><pre>${esc(compact(e.expected))}</pre><div class="example-actions"><button type="button" data-edit-example="${esc(e.id)}" aria-label="编辑第 ${i+1} 个例子">编辑</button><button type="button" data-delete-example="${esc(e.id)}" aria-label="删除第 ${i+1} 个例子">删除</button></div></div>`).join('') : '<p class="empty-state">还没有例子。先写下输入和你期望的输出，再生成候选。</p>';
  }
  function renderCandidates() {
    const current = generation();
    const selected = state.session?.state.selected;
    $('generation-source').textContent = current ? (sources[current.source] || current.source) : '尚未生成';
    $('selection-result').hidden = !selected;
    $('selection-result').textContent = selected ? '已由你确认：' + selected.label + '。继续补充例子会重新开启规则探索。' : '';
    if (!current) {
      $('candidate-grid').innerHTML = '<div class="candidate-placeholder"><span class="placeholder-number">A</span><h3>等待第一个候选</h3><p>候选会按当前例子与规则探针真实检查。</p></div><div class="candidate-placeholder"><span class="placeholder-number">B</span><h3>等待另一个可能</h3><p>如果例子已经排除另一种规则，也可能只剩一个候选。</p></div>';
      return;
    }
    const candidates = current.candidates || [];
    $('candidate-grid').innerHTML = candidates.map((c,i) => `<article class="candidate-card ${selected?.candidate_id === c.id ? 'selected' : ''}"><div class="candidate-top"><span class="candidate-letter">${String.fromCharCode(65+i)}</span><div><h3>${esc(c.label)}</h3><p class="candidate-meta">${esc(sources[c.source] || c.source)}${c.model ? ' · ' + esc(c.model) : ''}</p></div></div><pre><code>${esc(c.code)}</code></pre><div class="candidate-bottom"><p class="candidate-meta">${esc(c.explanation || '')}</p><span class="verification-state ${c.verified ? '' : 'failed'}">${c.verified ? '已通过本轮' : '本轮检查未全部通过'} ${c.verification?.passed || 0} / ${c.verification?.total || 0} 项检查</span><details class="verification-details"><summary>查看验证依据</summary>${(c.verification?.cases || []).map(v => `<p class="run-note">${v.passed ? '通过' : '未通过'} · ${v.kind === 'rule_probe' ? '规则探针' : '已知例子'}<br>输入 ${esc(compact(v.input))}<br>期望 ${esc(compact(v.expected))}<br>实际 ${esc(compact(v.output))}${v.error ? '<br>' + esc(v.error) : ''}</p>`).join('')}</details><button type="button" class="button button-outline" data-select-candidate="${esc(c.id)}" data-verified="${c.verified && current.status === 'verified'}">${selected?.candidate_id === c.id ? '已确认这个规则 ✓' : '选择并确认这个规则 →'}</button></div></article>`).join('');
    if (!candidates.length) $('candidate-grid').innerHTML = '<div class="candidate-placeholder"><h3>' + (current.status === 'running' ? '服务器正在生成候选' : '本次没有生成可用候选') + '</h3><p>' + esc(current.error || '请稍后读取最新记录查看进度。') + '</p></div>';
    if (current.error) notice(current.error + ' 你的例子仍保留。');
    if (candidates.length === 1 && current.status === 'verified') $('candidate-grid').insertAdjacentHTML('beforeend','<div class="candidate-placeholder"><span class="placeholder-number">✓</span><h3>你的例子已经澄清分歧</h3><p>当前有限规则范围内，只剩一种行为符合这些例子。仍可使用新的输入检验它。</p></div>');
  }
  function renderCompare(run) {
    state.currentCompare = run || null; $('clarify-example').hidden = !run;
    if (!run) { $('compare-results').innerHTML = '<p class="empty-state compact">生成候选后，试试推荐输入，观察它们是否有不同表现。</p>'; return; }
    const current = generation();
    const verdict = run.results?.some(r => !r.success) ? '至少一个候选未成功执行，暂时无法判断分歧。' : run.different ? '发现行为分歧，下一步由你澄清。' : '本次输入的成功输出没有分歧。';
    $('compare-results').innerHTML = `<div class="run-header"><b class="run-verdict">${verdict}</b><span class="quiet-badge">隔离环境 · 实际执行</span></div><div class="result-grid">${(run.results || []).map((r,i) => { const candidate = current?.candidates.find(c => c.id === r.candidate_id); return `<div class="result-cell ${r.success ? '' : 'error'}"><h3>${String.fromCharCode(65+i)} · ${esc(candidate?.label || '候选结果')}</h3><pre>${esc(r.success ? json(r.output) : r.error || '运行失败')}</pre>${r.success ? `<button type="button" class="text-button" data-use-output="${i}">以此为期望，补充例子</button>` : ''}</div>`; }).join('')}</div><p class="run-note">输入：${esc(compact(run.input))}。来源与代码仍以当前候选卡片为准；运行结果不会替你选择规则。</p>`;
  }
  function renderReview() {
    const review = state.session?.state.review;
    $('review-code').value = review?.code || '';
    $('review-source').textContent = review ? (sources[review.source] || review.source) : '尚未载入';
    $('review-code-status').textContent = review ? '代码版本 ' + review.code_revision + ' · 不作整体正确性证明' : '待生成 · Python 3';
    $('review-prediction').value = review?.prediction_saved ? json(review.prediction) : '';
    $('review-reflection').value = review?.reflection || '';
    document.querySelectorAll('[name=judgment]').forEach(input => { input.checked = input.value === review?.judgment; });
    $('review-save-status').textContent = review?.judgment ? '判断已保存 · 代码版本 ' + review.code_revision : '先保存判断与预测，再查看运行结果。';
    const evidence = review?.evidence || [];
    renderReviewEvidence(evidence);
    if (review?.generation_error) notice(review.generation_error + ' 原代码与输入保留。');
  }
  function renderReviewEvidence(evidence) {
    const latest = evidence[evidence.length - 1];
    if (!latest) { $('review-results').innerHTML = '<p class="empty-state compact">先写下判断和预测，再真实运行。结果将与本次验收规则对照。</p>'; return; }
    const stale = latest.code_revision !== state.session.state.review.code_revision;
    const verdict = !latest.success ? '运行未成功，暂时无法比较输出。' : latest.passed ? '该输入没有找到反例，继续检验其他边界。' : '发现反例：实际输出与约定规则不一致。';
    $('review-results').innerHTML = `<div class="run-header"><b class="run-verdict ${latest.success && !latest.passed ? 'counterexample' : ''}">${esc(verdict)}</b><span class="quiet-badge">代码版本 ${esc(latest.code_revision)}${stale ? ' · 历史证据' : ''}</span></div><p class="run-note">本次输入 ${esc(compact(latest.input))}${stale ? '。代码已经变化，下面证据对应旧版本，请重新运行当前代码。' : ''}</p><div class="result-grid"><div class="result-cell"><h3>你的事先预测</h3><pre>${esc(json(latest.prediction))}</pre></div><div class="result-cell"><h3>约定规则的期望</h3><pre>${esc(json(latest.expected))}</pre></div><div class="result-cell ${latest.success ? '' : 'error'}"><h3>代码的实际结果</h3><pre>${esc(latest.success ? json(latest.actual) : latest.error || '运行失败')}</pre></div></div><p class="run-note">${latest.success ? (latest.prediction_matched ? '你的预测与实际输出一致。' : '你的预测与实际输出不同，可以回到代码检查原因。') : '请结合运行错误修订代码或测试输入。'} 完成后，把依据补进上方复盘，再保存。</p><details class="evidence-history"><summary>查看 ${evidence.length} 次质检记录</summary>${[...evidence].reverse().map(e => `<div class="history-row"><span>版本 ${esc(e.code_revision)} · ${e.success ? (e.passed ? '此例通过' : '找到反例') : '运行失败'}<br>${esc(compact(e.input))}</span><span>${esc(date(e.created_at))}</span></div>`).join('')}</details>`;
  }
  function renderSession() {
    const session = state.session;
    $('session-label').textContent = session ? modeNames[session.mode] + ' / ' + session.title : '先选择场景并新建共创';
    $('revision-label').textContent = session ? '已保存 · 记录版本 ' + session.revision : '记录会跟随你的账号保存';
    $('evidence-count').textContent = (session?.state.runs.length || 0) + ' 次运行';
    $('example-input').value = ''; $('example-expected').value = ''; $('cancel-edit').hidden = true;
    $('example-form-title').textContent = '补充一个例子';
    renderExamples(); renderCandidates(); renderReview();
    const runs = session?.state.runs || [];
    const lastCompare = [...runs].reverse().find(r => r.kind === 'compare' && r.generation_id === session?.state.current_generation_id);
    renderCompare(lastCompare);
    const item = scenario();
    const review = session?.state.review;
    $('compare-input').value = json(lastCompare ? lastCompare.input : item?.probe || []);
    $('review-input').value = json(review?.prediction_saved && Object.hasOwn(review, 'prediction_input') ? review.prediction_input : item?.probe || []);
  }
  function renderSaved() {
    const list = state.sessions.filter(s => s.mode === state.mode);
    $('session-list').innerHTML = state.user ? (list.length ? list.map(s => `<button class="saved-session" type="button" data-open-session="${esc(s.id)}" ${s.id === state.session?.id ? 'aria-current="true"' : ''}><b>${esc(s.title)}</b><small>${esc(modeNames[s.mode])} · ${esc(date(s.updated_at))} · 版本 ${esc(s.revision)}</small></button>`).join('') : '<p class="empty-state compact">还没有这类共创记录。选择场景，新建一次探索。</p>') : '<p class="empty-state compact">登录后，例子、选择与运行证据都会保存在这里。</p>';
  }
  async function loadSessions() {
    if (!state.user) { renderSaved(); return; }
    const data = await request('/sessions'); state.sessions = data.sessions || []; renderSaved(); controls();
  }
  function switchMode(mode) {
    if (state.busy || mode === state.mode) return;
    stash(); state.mode = mode; state.session = state.active[mode] || null; state.editing = null; state.conflict = false;
    if (state.session) $('scenario-select').value = state.session.scenario_id;
    renderModes(); renderScenario(); renderSession(); restore(state.drafts[draftKey()]); renderSaved(); notice(''); controls();
  }
  function populateExample(input, expected) {
    state.editing = null; $('example-form-title').textContent = '用这个例子澄清分歧'; $('cancel-edit').hidden = true;
    $('example-input').value = json(input); $('example-expected').value = expected === undefined ? '' : json(expected);
    $('example-form').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',block:'center'});
    $('example-expected').focus();
    toast('请确认这是你真正希望的结果，再保存例子并重新生成候选。');
  }
  async function saveReview() {
    const judgment = document.querySelector('[name=judgment]:checked')?.value;
    if (!judgment) throw new Error('请先选择接受、存疑或拒绝，写下你的初步判断。');
    const draft = capture();
    const data = await mutate('/review', {judgment, prediction:readJson('review-prediction','预测输出'), prediction_input:readJson('review-input','测试输入'), reflection:$('review-reflection').value, code:$('review-code').value});
    setSession(data.session); restore(draft); $('review-save-status').textContent = '判断与代码已保存 · 版本 ' + data.session.state.review.code_revision;
  }
  function bind() {
    document.querySelectorAll('[data-mode]').forEach(button => button.addEventListener('click', () => switchMode(button.dataset.mode)));
    document.querySelector('.mode-tabs').addEventListener('keydown', event => {
      if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
      event.preventDefault(); const mode = event.key === 'Home' ? 'examples' : event.key === 'End' ? 'review' : state.mode === 'examples' ? 'review' : 'examples';
      switchMode(mode); $('tab-' + mode).focus();
    });
    $('scenario-select').addEventListener('change', () => {
      if (state.session && state.session.scenario_id !== $('scenario-select').value) { stash(); state.session = null; state.editing = null; state.conflict = false; }
      renderModes(); renderScenario(); renderSession(); restore(state.drafts[draftKey()]); notice(''); controls();
    });
    $('new-session').addEventListener('click', () => {
      if (!state.user) { location.href = '/login.html?next=' + encodeURIComponent(location.pathname + location.search); return; }
      perform('正在新建共创…', async () => { stash(); const data = await request('/sessions', {method:'POST',body:{mode:state.mode,scenario_id:scenario()?.id}}); state.conflict = false; setSession(data.session); toast('共创已创建，起始资料已经保存。'); });
    });
    $('example-form').addEventListener('submit', event => {
      event.preventDefault(); perform('正在保存例子…', async () => {
        const example = {input:readJson('example-input','例子的输入'),expected:readJson('example-expected','期望输出')}; if (state.editing) example.id = state.editing;
        const probe = $('compare-input').value;
        const data = await mutate('', {action:'upsert_example',example}, 'PATCH'); setSession(data.session); $('compare-input').value = probe;
        toast('例子已保存，旧候选已失效。请重新生成并验证。');
      });
    });
    $('cancel-edit').addEventListener('click', () => { state.editing = null; $('example-input').value = ''; $('example-expected').value = ''; $('cancel-edit').hidden = true; $('example-form-title').textContent = '补充一个例子'; });
    $('example-list').addEventListener('click', event => {
      const edit = event.target.closest('[data-edit-example]'), remove = event.target.closest('[data-delete-example]');
      if (edit) {
        const item = state.session.state.examples.find(e => e.id === edit.dataset.editExample); if (!item) return;
        state.editing = item.id; $('example-input').value = json(item.input); $('example-expected').value = json(item.expected); $('cancel-edit').hidden = false; $('example-form-title').textContent = '编辑这个例子'; $('example-input').focus();
      }
      if (remove) perform('正在删除例子…', async () => { const draft = capture(); const data = await mutate('',{action:'delete_example',example_id:remove.dataset.deleteExample},'PATCH'); setSession(data.session); restore(draft); if (state.editing === remove.dataset.deleteExample) $('cancel-edit').click(); toast('例子已删除，请重新生成候选。'); });
    });
    [['generate-ai','ai'],['generate-teaching','teaching'],['review-generate-ai','ai'],['review-generate-teaching','teaching']].forEach(([id,source]) => $(id).addEventListener('click', () => perform(source === 'ai' ? '正在请求 AI 并准备候选，请稍候…' : '正在准备教学样例并检查执行环境…', async () => {
      const draft = capture(); const suffix = state.mode === 'review' ? '/review-generate' : '/generate';
      const data = await mutate(suffix,{source}); setSession(data.session);
      if (state.mode === 'examples') restore(draft); else { $('review-input').value = draft['review-input']; if (data.session.state.review.generation_error) restore(draft); }
      if (!generation()?.error && !data.session.state.review.generation_error) toast(source === 'ai' ? 'AI 请求已完成，请查看来源和验证状态。' : '已明确载入预置教学样例。');
    })));
    $('candidate-grid').addEventListener('click', event => {
      const button = event.target.closest('[data-select-candidate]'); if (!button) return;
      const current = generation(); if (!current) return;
      perform('正在确认你选择的规则…', async () => { const data = await mutate('/select',{generation_id:current.id,candidate_id:button.dataset.selectCandidate}); setSession(data.session,true); toast('规则已由你确认，选择依据与代码已经保存。'); });
    });
    $('compare-form').addEventListener('submit', event => { event.preventDefault(); perform('正在隔离环境中对比运行候选…', async () => {
      const draft = capture(); const input = readJson('compare-input','对比输入'); const data = await mutate('/compare',{input}); setSession(data.session); restore(draft); renderCompare(data.run); toast('真实对比已完成，运行证据已保存。');
    }); });
    $('clarify-example').addEventListener('click', () => { if (state.currentCompare) populateExample(state.currentCompare.input); });
    $('compare-results').addEventListener('click', event => { const button = event.target.closest('[data-use-output]'); if (button && state.currentCompare) populateExample(state.currentCompare.input,state.currentCompare.results[Number(button.dataset.useOutput)]?.output); });
    $('save-review').addEventListener('click', () => perform('正在保存你的判断…', async () => { await saveReview(); toast('判断、预测与复盘已保存。'); }));
    $('review-form').addEventListener('submit', event => { event.preventDefault(); perform('正在保存判断并进行真实质检…', async () => {
      const input = readJson('review-input','测试输入'); await saveReview(); const draft = capture(); const data = await mutate('/review-run',{input}); setSession(data.session); restore(draft); toast('质检已完成，请对照规则期望与实际输出。');
    }); });
    ['review-code','review-prediction','review-reflection'].forEach(id => $(id).addEventListener('input', () => { $('review-save-status').textContent = '本页有未保存内容 · 保存后再检验'; }));
    $('session-list').addEventListener('click', event => { const button = event.target.closest('[data-open-session]'); if (!button) return; perform('正在打开共创记录…', async () => { stash(); const data = await request('/sessions/' + button.dataset.openSession); state.conflict = false; setSession(data.session); restore(state.drafts[draftKey()]); toast('已打开保存的共创记录。'); }); });
    $('refresh-sessions').addEventListener('click', () => perform('正在刷新共创记录…', loadSessions));
    $('export-session').addEventListener('click', () => {
      if (!state.session) return;
      const artifact = {format:'codelab-co-create-evidence',version:1,exported_at:new Date().toISOString(),note:'本文件为服务器已保存记录；当前页面未保存输入不包含在内。真实运行证据不代表所有输入下的正确性。',session:state.session};
      const url = URL.createObjectURL(new Blob([json(artifact)],{type:'application/json;charset=utf-8'}));
      const link = document.createElement('a'); link.href = url; link.download = 'CodeLab-共创证据-' + state.session.scenario_id + '-' + state.session.id + '.json'; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url),1000); toast('已导出服务器保存的共创证据。');
    });
    const encouragements = ['你不需要一次想到所有边界。发现一个新问题，就是前进了一步。','你补充的每个例子，都在把“差不多”变成“我想要这样”。','先猜，再测，最后用证据修正判断。思考正在发生。','休息一下也可以。你的例子与运行记录已经随账号保存。'];
    const hints = ['试试重复值：同一个元素出现两次或三次，规则还成立吗？','试试边界：空数组、单个元素、刚好等于门槛，往往能揭示分歧。','改变输入顺序看看。相同元素、不同排列，可能带来不同结果。','先想一个能让两个候选输出不同的输入，再决定哪一个符合你的意图。'];
    let encouragementIndex = 0, hintIndex = 0;
    function petSpeak(message) { $('pet-message').textContent = message; $('companion-image').classList.add('is-happy'); setTimeout(() => $('companion-image').classList.remove('is-happy'),500); }
    $('pet-encourage').addEventListener('click', () => petSpeak(encouragements[encouragementIndex++ % encouragements.length]));
    $('pet-hint').addEventListener('click', () => petSpeak(hints[hintIndex++ % hints.length]));
  }
  async function init() {
    const requestedSession = new URLSearchParams(location.search).get('session');
    bind(); renderModes({preserveSession:true}); controls();
    $('review-reflection').maxLength = 2000;
    const results = await Promise.allSettled([request('/catalog'),request('/api/current_user')]);
    const catalogResult = results[0];
    if (catalogResult.status === 'fulfilled') {
      state.scenarios = catalogResult.value.scenarios || []; state.ai = !!catalogResult.value.ai_available;
      $('scenario-select').innerHTML = state.scenarios.map(s => `<option value="${esc(s.id)}">${esc(s.title)}</option>`).join('');
      $('ai-status').textContent = state.ai ? 'AI 已配置 · 生成时实时调用' : 'AI 未配置 · 可使用教学样例'; $('ai-status').classList.toggle('available',state.ai);
    } else { notice(catalogResult.reason.message); $('ai-status').textContent = '场景读取失败'; }
    if (results[1].status === 'fulfilled') state.user = results[1].value.user;
    updateAccount(); renderScenario(); renderSaved(); controls();
    if (state.user) try { await loadSessions(); } catch (error) { notice(error.message); }
    if (requestedSession && state.user && state.scenarios.length && new URLSearchParams(location.search).get('session') === requestedSession) {
      await perform('正在恢复上次打开的共创记录…', async () => {
        try {
          const data = await request('/sessions/' + encodeURIComponent(requestedSession));
          state.conflict = false; setSession(data.session);
          toast('已恢复上次打开的共创记录。');
        } catch (error) {
          state.session = null; renderModes();
          throw new Error('无法恢复这条共创记录：' + error.message + ' 请从历史记录中重新选择，或新建共创。');
        }
      });
    } else if (requestedSession && !state.user) notice('登录后即可恢复链接中的共创记录。');
  }
  init();
})();
