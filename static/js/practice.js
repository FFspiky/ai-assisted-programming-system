document.addEventListener('DOMContentLoaded', function () {
    fetchCurrentUser();
    loadProblem();

    // --- 主题切换功能 ---
    const themeSelector = document.getElementById('themeSelector');
    const savedTheme = localStorage.getItem('selectedTheme') || 'default';

    document.documentElement.setAttribute('data-theme', savedTheme === 'default' ? null : savedTheme);
    themeSelector.value = savedTheme;

    themeSelector.addEventListener('change', function () {
        const theme = this.value;
        if (theme === 'default') {
            document.documentElement.removeAttribute('data-theme');
        } else {
            document.documentElement.setAttribute('data-theme', theme);
        }
        localStorage.setItem('selectedTheme', theme);
    });
});

async function fetchCurrentUser() {
    try {
        const response = await fetch('/api/current_user');
        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                updateUserInfo(result.user);
            } else {
                showLoginRegister();
            }
        } else {
            showLoginRegister();
        }
    } catch (error) {
        console.error('获取用户信息失败', error);
        showLoginRegister();
    }
}

function updateUserInfo(user) {
    const userInfoDiv = document.querySelector('.user-info');
    userInfoDiv.innerHTML = `
        <div class="user-details">
            <div class="username">${user.username}</div>
            <div class="user-stats">
                <span>积分: ${user.points}</span>
                <a href="#" id="logoutBtn" style="color: #f72585; cursor: pointer; margin-left: 15px; text-decoration: none;">登出</a>
            </div>
        </div>
        <div class="user-avatar" id="userAvatar">
            <img src="https://mms1.baidu.com/it/u=1390447151,3494080119&fm=253&app=138&f=JPEGw=500&h=500">
        </div>
    `;
    document.getElementById('logoutBtn').addEventListener('click', handleLogout);
}

function showLoginRegister() {
    const userInfoDiv = document.querySelector('.user-info');
    userInfoDiv.innerHTML = `
        <div style="display: flex; gap: 10px;">
            <a href="/login.html" class="btn">登录</a>
            <a href="/register.html" class="btn" style="background: var(--primary);">注册</a>
        </div>
    `;
}

async function handleLogout(e) {
    e.preventDefault();
    await fetch('/api/logout', { method: 'POST' });
    alert("已成功登出");
    window.location.href = '/index.html';
}


function getCurrentProblemId() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('problem');
}

let problemOrderCache = null;

async function getProblemOrder() {
    if (problemOrderCache) {
        return problemOrderCache;
    }
    const response = await fetch('/api/problems');
    const result = await response.json();
    if (!result.success || !result.problems) {
        return [];
    }
    problemOrderCache = result.problems.map((p) => p.id);
    return problemOrderCache;
}

async function updateNextButtonState() {
    if (!nextProblemBtn) {
        return;
    }
    try {
        const currentId = getCurrentProblemId();
        if (!currentId) {
            nextProblemBtn.classList.add('is-disabled');
            return;
        }
        const order = await getProblemOrder();
        const currentIndex = order.indexOf(currentId);
        const hasNext = currentIndex >= 0 && currentIndex + 1 < order.length;
        nextProblemBtn.classList.toggle('is-disabled', !hasNext);
        nextProblemBtn.title = hasNext ? '' : '已是最后一题';
    } catch (error) {
        nextProblemBtn.classList.add('is-disabled');
        nextProblemBtn.title = '已是最后一题';
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
                <span>${problem.title || '无标题'}</span>
                <div class="problem-meta">
                    <span class="problem-difficulty ${difficultyClass}">${problem.difficulty || '未知'}</span>
                </div>
            `;
            problemContentEl.innerHTML = problem.description || '<p>该题目没有描述信息。</p>';
        } else {
            problemTitleEl.textContent = '加载失败';
            problemContentEl.innerHTML = `<p>无法加载题目详情，错误：${result.error || '未知错误'}</p>`;
        }

    } catch (error) {
        console.error('加载题目失败:', error);
        problemTitleEl.textContent = '加载失败';
        problemContentEl.innerHTML = `<p>请求题目数据时发生网络错误: ${error.message}</p>`;
    }
    await updateNextButtonState();
}

// DOM元素
const codeInput = document.getElementById('codeInput');
const outputContent = document.getElementById('outputContent');
const aiSuggestion = document.getElementById('aiSuggestion');
const runBtn = document.getElementById('runBtn');
const optimizeBtn = document.getElementById('optimizeBtn');
const submitBtn = document.getElementById('submitBtn');
const nextProblemBtn = document.getElementById('nextProblemBtn');
const chatContainer = document.getElementById('chatContainer');
const messageInput = document.getElementById('messageInput');
const sendMessageBtn = document.getElementById('sendMessage');
const ghostLayer = document.getElementById('ghostLayer');
const inlineHint = document.getElementById('inlineHint');

let inlineSuggestion = '';
let inlineAbortController = null;
let inlineRequestId = 0;
let inlineDebounceTimer = null;

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
    const suffix = text.slice(end);
    const ghost = start === end ? inlineSuggestion : '';
    ghostLayer.innerHTML = `<span class="typed">${escapeHtml(prefix)}</span><span class="ghost">${escapeHtml(ghost)}</span><span class="typed">${escapeHtml(suffix)}</span>`;
    ghostLayer.scrollTop = codeInput.scrollTop;
    ghostLayer.scrollLeft = codeInput.scrollLeft;
    if (inlineHint) {
        inlineHint.classList.toggle('is-visible', ghost.length > 0);
    }
}

function clearInlineSuggestion() {
    inlineSuggestion = '';
    renderGhostLayer();
}

function scheduleInlineCompletion(force = false) {
    if (!codeInput) {
        return;
    }
    if (inlineDebounceTimer) {
        clearTimeout(inlineDebounceTimer);
    }
    if (force) {
        inlineRequestId += 1;
        requestInlineCompletion(inlineRequestId);
        return;
    }
    inlineDebounceTimer = setTimeout(() => {
        inlineRequestId += 1;
        requestInlineCompletion(inlineRequestId);
    }, 200);
}

async function requestInlineCompletion(requestId) {
    const { prefix, suffix, start, end } = getCursorContext();
    if (start !== end || prefix.length < 5) {
        clearInlineSuggestion();
        return;
    }
    if (inlineAbortController) {
        inlineAbortController.abort();
    }
    inlineAbortController = new AbortController();
    const language = document.getElementById('languageSelector').value || 'python';

    try {
        const response = await fetch('/api/ai-inline-complete-stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                language,
                prefix,
                suffix,
                max_tokens: 128
            }),
            signal: inlineAbortController.signal
        });
        if (!response.ok || !response.body) {
            clearInlineSuggestion();
            return;
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';
        while (true) {
            const { value, done } = await reader.read();
            if (done) {
                break;
            }
            buffer += decoder.decode(value, { stream: true });
            if (requestId !== inlineRequestId) {
                return;
            }
            inlineSuggestion = buffer;
            renderGhostLayer();
        }
    } catch (error) {
        clearInlineSuggestion();
    }
}

function acceptInlineSuggestion() {
    if (!inlineSuggestion) {
        return;
    }
    const text = codeInput.value || '';
    const start = codeInput.selectionStart || 0;
    const end = codeInput.selectionEnd || start;
    codeInput.value = text.slice(0, start) + inlineSuggestion + text.slice(end);
    const newPos = start + inlineSuggestion.length;
    codeInput.setSelectionRange(newPos, newPos);
    clearInlineSuggestion();
}

if (codeInput) {
    codeInput.addEventListener('input', () => {
        clearInlineSuggestion();
        scheduleInlineCompletion();
    });
    codeInput.addEventListener('keydown', (e) => {
        if (e.key === 'Tab' && inlineSuggestion) {
            e.preventDefault();
            acceptInlineSuggestion();
            return;
        }
        if (e.key === 'Escape' && inlineSuggestion) {
            e.preventDefault();
            clearInlineSuggestion();
            return;
        }
        if (e.ctrlKey && e.key === ' ') {
            e.preventDefault();
            scheduleInlineCompletion(true);
        }
    });
    codeInput.addEventListener('click', renderGhostLayer);
    codeInput.addEventListener('keyup', renderGhostLayer);
    codeInput.addEventListener('scroll', () => {
        if (!ghostLayer) {
            return;
        }
        ghostLayer.scrollTop = codeInput.scrollTop;
        ghostLayer.scrollLeft = codeInput.scrollLeft;
    });
    renderGhostLayer();
}

if (nextProblemBtn) {
    nextProblemBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        if (nextProblemBtn.classList.contains('is-disabled')) {
            return;
        }
        try {
            const currentId = getCurrentProblemId();
            if (!currentId) {
                alert('请先选择题目');
                return;
            }
            const order = await getProblemOrder();
            const currentIndex = order.indexOf(currentId);
            const nextId = currentIndex >= 0 ? order[currentIndex + 1] : null;
            if (!nextId) {
                alert('已经是最后一题');
                return;
            }
            window.location.href = `/practice.html?problem=${encodeURIComponent(nextId)}`;
        } catch (error) {
            alert(`获取下一题失败: ${error.message}`);
        }
    });
}
const aiFloatingWindow = document.getElementById('aiFloatingWindow');
const aiToggleBtn = document.getElementById('aiToggleBtn');

let globalOptimizedVersions = [];

function escapeHtml(text) {
    var map = {
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
    };
    return String(text || '').replace(/[&<>"']/g, function (m) { return map[m]; });
}

            // 记录页面加载的时间戳
    const startTime = Date.now();

    // 当用户准备离开页面时（关闭、刷新、跳转）触发
    window.addEventListener('beforeunload', function(event) {
        // 计算停留时长（秒）
        const endTime = Date.now();
        const durationInSeconds = Math.round((endTime - startTime) / 1000);

        // 只有当停留时间超过10秒时才记录，避免无效数据
        if (durationInSeconds > 10) {
            // 使用 navigator.sendBeacon 发送数据
            // 这种方式可以确保即使用户关闭了页面，请求也能大概率成功发送
            const data = new Blob(
                [JSON.stringify({ duration: durationInSeconds })],
                { type: 'application/json' }
            );
            navigator.sendBeacon('/api/update_learning_time', data);
        }
    });

    // 注意：为了让 sendBeacon 生效，需要确保后端API支持 application/json
    // Flask 默认支持，但如果您的服务器配置了严格的CORS或内容类型策略，请确保允许。
    // 如果 sendBeacon 不可用或被阻止，可以退回到使用同步的 XMLHttpRequest，但这会阻塞页面关闭，体验不佳。

function formatAiResponse(text) {
    if (!text) return '';
    text = text.replace(/---/g, '<hr>');
    text = text.replace(/^######\s*(.*)$/gm, '<h6>$1</h6>');
    text = text.replace(/^#####\s*(.*)$/gm, '<h5>$1</h5>');
    text = text.replace(/^####\s*(.*)$/gm, '<h4>$1</h4>');
    text = text.replace(/^###\s*(.*)$/gm, '<h3>$1</h3>');
    text = text.replace(/^##\s*(.*)$/gm, '<h2>$1</h2>');
    text = text.replace(/^#\s*(.*)$/gm, '<h1>$1</h1>');
    text = text.replace(/^([一二三四五六七八九十]+、[^\n]+)/gm, '<span class="section-title">$1</span>');
    text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\*(.*?)\*/g, '<em>$1</em>');
    text = text.replace(/^\s*([*-])\s+(.*)$/gm, '<li>$2</li>');
    text = text.replace(/(<li>.*?<\/li>(\n<li>.*?<\/li>)*)/g, '<ul>$1</ul>');
    text = text.replace(/\n\s*\n/g, '</p><p>').replace(/\n/g, '<br>');
    return `<div class="ai-formatted-content">${text}</div>`;
}

function applyOptimizedCode(versionIndex) {
    if (versionIndex >= 0 && versionIndex < globalOptimizedVersions.length) {
        codeInput.value = globalOptimizedVersions[versionIndex].code;
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
        const response = await fetch('/api/run-code', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code, language, input_text: customInput })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || errorData.message || `服务器返回错误: ${response.status} ${response.statusText}`);
        }

        const result = await response.json();
        const safeOutput = escapeHtml(result.output || '无输出内容');
        const safeError = escapeHtml(result.error || '未知错误');
        const safeStderr = escapeHtml(result.stderr || '');
        if (result.success) {
            outputContent.innerHTML = `<div style="margin-bottom:8px; color:var(--success)"><i class="fas fa-check-circle"></i> 执行成功 (${result.time}ms)</div><pre style="background:rgba(76,201,240,0.1); padding:12px; border-radius:6px;">${safeOutput}</pre>`;
        } else {
            outputContent.innerHTML = `<div style="margin-bottom:8px; color:var(--warning)"><i class="fas fa-times-circle"></i> 执行失败 (${result.time}ms)</div><div style="color:var(--warning); margin-bottom:8px;">${escapeHtml(language)}环境错误:</div><pre style="background:rgba(247,37,133,0.1); padding:12px; border-radius:6px;">${safeError}</pre>${safeStderr ? `<pre style="background:rgba(247,37,133,0.1); padding:12px; border-radius:6px; margin-top:8px;">${safeStderr}</pre>` : ''}`;
        }
    } catch (error) {
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
    const code = document.getElementById('codeInput').value;
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

    try {
        const response = await fetch('/api/optimize-code', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({ code })
        });

        if (!response.ok) {
            throw new Error(`HTTP错误: ${response.status}`);
        }

        const result = await response.json();

        if (result.success) {
            // 将获取到的优化版本存储到全局变量
            globalOptimizedVersions = result.optimizedVersions; // <--- 关键：保存到全局变量

            let versionsHtml = '';
            if (globalOptimizedVersions && globalOptimizedVersions.length > 0) {
                versionsHtml = globalOptimizedVersions.map((version, index) => `
                    <div class="optimized-version-card" style="margin-bottom:15px; border:1px solid var(--light-gray); padding:10px; border-radius:8px; background-color: var(--darker);">
                        <div style="font-weight:600; margin-bottom:5px; color:var(--accent);">
                            ${version.description || `优化版本 ${index + 1}`}
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
                versionsHtml = `<p style="color:var(--warning);">未能生成优化版本，或AI返回格式不符预期。</p>`;
            }

            aiSuggestion.innerHTML = `
                <div style="color:var(--success)">
                    <i class="fas fa-check-circle"></i> 优化完成！
                </div>
                <div style="margin: 10px 0; font-weight:500"></div>
                <div style="margin-bottom:10px; padding:8px; background:rgba(76,201,240,0.1); border-radius:6px;">
                    ${formatAiResponse(result.feedback) || '代码已优化，性能更优'} </div>
                <div style="margin: 10px 0; font-weight:500">优化版本选择：</div>
                ${versionsHtml}
            `;
        } else {
            aiSuggestion.innerHTML = `<div style="color:var(--warning)"><i class="fas fa-exclamation-triangle"></i> AI优化失败: ${result.error}</div>`;
        }
    } catch (error) {
        aiSuggestion.innerHTML = `<div style="color:var(--warning)"><i class="fas fa-exclamation-triangle"></i> 请求失败: ${error.message}</div>`;
        console.error('优化代码请求错误:', error);
    } finally {
        optimizeBtn.disabled = false;
        optimizeBtn.innerHTML = '<i class="fas fa-cogs"></i> AI优化';
    }
}

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
        const response = await fetch('/api/check-solution', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code, language, problem_id: problemId })
        });
        const result = await response.json();
        const safeDetails = escapeHtml(result.details || result.error || '没有返回详细信息。');
        const safeStatus = escapeHtml(result.status || '提交失败');

        if (result.success && result.status === "Accepted") {
            outputContent.innerHTML = `<div class="ai-response" style="border-left-color: var(--success);"><h4 style="color: var(--success); display: flex; align-items: center; gap: 8px;"><i class="fas fa-check-circle"></i><span>${safeStatus}</span></h4><pre style="white-space: pre-wrap;">${safeDetails || '通过！'}</pre></div>`;
        } else {
            outputContent.innerHTML = `<div class="ai-response" style="border-left-color: var(--danger);"><h4 style="color: var(--danger); display: flex; align-items: center; gap: 8px;"><i class="fas fa-times-circle"></i><span>${safeStatus}</span></h4><pre style="white-space: pre-wrap;">${safeDetails}</pre></div>`;
        }
    } catch (error) {
        outputContent.innerHTML = `<div style="margin-bottom:8px; color:var(--warning)"><i class="fas fa-exclamation-triangle"></i> 请求失败</div><pre style="background:rgba(247,37,133,0.1); padding:12px; border-radius:6px;">${escapeHtml(error.message)}</pre>`;
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fas fa-paper-plane"></i> 提交解答';
        outputContent.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

function addChatMessage(content, sender, id = null, isHtml = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;
    const header = document.createElement('div');
    header.className = 'message-header';
    header.innerHTML = sender === 'ai' ? '<i class="fas fa-robot"></i> AI助手' : '<i class="fas fa-user"></i> 你';
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    if (id) contentDiv.id = id;
    if (sender === 'ai') {
        contentDiv.innerHTML = isHtml ? content : formatAiResponse(content);
    } else {
        contentDiv.textContent = content;
    }
    messageDiv.appendChild(header);
    messageDiv.appendChild(contentDiv);
    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return contentDiv;
}

async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message) return;

    addChatMessage(message, 'user');
    messageInput.value = '';

    const aiId = `ai-${Date.now()}`;
    const aiContentDiv = addChatMessage('<span class="thinking">🤔 AI助手正在思考中...</span>', 'ai', aiId, true);

    try {
        const response = await fetch('/api/ai-chat-stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, language: 'Python' })
        });

        if (!response.ok) {
            aiContentDiv.innerText = `错误: ${response.statusText}`;
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let fullText = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            fullText += decoder.decode(value, { stream: true });
            aiContentDiv.innerHTML = formatAiResponse(fullText);
        }
    } catch (error) {
        aiContentDiv.innerText = `请求失败: ${error.message}`;
        console.error('聊天错误:', error);
    }
}

function toggleAiWindow() {
    aiFloatingWindow.classList.toggle('hidden');
}

runBtn.addEventListener('click', runCode);
optimizeBtn.addEventListener('click', optimizeCode);
submitBtn.addEventListener('click', submitCode);
sendMessageBtn.addEventListener('click', sendMessage);
aiToggleBtn.addEventListener('click', toggleAiWindow);

messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

codeInput.value = `# 示例Python代码\ndef greet(name):\n    return f"Hello, {name}!"\n\nprint(greet("World"))\n`;
renderGhostLayer();

// --- 拖拽功能 ---
(function () {
    const btn = document.getElementById('aiToggleBtn');
    let isDragging = false, startX, startY, initialLeft, initialTop, isClick = true;

    function startDrag(e) {
        isDragging = true;
        isClick = true;
        const rect = btn.getBoundingClientRect();
        initialLeft = rect.left;
        initialTop = rect.top;
        if (e.type === 'mousedown') {
            startX = e.clientX; startY = e.clientY;
        } else if (e.type === 'touchstart') {
            startX = e.touches[0].clientX; startY = e.touches[0].clientY;
        }
        btn.style.transition = 'none';
        btn.style.boxShadow = '0 10px 25px rgba(138, 43, 226, 0.6)';
        e.preventDefault();
    }

    function duringDrag(e) {
        if (!isDragging) return;
        isClick = false;
        let currentX, currentY;
        if (e.type === 'mousemove') {
            currentX = e.clientX; currentY = e.clientY;
        } else if (e.type === 'touchmove') {
            currentX = e.touches[0].clientX; currentY = e.touches[0].clientY;
        }
        const dx = currentX - startX, dy = currentY - startY;
        btn.style.left = `${initialLeft + dx}px`;
        btn.style.top = `${initialTop + dy}px`;
        btn.style.right = 'auto';
        btn.style.bottom = 'auto';
        e.preventDefault();
    }

    function endDrag(e) {
        if (!isDragging) return;
        isDragging = false;
        btn.style.transition = 'all 0.3s ease';
        btn.style.boxShadow = '0 5px 15px rgba(138, 43, 226, 0.4)';
        if (!isClick) { e.preventDefault(); e.stopPropagation(); }
    }

    btn.addEventListener('mousedown', startDrag);
    document.addEventListener('mousemove', duringDrag);
    document.addEventListener('mouseup', endDrag);
    btn.addEventListener('touchstart', startDrag, { passive: false });
    document.addEventListener('touchmove', duringDrag, { passive: false });
    document.addEventListener('touchend', endDrag);
    btn.addEventListener('click', function (e) {
        if (!isClick) { e.preventDefault(); e.stopPropagation(); }
    });
})();

