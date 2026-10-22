let practiceUser = null;
let chatHistory = [];
let chatBusy = false;
let chatProblemId = null;
let attachedPractice = null;
let chatAbortController = null;
let optimizeController = null;
let aiContextRevision = 0;
let chatContextRevision = 0;
document.addEventListener('DOMContentLoaded', function () {
    UserSession.init({ logoutRedirect: '/index.html' }).then(user => {
        practiceUser = user;
        visibleStudySeconds = 0;
        lastStudyTick = document.visibilityState === 'visible' ? Date.now() : null;
        window.dispatchEvent(new CustomEvent('practice:user', {detail: user}));
        problemListCache = null;
        updateProblemNavigationState();
    });
    const backParams = new URLSearchParams(location.search);backParams.delete('problem');
    document.getElementById('backProblemList').href = '/problem_selector.html'+(backParams.size?'?'+backParams:'');
    loadProblem();


});

function getCurrentProblemId() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('problem');
}

let problemListCache = null;
function libraryFilter() {
    const source=new URLSearchParams(location.search),result=new URLSearchParams();
    for(const key of ['q','category','difficulty','state'])if(source.get(key))result.set(key,source.get(key));
    return result;
}
function practiceListURL(id) {
    const params=new URLSearchParams(location.search);params.set('problem',id);return '/practice.html?'+params;
}

async function getProblemList() {
    if (problemListCache) {
        return problemListCache;
    }
    const filter=libraryFilter();let snapshot=null;
    try {
        const saved=JSON.parse(sessionStorage.getItem('codelab:problem-list')||'null');
        if(saved?.filter===filter.toString()&&saved.owner===(practiceUser?.id||null)&&saved.ids.includes(getCurrentProblemId()))snapshot=saved;
    } catch(_){/* Fall back to the filters retained in the URL. */}
    const response = await fetch('/api/problems'+(snapshot?'':'?'+filter));
    const result = await response.json();
    if (!result.success || !result.problems) {
        return [];
    }
    problemListCache = snapshot ? snapshot.ids.map(id=>result.problems.find(p=>p.id===id)).filter(Boolean) : result.problems;
    return problemListCache;
}

async function updateProblemNavigationState() {
    if (!nextProblemBtn || !prevProblemBtn) {
        return;
    }
    try {
        const currentId = getCurrentProblemId();
        if (!currentId) {
            nextProblemBtn.classList.add('is-disabled');
            prevProblemBtn.classList.add('is-disabled');
            return;
        }
        const problems = await getProblemList();
        const order = problems.map((p) => p.id);
        const currentIndex = order.indexOf(currentId);
        const currentProblem = problems[currentIndex];
        const hasPrev = currentIndex > 0;
        const hasNext = currentIndex >= 0 && currentIndex + 1 < order.length;
        prevProblemBtn.classList.toggle('is-disabled', !hasPrev);
        prevProblemBtn.title = hasPrev ? '' : '已是第一题';
        nextProblemBtn.classList.toggle('is-disabled', !hasNext);
        nextProblemBtn.title = hasNext ? '' : '已是最后一题';

        if (problemProgress) {
            problemProgress.textContent = currentIndex >= 0
                ? `题目 ${currentIndex + 1}/${order.length}`
                : '题目 -/-';
        }
        if (problemPassedBadge) {
            problemPassedBadge.hidden = !(currentProblem && currentProblem.accepted);
        }
    } catch (error) {
        nextProblemBtn.classList.add('is-disabled');
        prevProblemBtn.classList.add('is-disabled');
        nextProblemBtn.title = '已是最后一题';
        prevProblemBtn.title = '已是第一题';
    }
}

async function loadProblem() {
    const problemId = getCurrentProblemId();
    const problemTitleEl = document.querySelector('.problem-title');
    const problemContentEl = document.querySelector('.problem-content');

    if (!problemId) {
        problemTitleEl.textContent = '无效的题目';
        problemContentEl.innerHTML = '<h2>请先通过题目列表选择一个题目</h2>';
        return;
    }

    try {
        const response = await fetch(`/api/problems/${problemId}`);
        const result = await response.json();

        if (result.success && result.problem) {
            const problem = result.problem;
            let difficultyClass = 'difficulty-easy';
            if (problem.difficulty && problem.difficulty.toLowerCase().includes('中等')) {
                difficultyClass = 'difficulty-medium';
            } else if (problem.difficulty && problem.difficulty.toLowerCase().includes('困难')) {
                difficultyClass = 'difficulty-hard';
            }

            problemTitleEl.innerHTML = `
                <span>${escapeHtml(problem.title || '无标题')}</span>
                <div class="problem-meta">
                    <span class="problem-difficulty ${difficultyClass}">${escapeHtml(problem.difficulty || '未知')}</span>
                </div>
            `;
            problemContentEl.innerHTML = problem.description || '<p>该题目没有描述信息。</p>';
            document.getElementById('problemKnowledge').textContent = [problem.category_name,...(problem.tags||[])].filter(Boolean).join(' · ');
            window.dispatchEvent(new CustomEvent('practice:problem', {detail: problem}));
        } else {
            problemTitleEl.textContent = '加载失败';
            problemContentEl.innerHTML = `<p>无法加载题目详情，错误：${escapeHtml(apiErrorMessage(result, '未知错误'))}</p>`;
        }

    } catch (error) {
        console.error('加载题目失败:', error);
        problemTitleEl.textContent = '加载失败';
        problemContentEl.innerHTML = `<p>请求题目数据时发生网络错误: ${escapeHtml(error.message)}</p>`;
    }
    await updateProblemNavigationState();
}

// DOM元素
const codeInput = document.getElementById('codeInput');
const outputContent = document.getElementById('outputContent');
const aiSuggestion = document.getElementById('aiSuggestion');
const runBtn = document.getElementById('runBtn');
const optimizeBtn = document.getElementById('optimizeBtn');
const submitBtn = document.getElementById('submitBtn');
const nextProblemBtn = document.getElementById('nextProblemBtn');
const prevProblemBtn = document.getElementById('prevProblemBtn');
const problemProgress = document.getElementById('problemProgress');
const problemPassedBadge = document.getElementById('problemPassedBadge');
const chatContainer = document.getElementById('chatContainer');
const messageInput = document.getElementById('messageInput');
const sendMessageBtn = document.getElementById('sendMessage');
const ghostLayer = document.getElementById('ghostLayer');
const inlineHint = document.getElementById('inlineHint');

let inlineSuggestion = '';
let inlineSuggestionContext = null;
let inlineAbortController = null;
let inlineRequestId = 0;
let inlineDebounceTimer = null;
let inlineComposing = false;
let inlineActiveContext = null;
let inlineRetryAfter = 0;
const inlineCompletionCache = new Map();

function getCursorContext() {
    const text = codeInput.value || '';
    const start = codeInput.selectionStart || 0;
    const end = codeInput.selectionEnd || start;
    const rawPrefix = text.slice(0, start);
    const rawSuffix = text.slice(end);
    const prefix = rawPrefix.slice(-2000);
    const suffix = rawSuffix.slice(0, 800);
    return { prefix, suffix, start, end };
}

function renderGhostLayer() {
    if (!ghostLayer || !codeInput) {
        return;
    }
    const text = codeInput.value || '';
    const start = codeInput.selectionStart || 0;
    const end = codeInput.selectionEnd || start;
    const prefix = text.slice(0, start);
    const ghost = start === end ? inlineSuggestion : '';
    // Never re-render or shift actual code: native text, selection and hit testing stay together.
    // Mid-code completions use a separate preview so they cannot cover the existing suffix.
    const atEnd = start === text.length;
    ghostLayer.style.width = `${codeInput.clientWidth}px`;
    ghostLayer.style.height = `${codeInput.clientHeight}px`;
    ghostLayer.innerHTML = `<span class="typed">${escapeHtml(prefix)}</span><span class="ghost">${escapeHtml(atEnd ? ghost : '')}</span>`;
    ghostLayer.scrollTop = codeInput.scrollTop;
    ghostLayer.scrollLeft = codeInput.scrollLeft;
    if (inlineHint) {
        inlineHint.innerHTML = 'Tab 接受 / Esc 取消' + (ghost && !atEnd
            ? `<pre class="completion-preview">${escapeHtml(ghost)}</pre>` : '');
        inlineHint.classList.toggle('is-visible', ghost.length > 0);
    }
}

function clearInlineSuggestion() {
    inlineSuggestion = '';
    inlineSuggestionContext = null;
    renderGhostLayer();
}

function cancelInlineCompletion() {
    clearTimeout(inlineDebounceTimer);
    inlineDebounceTimer = null;
    inlineRequestId += 1;
    inlineAbortController?.abort();
    inlineAbortController = null;
    inlineActiveContext = null;
    clearInlineSuggestion();
}

function scheduleInlineCompletion(force = false) {
    clearTimeout(inlineDebounceTimer);
    if (window.PracticeTransfer?.blocksAI) { cancelInlineCompletion(); return; }
    if (!LearningHelpUI.get().ready || LearningHelpUI.get().mode !== 'free' || !codeInput || !practiceUser || inlineComposing || document.activeElement !== codeInput
        || Date.now() < inlineRetryAfter) return;
    const requestId = ++inlineRequestId;
    if (force) requestInlineCompletion(requestId);
    else inlineDebounceTimer = setTimeout(() => requestInlineCompletion(requestId), 120);
}

async function requestInlineCompletion(requestId) {
    if (window.PracticeTransfer?.blocksAI) { cancelInlineCompletion(); return; }
    if (!LearningHelpUI.get().ready || LearningHelpUI.get().mode !== 'free' || !practiceUser || inlineComposing || document.activeElement !== codeInput) return;
    const { prefix, suffix, start, end } = getCursorContext();
    if (start !== end || prefix.trim().length < 3) { clearInlineSuggestion(); return; }
    inlineAbortController?.abort();
    const requestController = new AbortController();
    inlineAbortController = requestController;
    const language = document.getElementById('languageSelector').value || 'python';
    const code = codeInput.value;
    inlineActiveContext = {code, start, language};
    const cacheKey = JSON.stringify([language, prefix, suffix]);
    const isCurrent = () => !requestController.signal.aborted && requestId === inlineRequestId
        && !window.PracticeTransfer?.blocksAI
        && codeInput.value === code && codeInput.selectionStart === start && codeInput.selectionEnd === end
        && document.getElementById('languageSelector').value === language
        && document.activeElement === codeInput && !inlineComposing && !!practiceUser
        && LearningHelpUI.get().ready && LearningHelpUI.get().mode === 'free';
    const show = text => {
        if (!isCurrent()) return;
        inlineSuggestion = text;
        inlineSuggestionContext = {code, start, language};
        renderGhostLayer();
    };
    const cached = inlineCompletionCache.get(cacheKey);
    if (cached && Date.now() - cached.at < 120000) {
        show(cached.text);
        inlineAbortController = null;
        return;
    }
    const deadline = setTimeout(() => requestController.abort(), 15000);
    try {
        const response = await UserSession.csrfFetch('/api/ai-inline-complete-stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({language, prefix, suffix, max_tokens: 96}),
            signal: requestController.signal
        });
        if (!isCurrent()) { requestController.abort(); return; }
        if (!response.ok || !response.body) {
            if (response.status === 429) inlineRetryAfter = Date.now() + 10000;
            clearInlineSuggestion();
            return;
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';
        while (true) {
            const { value, done } = await reader.read();
            if (!isCurrent()) { requestController.abort(); return; }
            if (done) { buffer += decoder.decode(); break; }
            buffer += decoder.decode(value, { stream: true });
            show(buffer);
        }
        show(buffer);
        if (buffer) {
            LearningHelpUI.acknowledge(response.headers.get('X-Help-Id'));
            inlineCompletionCache.delete(cacheKey);
            inlineCompletionCache.set(cacheKey, {text: buffer, at: Date.now()});
            if (inlineCompletionCache.size > 24) inlineCompletionCache.delete(inlineCompletionCache.keys().next().value);
        }
    } catch (_) {
        if (requestId === inlineRequestId) clearInlineSuggestion();
    } finally {
        clearTimeout(deadline);
        if (inlineAbortController === requestController) inlineAbortController = null;
    }
}

function acceptInlineSuggestion() {
    if (window.PracticeTransfer?.blocksAI) { cancelInlineCompletion(); return; }
    if (!LearningHelpUI.get().ready || LearningHelpUI.get().mode !== 'free') { cancelInlineCompletion(); return; }
    if (!inlineSuggestion) {
        return;
    }
    const text = codeInput.value || '';
    const start = codeInput.selectionStart || 0;
    const end = codeInput.selectionEnd || start;
    if (!inlineSuggestionContext || inlineSuggestionContext.code !== text
        || inlineSuggestionContext.start !== start || start !== end
        || inlineSuggestionContext.language !== document.getElementById('languageSelector').value) {
        clearInlineSuggestion();
        return;
    }
    codeInput.value = text.slice(0, start) + inlineSuggestion + text.slice(end);
    const newPos = start + inlineSuggestion.length;
    codeInput.setSelectionRange(newPos, newPos);
    clearInlineSuggestion();
    codeInput.dispatchEvent(new Event('input'));
}

if (codeInput) {
    codeInput.addEventListener('input', () => {
        cancelInlineCompletion();
        scheduleInlineCompletion();
    });
    codeInput.addEventListener('compositionstart', () => { inlineComposing = true; cancelInlineCompletion(); });
    codeInput.addEventListener('compositionend', () => { inlineComposing = false; scheduleInlineCompletion(); });
    codeInput.addEventListener('blur', cancelInlineCompletion);
    document.getElementById('languageSelector').addEventListener('change', cancelInlineCompletion);
    window.addEventListener('auth:required', () => {
        practiceUser = null;
        cancelInlineCompletion();
        inlineCompletionCache.clear();
    });
    codeInput.addEventListener('keydown', e => {
        if (e.isComposing || inlineComposing) return;
        if (e.key === 'Tab' && inlineSuggestion) {
            e.preventDefault();
            acceptInlineSuggestion();
        } else if (e.key === 'Escape') {
            e.preventDefault();
            cancelInlineCompletion();
        } else if (e.ctrlKey && e.key === ' ') {
            e.preventDefault();
            cancelInlineCompletion();
            scheduleInlineCompletion(true);
        }
    });
    const handleCursorMove = () => {
        if (inlineActiveContext && (codeInput.selectionStart !== inlineActiveContext.start
            || codeInput.selectionEnd !== inlineActiveContext.start)) cancelInlineCompletion();
        renderGhostLayer();
    };
    codeInput.addEventListener('click', handleCursorMove);
    codeInput.addEventListener('keyup', handleCursorMove);
    codeInput.addEventListener('select', handleCursorMove);
    codeInput.addEventListener('scroll', () => {
        if (!ghostLayer) return;
        ghostLayer.scrollTop = codeInput.scrollTop;
        ghostLayer.scrollLeft = codeInput.scrollLeft;
    });
    if (typeof ResizeObserver !== 'undefined') new ResizeObserver(renderGhostLayer).observe(codeInput);
    renderGhostLayer();
}

async function goToRelativeProblem(offset) {
    const currentId = getCurrentProblemId();
    if (!currentId) {
        return;
    }
    const problems = await getProblemList();
    const order = problems.map((p) => p.id);
    const currentIndex = order.indexOf(currentId);
    const targetId = currentIndex >= 0 ? order[currentIndex + offset] : null;
    if (!targetId) {
        return;
    }
    window.location.href = practiceListURL(targetId);
}

if (prevProblemBtn) {
    prevProblemBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        if (prevProblemBtn.classList.contains('is-disabled')) {
            return;
        }
        try {
            await goToRelativeProblem(-1);
        } catch (error) {
            console.error('获取上一题失败:', error);
        }
    });
}

if (nextProblemBtn) {
    nextProblemBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        if (nextProblemBtn.classList.contains('is-disabled')) {
            return;
        }
        try {
            await goToRelativeProblem(1);
        } catch (error) {
            console.error('获取下一题失败:', error);
        }
    });
}
const aiFloatingWindow = document.getElementById('aiFloatingWindow');
const aiToggleBtn = document.getElementById('aiToggleBtn');

let globalOptimizedVersions = [];
let optimizationBase = null;

function escapeHtml(text) {
    var map = {
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
    };
    return String(text || '').replace(/[&<>"']/g, function (m) { return map[m]; });
}

function apiErrorMessage(result, fallback = '请求失败') {
    if (window.UserSession && typeof UserSession.apiErrorMessage === 'function') {
        return UserSession.apiErrorMessage(result, fallback);
    }
    if (!result) return fallback;
    if (typeof result.error === 'string') return result.error;
    if (result.error && result.error.message) return result.error.message;
    if (result.message) return result.message;
    return fallback;
}

let visibleStudySeconds = 0;
let lastStudyTick = document.visibilityState === 'visible' ? Date.now() : null;

function collectVisibleStudySeconds() {
    if (document.visibilityState !== 'visible' || lastStudyTick === null) {
        return;
    }
    const now = Date.now();
    visibleStudySeconds += Math.floor((now - lastStudyTick) / 1000);
    lastStudyTick = now;
}

function reportStudyTime(keepalive = false) {
    if (!practiceUser) {
        visibleStudySeconds = 0;
        lastStudyTick = document.visibilityState === 'visible' ? Date.now() : null;
        return;
    }
    collectVisibleStudySeconds();
    const duration = visibleStudySeconds;
    if (duration < 10) {
        return;
    }
    visibleStudySeconds = 0;
    UserSession.csrfFetch('/api/update_learning_time', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ duration }),
        keepalive
    }).catch(error => {
        if (error.code === 'AUTH_REQUIRED') practiceUser = null;
        else visibleStudySeconds += duration;
    });
}

document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
        lastStudyTick = Date.now();
        return;
    }
    reportStudyTime(true);
    lastStudyTick = null;
});

setInterval(() => reportStudyTime(false), 60000);
window.addEventListener('beforeunload', () => reportStudyTime(true));

function formatAiResponse(text) {
    return SafeContent.markdown(text);
}

function applyOptimizedCode(versionIndex) {
    if (!optimizationBase || codeInput.value !== optimizationBase.code || document.getElementById('languageSelector').value !== optimizationBase.language) {
        aiSuggestion.textContent = '代码或语言已改变，请重新生成建议，避免覆盖当前修改。';
        return;
    }
    if (versionIndex >= 0 && versionIndex < globalOptimizedVersions.length) {
        codeInput.value = globalOptimizedVersions[versionIndex].code;
        codeInput.dispatchEvent(new Event('input'));
        renderGhostLayer();
        aiSuggestion.innerHTML = `<div style="color:var(--success); text-align:center; padding:20px;"><i class="fas fa-check-circle"></i> 代码已应用！请检查代码编辑器。</div>`;
    } else {
        console.error("Error: Invalid version index provided:", versionIndex);
        aiSuggestion.innerHTML = `<div style="color:var(--warning); text-align:center; padding:20px;"><i class="fas fa-exclamation-triangle"></i> 应用优化代码失败：无效的版本。</div>`;
    }
}

async function runCode() {
    const code = codeInput.value;
    const customInput = document.getElementById('customInput').value;
    const language = document.getElementById('languageSelector').value;
    outputContent.innerHTML = '<p style="color: var(--accent)">执行中...</p>';
    runBtn.disabled = true;
    runBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 运行中';

    try {
        const response = await UserSession.csrfFetch('/api/run-code', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code, language, input_text: customInput })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(apiErrorMessage(errorData, `服务器返回错误: ${response.status} ${response.statusText}`));
        }

        const result = await response.json();
        const safeOutput = escapeHtml(result.output || '无输出内容');
        const safeError = escapeHtml(result.error || '未知错误');
        const safeStderr = escapeHtml(result.stderr || '');
        const outputTruncatedNotice = result.output_truncated
            ? '<div style="color:var(--warning); margin:8px 0;"><i class="fas fa-scissors"></i> 输出超过系统限制，已截断展示。</div>'
            : '';
        const errorTruncatedNotice = result.error_truncated
            ? '<div style="color:var(--warning); margin:8px 0;"><i class="fas fa-scissors"></i> 错误输出超过系统限制，已截断展示。</div>'
            : '';
        if (result.success) {
            outputContent.innerHTML = `<div style="margin-bottom:8px; color:var(--success)"><i class="fas fa-check-circle"></i> 执行成功 (${result.time}ms)</div>${outputTruncatedNotice}<pre style="background:rgba(76,201,240,0.1); padding:12px; border-radius:6px;">${safeOutput}</pre>`;
        } else {
            outputContent.innerHTML = `<div style="margin-bottom:8px; color:var(--warning)"><i class="fas fa-times-circle"></i> 执行失败 (${result.time}ms)</div><div style="color:var(--warning); margin-bottom:8px;">${escapeHtml(language)}环境错误:</div>${errorTruncatedNotice}<pre style="background:rgba(247,37,133,0.1); padding:12px; border-radius:6px;">${safeError}</pre>${safeStderr ? `<pre style="background:rgba(247,37,133,0.1); padding:12px; border-radius:6px; margin-top:8px;">${safeStderr}</pre>` : ''}`;
        }
    } catch (error) {
        if (UserSession.handleAuthError(error, outputContent, '请先登录后再运行代码。')) return;
        console.error('代码执行错误:', error);
        outputContent.innerHTML = `<div style="margin-bottom:8px; color:var(--warning)"><i class="fas fa-exclamation-triangle"></i> 请求失败</div><pre style="background:rgba(247,37,133,0.1); padding:12px; border-radius:6px;">${escapeHtml(error.message)}</pre>${!navigator.onLine ? '<p style="color:var(--warning)">检测到网络离线</p>' : ''}<p style="color:var(--light-gray); margin-top:10px;">提示: 请确保已安装${escapeHtml(language)}运行环境并配置正确</p>`;
    } finally {
        runBtn.disabled = false;
        runBtn.innerHTML = '<i class="fas fa-play"></i> 运行代码';
        outputContent.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

// 优化代码
async function optimizeCode() {
    if (window.PracticeTransfer?.blocksAI) { window.PracticeTransfer.notifyBlocked?.(); return; }
    const help = LearningHelpUI.get();
    const contextRevision = aiContextRevision;
    document.getElementById('optimizationResult').hidden = false;
    const code = document.getElementById('codeInput').value;
    const requestedLanguage = document.getElementById('languageSelector').value;
    const aiSuggestion = document.getElementById('aiSuggestion');

    if (!code.trim()) {
        aiSuggestion.innerHTML = '<span style="color:var(--warning)">请输入需要优化的代码</span>';
        return;
    }

    const optimizeBtn = document.getElementById('optimizeBtn');
    optimizeBtn.disabled = true;
    optimizeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 优化中';

    aiSuggestion.innerHTML = `
        <div style="display:flex; align-items:center; gap:8px; color:var(--accent)">
            <i class="fas fa-spinner fa-spin"></i>
            <span>正在使用AI优化代码...</span>
        </div>
    `;

    const requestController = new AbortController();
    optimizeController = requestController;
    const timeout = setTimeout(() => requestController.abort(), 70000);
    try {
        if (practiceUser && !help.ready) throw new Error('帮助设置尚未就绪，请刷新页面重试。');
        const response = await UserSession.csrfFetch('/api/optimize-code', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({ code, language: requestedLanguage, help_level: help.level }),
            signal: requestController.signal
        });

        const result = await response.json();
        if ((help.epoch !== LearningHelpUI.get().epoch || contextRevision !== aiContextRevision)) return;
        if (!response.ok) throw new Error(apiErrorMessage(result));
        if (result.success && result.learning_help) {
            globalOptimizedVersions = [];
            optimizationBase = {code, language: requestedLanguage};
            aiSuggestion.replaceChildren();
            const label = document.createElement('p');
            label.textContent = LearningHelpUI.labels[result.learning_help.level];
            label.className = 'hypothesis-tag';
            aiSuggestion.append(label);
            LearningHelpUI.render(result.learning_help, aiSuggestion);
            LearningHelpUI.acknowledge(result.learning_help.id);
            showOptimizationStale();
        } else if (result.success) {
            LearningHelpUI.acknowledge(result.help_id);
            // 将获取到的优化版本存储到全局变量
            optimizationBase = {code, language: requestedLanguage};
            globalOptimizedVersions = result.optimizedVersions; // <--- 关键：保存到全局变量

            let versionsHtml = '';
            if (globalOptimizedVersions && globalOptimizedVersions.length > 0) {
                versionsHtml = globalOptimizedVersions.map((version, index) => `
                    <div class="optimized-version-card" style="margin-bottom:15px; border:1px solid var(--light-gray); padding:10px; border-radius:8px; background-color: var(--darker);">
                        <div style="font-weight:600; margin-bottom:5px; color:var(--accent);">
                            ${escapeHtml(version.description || `优化版本 ${index + 1}`)}
                        </div>
                        <div class="code-block" style="margin-bottom:10px; font-size:0.9rem; max-height: 200px; overflow-y: auto; background-color: var(--dark); padding: 8px; border-radius: 4px;">
                            <pre style="margin:0; white-space: pre-wrap; word-break: break-all;">${escapeHtml(version.code)}</pre>
                        </div>
                        <button class="btn btn-run btn-sm" style="width:100%; background-color: var(--primary);"
                            onclick="applyOptimizedCode(${index})"> <i class="fas fa-check-square"></i> 应用此版本
                        </button>
                    </div>
                `).join('');
            } else {
                versionsHtml = `<p>本次没有提供需要应用的代码修改，请查看上方分析。</p>`;
            }

            aiSuggestion.innerHTML = `
                <div style="color:var(--success)">
                    <i class="fas fa-check-circle"></i> 优化完成！
                </div>
                <div style="margin: 10px 0; font-weight:500"></div>
                <div style="margin-bottom:10px; padding:8px; background:rgba(76,201,240,0.1); border-radius:6px;">
                    ${formatAiResponse(result.feedback) || '建议已生成，尚未运行验证'} </div>
                <div style="margin: 10px 0; font-weight:500">优化版本选择：</div>
                ${versionsHtml}
            `;
        } else {
            aiSuggestion.innerHTML = `<div style="color:var(--warning)"><i class="fas fa-exclamation-triangle"></i> AI优化失败: ${escapeHtml(apiErrorMessage(result))}</div>`;
        }
    } catch (error) {
        if ((help.epoch !== LearningHelpUI.get().epoch || contextRevision !== aiContextRevision)) return;
        if (UserSession.handleAuthError(error, aiSuggestion, '请先登录后再使用 AI 优化。')) return;
        aiSuggestion.innerHTML = `<div style="color:var(--warning)"><i class="fas fa-exclamation-triangle"></i> 请求失败: ${escapeHtml(error.message)}</div>`;
        console.error('优化代码请求错误:', error);
    } finally {
        clearTimeout(timeout);
        if (optimizeController === requestController) optimizeController = null;
        optimizeBtn.disabled = false;
        optimizeBtn.innerHTML = '<i class="fas fa-cogs"></i> AI优化';
    }
}

let submissionAttempt = null;
async function submitCode() {
    const code = codeInput.value;
    const language = document.getElementById('languageSelector').value;
    const urlParams = new URLSearchParams(window.location.search);
    const problemId = urlParams.get('problem');

    if (!code.trim()) {
        outputContent.innerHTML = '<p style="color: var(--warning)">请先输入代码</p>';
        return;
    }

    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 提交中';
    outputContent.innerHTML = `<div style="display:flex; align-items:center; gap:10px;"><i class="fas fa-spinner fa-spin" style="color:var(--accent)"></i><span>正在提交代码并检查...</span></div>`;

    try {
        const context = window.PracticeReview?.submissionContext() || {};
        const signature = JSON.stringify({code,language,problem_id:problemId,proposal_id:context.proposal_id});
        if (submissionAttempt?.signature !== signature) submissionAttempt = {signature, body:{code,language,problem_id:problemId,...context,operation_id:crypto.randomUUID()}};
        const response = await UserSession.csrfFetch('/api/check-solution', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(submissionAttempt.body)
        });
        const result = await response.json();
        if (result.error?.code === 'PRACTICE_CONFLICT') {
            submissionAttempt = null;
            window.PracticeReview?.refresh();
        }
        if (result.success && result.submission_id) {
            submissionAttempt = null;
            window.dispatchEvent(new CustomEvent('practice:submission', {detail: result.data}));
        }
        const safeDetails = escapeHtml(result.details || apiErrorMessage(result, '没有返回详细信息。'));
        const safeStatus = escapeHtml(result.status || '提交失败');

        if (result.success && result.status === "Accepted") {
            outputContent.innerHTML = `<div class="ai-response" style="border-left-color: var(--success);"><h4 style="color: var(--success); display: flex; align-items: center; gap: 8px;"><i class="fas fa-check-circle"></i><span>${safeStatus}</span></h4><pre style="white-space: pre-wrap;">${safeDetails || '通过！'}</pre></div>`;
            if (problemPassedBadge) {
                problemPassedBadge.hidden = false;
            }
            if (problemListCache) {
                const currentProblem = problemListCache.find((problem) => problem.id === problemId);
                if (currentProblem) {
                    currentProblem.accepted = true;
                }
            }
        } else {
            outputContent.innerHTML = `<div class="ai-response" style="border-left-color: var(--danger);"><h4 style="color: var(--danger); display: flex; align-items: center; gap: 8px;"><i class="fas fa-times-circle"></i><span>${safeStatus}</span></h4><pre style="white-space: pre-wrap;">${safeDetails}</pre></div>`;
        }
        if (result.success && result.submission_id) outputContent.replaceChildren();
    } catch (error) {
        if (UserSession.handleAuthError(error, outputContent, '请先登录后再提交代码。')) return;
        outputContent.innerHTML = `<div style="margin-bottom:8px; color:var(--warning)"><i class="fas fa-exclamation-triangle"></i> 请求失败</div><pre style="background:rgba(247,37,133,0.1); padding:12px; border-radius:6px;">${escapeHtml(error.message)}</pre>`;
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fas fa-paper-plane"></i> 提交解答';
        outputContent.parentElement.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

function addChatMessage(content, sender, id = null, isHtml = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    const image = document.createElement('img');
    image.src = sender === 'ai' ? aiFloatingWindow.dataset.avatar
        : (practiceUser?.avatar_url || UserSession.defaultAvatar);
    image.alt = sender === 'ai' ? '达菲郁头像' : '你的头像';
    image.draggable = false;
    image.addEventListener('error', () => { image.src = UserSession.defaultAvatar; }, {once: true});
    avatar.appendChild(image);
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    const header = document.createElement('div');
    header.className = 'message-header';
    header.textContent = sender === 'ai' ? '达菲郁' : (practiceUser?.display_name || practiceUser?.username || '你');
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    if (id) contentDiv.id = id;
    if (sender === 'ai') contentDiv.innerHTML = isHtml ? content : formatAiResponse(content);
    else contentDiv.textContent = content;
    bubble.append(header, contentDiv);
    messageDiv.append(avatar, bubble);
    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return contentDiv;
}

function updateChatContext() {
    const button = document.getElementById('attachPracticeContext');
    button.setAttribute('aria-pressed', String(!!attachedPractice));
    button.textContent = attachedPractice ? '取消附带' : '附带当前练习';
    document.getElementById('chatContextStatus').textContent = attachedPractice ? '下一条消息附带题目、代码和提交结果' : '';
}
document.getElementById('attachPracticeContext').addEventListener('click', () => {
    if (chatBusy) return;
    attachedPractice = attachedPractice ? null : {
        problem_id: getCurrentProblemId(), code: codeInput.value,
        input_text: document.getElementById('customInput').value,
        language: document.getElementById('languageSelector').value,
        title: document.querySelector('.problem-title').textContent
    };
    updateChatContext();
});

async function sendMessage() {
    if (window.PracticeTransfer?.blocksAI) { window.PracticeTransfer.notifyBlocked?.(); return; }
    if (chatBusy) return;
    const contextRevision = chatContextRevision;
    const message = messageInput.value.trim();
    if (!message) return;
    const problemId = getCurrentProblemId();
    if (chatProblemId !== problemId) {
        chatHistory = [];
        chatContainer.replaceChildren();
        chatProblemId = problemId;
    }
    chatBusy = true;
    window.DafeiyuPet?.setActivity('think');
    const attachment = attachedPractice;

    addChatMessage(message + (attachment ? '\n已附带：' + attachment.title + '（代码快照与最近提交）' : ''), 'user');
    messageInput.value = '';

    const aiContentDiv = addChatMessage('', 'ai');
    const reasoningPanel = document.createElement('details');
    reasoningPanel.className = 'reasoning-panel';
    reasoningPanel.hidden = true;
    reasoningPanel.open = true;
    const summary = document.createElement('summary');
    summary.textContent = '正在思考…';
    const reasoningText = document.createElement('div');
    reasoningText.className = 'reasoning-text';
    reasoningPanel.append(summary, reasoningText);
    const answer = document.createElement('div');
    const status = document.createElement('p');
    status.className = 'chat-stream-status';
    status.setAttribute('role', 'status');
    status.textContent = '达菲郁正在思考…';
    aiContentDiv.append(reasoningPanel, answer, status);
    const stopButton = document.getElementById('stopChat');
    stopButton.hidden = false;
    sendMessageBtn.disabled = true;
    chatAbortController = new AbortController();
    let fullText = '';
    let renderTimer = null;
    const renderAnswer = () => {
        clearTimeout(renderTimer); renderTimer = null;
        const follow = chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight < 80;
        answer.innerHTML = formatAiResponse(fullText);
        if (follow) chatContainer.scrollTop = chatContainer.scrollHeight;
    };
    let reasoning = '';
    let failed = false;
    let finished = false;
    let reasoningFinished = false;
    let userToggledReasoning = false;
    let reasoningStarted = null;
    summary.addEventListener('click', () => { userToggledReasoning = true; });
    const finishReasoning = () => {
        if (!reasoning || reasoningFinished) return;
        reasoningFinished = true;
        const seconds = Math.max(1, Math.round((Date.now() - reasoningStarted) / 1000));
        summary.textContent = `已思考 ${seconds} 秒`;
        // Keep the user's reading position stable; collapse only by explicit action.
    };
    const consumeEvent = (event) => {
        if (contextRevision !== chatContextRevision) return;
        const followBottom = chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight < 80;
        if (event.type === 'reasoning') {
            if (reasoningStarted === null) reasoningStarted = Date.now();
            reasoning += event.text || '';
            reasoningPanel.hidden = false;
            reasoningText.textContent = reasoning;
            status.textContent = '正在思考…';
        } else if (event.type === 'content') {
            if (!fullText) window.DafeiyuPet?.setActivity('talk');
            finishReasoning();
            fullText += event.text || '';
            if (renderTimer === null) renderTimer = setTimeout(renderAnswer, 80);
            status.textContent = '正在回答…';
        } else if (event.type === 'error') {
            failed = true;
            status.textContent = `生成失败：${event.text || '请重试'}`;
        } else if (event.type === 'help_record') {
            LearningHelpUI.acknowledge(event.id);
        } else if (event.type === 'done') {
            renderAnswer();
            finished = true;
            finishReasoning();
            if (!failed) status.textContent = fullText.trim() ? '' : '模型未返回回答，请重试。';
        }
        if (followBottom) chatContainer.scrollTop = chatContainer.scrollHeight;
    };

    const chatTimeout = setTimeout(() => chatAbortController?.abort(), 130000);
    try {
        const response = await UserSession.csrfFetch('/api/ai-chat-stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
            signal: chatAbortController.signal,
            body: JSON.stringify({ message, language: attachment?.language || document.getElementById('languageSelector').value,
                include_context: !!attachment, history: chatHistory,
                ...(attachment ? {code: attachment.code, input_text: attachment.input_text, problem_id: attachment.problem_id} : {}) })
        });
        if (!response.ok || !response.body) {
            const result = await response.json().catch(() => ({}));
            throw new Error(apiErrorMessage(result, `请求失败 (${response.status})`));
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';
        const consumeBuffer = () => {
            let boundary;
            while ((boundary = buffer.indexOf('\n\n')) !== -1) {
                const frame = buffer.slice(0, boundary);
                buffer = buffer.slice(boundary + 2);
                const data = frame.split('\n').filter(line => line.startsWith('data:'))
                    .map(line => line.slice(5).trimStart()).join('\n');
                if (data) consumeEvent(JSON.parse(data));
            }
        };
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            consumeBuffer();
        }
        buffer += decoder.decode();
        consumeBuffer();
        if (contextRevision !== chatContextRevision) return;
        if (!finished) throw new Error('连接已中断，请重试。已生成的内容已保留。');
        if (!failed && fullText.trim()) {
            const historyText = attachment ? JSON.stringify({question:message, attached_practice:attachment}) : message;
            chatHistory.push({role:'user', content:historyText.slice(0,8000)},
                {role:'assistant', content:fullText.slice(0,8000)});
            chatHistory = chatHistory.slice(-10);
            attachedPractice = null;
            updateChatContext();
        }
    } catch (error) {
        if (contextRevision !== chatContextRevision) return;
        if (UserSession.handleAuthError(error, status, '请先登录后再使用编程助手。')) return;
        status.textContent = error.name === 'AbortError' ? '已停止，已生成的内容已保留。' : `请求失败：${error.message}`;
        if (reasoning && !reasoningFinished) summary.textContent = '思考已中止';
    } finally {
        clearTimeout(chatTimeout);
        renderAnswer();
        chatBusy = false;
        window.DafeiyuPet?.setActivity('idle');
        chatAbortController = null;
        stopButton.hidden = true;
        sendMessageBtn.disabled = false;
        messageInput.focus({preventScroll: true});
    }
}

function showOptimizationStale() {
    let note = document.getElementById('optimizationStale');
    if (!optimizationBase) return;
    if (!note) {
        note = document.createElement('p');
        note.id = 'optimizationStale';
        note.className = 'stale-note';
        note.textContent = '代码已修改，以下建议对应请求时的代码。需要新建议时请重新请求。';
        aiSuggestion.prepend(note);
    }
    note.hidden = codeInput.value === optimizationBase.code && document.getElementById('languageSelector').value === optimizationBase.language;
}
codeInput.addEventListener('input', showOptimizationStale);

function resetHelpOutputs() {
    aiContextRevision += 1;
    cancelInlineCompletion();
    inlineCompletionCache.clear();
    optimizeController?.abort();
    globalOptimizedVersions = [];
    optimizationBase = null;
    aiSuggestion.replaceChildren();
    document.getElementById('optimizationResult').hidden = true;
}
function resetChatContext() {
    chatContextRevision += 1;
    chatAbortController?.abort();
    chatHistory = [];
    chatContainer.replaceChildren();
    attachedPractice = null;
    updateChatContext();
}
window.addEventListener('auth:required', resetChatContext);
window.addEventListener('practice:help-settings', resetHelpOutputs);
window.addEventListener('practice:help-level', resetHelpOutputs);
window.addEventListener('practice:transfer-mode', () => {
    if (!window.PracticeTransfer?.blocksAI) return;
    cancelInlineCompletion();
    optimizeController?.abort();
    chatAbortController?.abort();
    aiContextRevision += 1;
    chatContextRevision += 1;
    if (!aiFloatingWindow.classList.contains('hidden')) setChatWindowOpen(false);
});
document.getElementById('languageSelector').addEventListener('change', () => {
    resetHelpOutputs();
    resetChatContext();
});
window.addEventListener('practice:submission', () => {
    // New judging evidence supersedes old context, without attaching the new submission to chat.
    resetHelpOutputs();
    resetChatContext();
});

document.getElementById('stopChat').addEventListener('click', () => chatAbortController?.abort());

const chatWindowStorageKey = 'dafeiyu-chat-window-v1';
let savedChatGeometry = null;
let chatMaximized = false;
try {
    const stored = JSON.parse(localStorage.getItem(chatWindowStorageKey));
    if (stored && ['left', 'top', 'width', 'height'].every(key => Number.isFinite(stored[key]))) {
        savedChatGeometry = stored;
        chatMaximized = stored.maximized === true;
    }
} catch (_) { /* Window placement is optional when browser storage is unavailable. */ }

function chatViewport() {
    const viewport = window.visualViewport;
    return {left: viewport?.offsetLeft || 0, top: viewport?.offsetTop || 0,
        width: viewport?.width || window.innerWidth, height: viewport?.height || window.innerHeight};
}

function defaultChatGeometry() {
    const viewport = chatViewport();
    const width = Math.min(440, viewport.width - 24);
    const height = Math.min(640, viewport.height - 24);
    return {left: viewport.left + viewport.width - width - 12,
        top: viewport.top + viewport.height - height - 12, width, height};
}

function currentChatGeometry() {
    const {left, top, width, height} = aiFloatingWindow.getBoundingClientRect();
    return {left, top, width, height};
}

function applyChatGeometry(geometry) {
    const viewport = chatViewport();
    const maxWidth = Math.max(1, viewport.width - 24);
    const maxHeight = Math.max(1, viewport.height - 24);
    const width = Math.max(Math.min(300, maxWidth), Math.min(geometry.width, maxWidth));
    const height = Math.max(Math.min(300, maxHeight), Math.min(geometry.height, maxHeight));
    const left = Math.max(viewport.left + 12, Math.min(geometry.left, viewport.left + viewport.width - width - 12));
    const top = Math.max(viewport.top + 12, Math.min(geometry.top, viewport.top + viewport.height - height - 12));
    Object.assign(aiFloatingWindow.style, {left: `${left}px`, top: `${top}px`,
        width: `${width}px`, height: `${height}px`, right: 'auto', bottom: 'auto'});
    return {left, top, width, height};
}

function resizeChatGeometry(rect, direction, dx, dy) {
    const viewport = chatViewport();
    const minWidth = Math.min(300, viewport.width - 24), minHeight = Math.min(300, viewport.height - 24);
    let left = rect.left, top = rect.top, right = left + rect.width, bottom = top + rect.height;
    if (direction.includes('w')) left = Math.max(viewport.left + 12, Math.min(left + dx, right - minWidth));
    if (direction.includes('e')) right = Math.min(viewport.left + viewport.width - 12, Math.max(right + dx, left + minWidth));
    if (direction.includes('n')) top = Math.max(viewport.top + 12, Math.min(top + dy, bottom - minHeight));
    if (direction.includes('s')) bottom = Math.min(viewport.top + viewport.height - 12, Math.max(bottom + dy, top + minHeight));
    return {left, top, width: right - left, height: bottom - top};
}

function saveChatGeometry() {
    if (!chatMaximized) savedChatGeometry = currentChatGeometry();
    try { localStorage.setItem(chatWindowStorageKey, JSON.stringify({
        ...(savedChatGeometry || defaultChatGeometry()), maximized: chatMaximized
    })); } catch (_) {}
}

function renderChatWindowMode() {
    aiFloatingWindow.classList.toggle('is-maximized', chatMaximized);
    const button = document.getElementById('maximizeChatWindow');
    button.setAttribute('aria-pressed', String(chatMaximized));
    button.setAttribute('aria-label', chatMaximized ? '还原对话框' : '最大化对话框');
    button.title = chatMaximized ? '还原' : '最大化';
    button.innerHTML = chatMaximized
        ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M8 8V4h12v12h-4"/><rect x="4" y="8" width="12" height="12" rx="1"/></svg>'
        : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="1"/></svg>';
    if (chatMaximized) {
        const viewport = chatViewport();
        applyChatGeometry({left: viewport.left + 12, top: viewport.top + 12,
            width: viewport.width - 24, height: viewport.height - 24});
    }
}

function toggleChatMaximized() {
    if (!chatMaximized) savedChatGeometry = currentChatGeometry();
    chatMaximized = !chatMaximized;
    renderChatWindowMode();
    if (!chatMaximized) applyChatGeometry(savedChatGeometry || defaultChatGeometry());
    saveChatGeometry();
}

function setChatWindowOpen(open) {
    if (open && window.PracticeTransfer?.blocksAI) { window.PracticeTransfer.notifyBlocked?.(); return; }
    aiFloatingWindow.classList.toggle('hidden', !open);
    aiToggleBtn.setAttribute('aria-expanded', String(open));
    aiToggleBtn.setAttribute('aria-label', `${open ? '收起' : '打开'}达菲郁编程助手`);
    if (open) {
        applyChatGeometry(savedChatGeometry || defaultChatGeometry());
        renderChatWindowMode();
        messageInput.focus({preventScroll: true});
    } else aiToggleBtn.focus({preventScroll: true});
}

function toggleAiWindow() { setChatWindowOpen(aiFloatingWindow.classList.contains('hidden')); }
document.getElementById('closeChatWindow').addEventListener('click', () => setChatWindowOpen(false));
document.getElementById('maximizeChatWindow').addEventListener('click', toggleChatMaximized);
document.getElementById('resetChatWindow').addEventListener('click', () => {
    chatMaximized = false;
    renderChatWindowMode();
    applyChatGeometry(defaultChatGeometry());
    saveChatGeometry();
});
aiFloatingWindow.addEventListener('keydown', event => {
    if (event.key === 'Escape') { event.preventDefault(); setChatWindowOpen(false); }
});

(function setupChatWindowInteraction() {
    const header = document.getElementById('aiDragHandle');
    const resizeHandles = [...aiFloatingWindow.querySelectorAll('.chat-resize-handle')];
    let interaction = null;
    header.addEventListener('dblclick', event => {
        if (!event.target.closest('.chat-window-actions')) toggleChatMaximized();
    });
    function start(event, direction, handle) {
        if (event.button !== 0 || event.target.closest('.chat-window-actions')) return;
        const rect = currentChatGeometry();
        interaction = {direction, pointerId: event.pointerId, x: event.clientX, y: event.clientY,
            ...rect, wasMaximized: chatMaximized, moved: false};
        handle.setPointerCapture(event.pointerId);
        event.preventDefault();
    }
    function move(event) {
        if (!interaction || event.pointerId !== interaction.pointerId) return;
        let dx = event.clientX - interaction.x, dy = event.clientY - interaction.y;
        if (!interaction.moved && Math.hypot(dx, dy) < 3) return;
        interaction.moved = true;
        aiFloatingWindow.classList.add('is-manipulating');
        if (interaction.wasMaximized) {
            // Restore under the grab point, as a desktop window does when pulled down.
            const ratio = Math.max(0, Math.min(1, (interaction.x - interaction.left) / interaction.width));
            const normal = savedChatGeometry || defaultChatGeometry();
            chatMaximized = false;
            renderChatWindowMode();
            const restored = applyChatGeometry({...normal,
                left: event.clientX - normal.width * ratio, top: event.clientY - Math.min(30, interaction.y - interaction.top)});
            Object.assign(interaction, restored, {x: event.clientX, y: event.clientY, wasMaximized: false});
            dx = 0; dy = 0;
        }
        const geometry = interaction.direction === 'move'
            ? {...interaction, left: interaction.left + dx, top: interaction.top + dy}
            : resizeChatGeometry(interaction, interaction.direction, dx, dy);
        applyChatGeometry(geometry);
    }
    function end(event) {
        if (!interaction || event.pointerId !== interaction.pointerId) return;
        interaction = null;
        aiFloatingWindow.classList.remove('is-manipulating');
        saveChatGeometry();
    }
    for (const handle of [header, ...resizeHandles]) {
        const direction = handle === header ? 'move' : handle.dataset.direction;
        handle.addEventListener('pointerdown', event => start(event, direction, handle));
        handle.addEventListener('pointermove', move);
        handle.addEventListener('pointerup', end);
        handle.addEventListener('pointercancel', end);
        handle.addEventListener('lostpointercapture', end);
        handle.addEventListener('keydown', event => {
            if (event.target !== handle || !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
            event.preventDefault();
            if (chatMaximized) toggleChatMaximized();
            const rect = currentChatGeometry();
            const step = event.shiftKey ? 40 : 12;
            const dx = event.key === 'ArrowLeft' ? -step : event.key === 'ArrowRight' ? step : 0;
            const dy = event.key === 'ArrowUp' ? -step : event.key === 'ArrowDown' ? step : 0;
            applyChatGeometry(direction === 'move'
                ? {...rect, left: rect.left + dx, top: rect.top + dy}
                : resizeChatGeometry(rect, direction, dx, dy));
            saveChatGeometry();
        });
    }
    const constrain = () => {
        if (aiFloatingWindow.classList.contains('hidden')) return;
        if (chatMaximized) renderChatWindowMode();
        else applyChatGeometry(currentChatGeometry());
    };
    window.addEventListener('resize', constrain);
    window.visualViewport?.addEventListener('resize', constrain);
    window.visualViewport?.addEventListener('scroll', constrain);
})();

runBtn.addEventListener('click', runCode);
optimizeBtn.addEventListener('click', optimizeCode);
submitBtn.addEventListener('click', submitCode);
sendMessageBtn.addEventListener('click', sendMessage);
aiToggleBtn.addEventListener('click', toggleAiWindow);

let chatComposing = false;
messageInput.addEventListener('compositionstart', () => { chatComposing = true; });
messageInput.addEventListener('compositionend', () => { chatComposing = false; });
messageInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.isComposing && !chatComposing && e.keyCode !== 229) { e.preventDefault(); sendMessage(); }
});

renderGhostLayer();

chatProblemId = getCurrentProblemId();
addChatMessage('我是达菲郁，陪你把代码里的小问号一个个捞起来。🐋 有问题就丢给本鱼吧！', 'ai');

// Click alternatives to moving/resizing the assistant.
document.querySelectorAll('[data-chat-dock],[data-chat-size]').forEach(button => button.addEventListener('click', () => {
    chatMaximized = false; renderChatWindowMode();
    const viewport = chatViewport(), rect = currentChatGeometry();
    if (button.dataset.chatSize) {
        rect.width = button.dataset.chatSize === 'compact' ? 360 : 440;
        rect.height = button.dataset.chatSize === 'compact' ? 480 : 640;
    }
    if (button.dataset.chatDock) rect.left = button.dataset.chatDock === 'left' ? viewport.left + 12 : viewport.left + viewport.width - rect.width - 12;
    applyChatGeometry(rect); saveChatGeometry();
}));
document.getElementById('dockPet').addEventListener('click', () => window.DafeiyuPet?.dock());
document.getElementById('hidePet').addEventListener('click', () => {
    setChatWindowOpen(false); aiToggleBtn.hidden = true;
    document.getElementById('restorePet').hidden = false; document.getElementById('restorePet').focus();
});
document.getElementById('restorePet').addEventListener('click', () => {
    aiToggleBtn.hidden = false; document.getElementById('restorePet').hidden = true;
    window.DafeiyuPet?.dock(); setChatWindowOpen(true);
});
