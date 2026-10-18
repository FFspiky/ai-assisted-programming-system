(() => {
    'use strict';

    const state = {
        questions: [], answers: {}, current: 0, assessment: null, plan: null,
        revision: 0, authenticated: false, wizardOpen: true,
        questionLoading: true, planLoading: false, submitting: false,
        conflict: false, conflictResult: null, aiLoading: false
    };
    const GUEST_DRAFT_KEY = 'codelab:learning-plan:guest-draft:v1';
    const AI_ANALYSIS_CACHE_TTL_MS = 24 * 60 * 60 * 1000;
    let questionsReady;
    let currentOverviewSignature = '';
    let currentAnalysisUserKey = 'guest';
    const $ = (id) => document.getElementById(id);
    const escapeHtml = (text) => String(text ?? '').replace(/[&<>"']/g, (char) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
    }[char]));
    const copyAnswers = (answers) => Object.fromEntries(Object.entries(answers || {}).map(
        ([key, value]) => [key, Array.isArray(value) ? [...value] : value]
    ));
    const busy = () => state.questionLoading || state.planLoading || state.submitting;

    function notice(id, message = '', isError = false) {
        const element = $(id);
        element.textContent = message;
        element.classList.toggle('is-error', isError);
        element.hidden = !message;
    }

    function showLoginNotice(message) {
        notice('assessmentNotice', message, true);
        const link = document.createElement('a');
        link.href = UserSession.loginUrl();
        link.dataset.returnToCurrent = 'true';
        link.textContent = '登录后返回问卷';
        $('assessmentNotice').append(' ', link);
    }

    function validAnswer(question, answer = state.answers[question.id]) {
        const allowed = new Set(question.options.map((option) => option.value));
        if (question.type === 'multi') {
            return Array.isArray(answer) && answer.length > 0 &&
                answer.length <= question.max_select && new Set(answer).size === answer.length &&
                answer.every((value) => allowed.has(value));
        }
        return typeof answer === 'string' && allowed.has(answer);
    }

    function saveGuestDraft() {
        if (state.authenticated) return;
        try { sessionStorage.setItem(GUEST_DRAFT_KEY, JSON.stringify(state.answers)); } catch (_) { /* Optional draft storage. */ }
    }

    function restoreGuestDraft() {
        try {
            const answers = JSON.parse(sessionStorage.getItem(GUEST_DRAFT_KEY) || '{}');
            state.questions.forEach((question) => {
                if (validAnswer(question, answers[question.id])) state.answers[question.id] = answers[question.id];
            });
        } catch (_) { /* Ignore invalid or unavailable draft storage. */ }
    }

    function updateControls() {
        const pending = busy();
        $('assessmentForm').setAttribute('aria-busy', String(pending));
        $('prevBtn').disabled = pending || state.current === 0;
        $('nextBtn').disabled = pending;
        $('submitBtn').disabled = pending || state.conflict;
        $('submitBtn').innerHTML = state.submitting
            ? '正在保存…' : '保存并推荐简单项目 <i class="fas fa-arrow-right" aria-hidden="true"></i>';
        ['retakeBtn', 'refreshPlanBtn', 'retryPlanBtn', 'retryQuestionsBtn'].forEach((id) => { $(id).disabled = pending; });
        $('cancelRetakeBtn').disabled = pending || state.conflict;
        $('useLatestAnswersBtn').disabled = pending || !state.conflictResult;
        $('keepDraftAnswersBtn').disabled = pending || !state.conflictResult;
        $('retryConflictBtn').disabled = pending;
        document.querySelectorAll('#questionContainer .option-btn').forEach((button) => { button.disabled = pending; });
    }

    function renderAssessment() {
        const hasQuestions = state.questions.length > 0;
        $('assessmentForm').hidden = !hasQuestions || !state.wizardOpen;
        $('assessmentSaved').hidden = !state.assessment || state.wizardOpen;
        $('cancelRetakeBtn').hidden = !state.assessment;
        $('assessmentConflict').hidden = !state.conflict;
        $('retryConflictBtn').hidden = Boolean(state.conflictResult);
        if (!hasQuestions) return updateControls();
        const completed = state.questions.filter((question) => validAnswer(question)).length;
        $('questionCount').textContent = state.wizardOpen
            ? `${state.current + 1} / ${state.questions.length}` : `${state.questions.length} 项已保存`;
        $('completedCount').textContent = `已完成 ${completed} / ${state.questions.length}`;
        $('progressBar').style.width = `${completed / state.questions.length * 100}%`;
        $('assessmentProgress').setAttribute('aria-valuemax', String(state.questions.length));
        $('assessmentProgress').setAttribute('aria-valuenow', String(completed));
        $('assessmentSavedAt').textContent = '可以随时重新填写；项目进度会从实战任务室同步。';
        if (state.assessment?.updated_at) {
            const savedAt = new Date(state.assessment.updated_at);
            if (!Number.isNaN(savedAt.getTime())) $('assessmentSavedAt').textContent = `保存于 ${savedAt.toLocaleString('zh-CN')}，可随时重新填写。`;
        }
        const question = state.questions[state.current];
        const selected = state.answers[question.id];
        const hint = question.type === 'multi' ? `选择 1–${question.max_select} 项，可再次点击取消` : '选择最接近你实际情况的一项';
        $('questionContainer').innerHTML = `
            <div class="question-content">
                <h3 id="currentQuestionTitle" tabindex="-1">${escapeHtml(question.title)}</h3>
                <p class="question-hint" id="questionHint">${escapeHtml(hint)}</p>
                <div class="options" role="group" aria-labelledby="currentQuestionTitle" aria-describedby="questionHint">
                    ${question.options.map((option) => {
                        const checked = question.type === 'multi' ? (Array.isArray(selected) ? selected : []).includes(option.value) : selected === option.value;
                        return `<button type="button" class="option-btn${checked ? ' selected' : ''}" data-value="${escapeHtml(option.value)}" aria-pressed="${checked}"><span class="option-indicator" aria-hidden="true">${checked ? '✓' : ''}</span><span>${escapeHtml(option.label)}</span></button>`;
                    }).join('')}
                </div>
            </div>`;
        $('nextBtn').hidden = state.current === state.questions.length - 1;
        $('submitBtn').hidden = state.current !== state.questions.length - 1;
        updateControls();
    }

    function goToQuestion(index) {
        if (busy() || index < 0 || index >= state.questions.length) return;
        state.current = index;
        $('questionError').hidden = true;
        renderAssessment();
        $('currentQuestionTitle').focus({ preventScroll: true });
    }

    function showQuestionError(message) {
        $('questionError').textContent = message;
        $('questionError').hidden = false;
    }

    function handleOptionSelect(event) {
        const button = event.target.closest('.option-btn');
        if (!button || busy()) return;
        const question = state.questions[state.current];
        const value = button.dataset.value;
        if (question.type === 'multi') {
            const selected = Array.isArray(state.answers[question.id]) ? [...state.answers[question.id]] : [];
            const index = selected.indexOf(value);
            if (index >= 0) selected.splice(index, 1);
            else if (selected.length < question.max_select) selected.push(value);
            else return showQuestionError(`最多选择 ${question.max_select} 项，请先取消一项。`);
            state.answers[question.id] = selected;
        } else {
            state.answers[question.id] = value;
        }
        $('questionError').hidden = true;
        saveGuestDraft();
        renderAssessment();
        // Advancing stays explicit, and keyboard focus stays on the selected option.
        [...$('questionContainer').querySelectorAll('.option-btn')].find((option) => option.dataset.value === value)?.focus({ preventScroll: true });
    }

    async function fetchQuestions() {
        state.questionLoading = true;
        $('questionLoading').hidden = false;
        $('retryQuestionsBtn').hidden = true;
        updateControls();
        try {
            const response = await fetch('/api/learning-plan/questions', { cache: 'no-store' });
            const packet = await response.json();
            if (!response.ok) throw new Error(UserSession.apiErrorMessage(packet, '问卷暂时无法加载。'));
            const result = packet.data || packet;
            if (!Array.isArray(result.questions) || !result.questions.length || result.questions.some((question) =>
                !question.id || !question.title || !['single', 'multi'].includes(question.type) ||
                !Array.isArray(question.options) || !question.options.length ||
                question.options.some((option) => typeof option.value !== 'string' || typeof option.label !== 'string') ||
                (question.type === 'multi' && !(question.max_select > 0)))) {
                throw new Error('问卷格式暂时不可用，请重新加载。');
            }
            state.questions = result.questions;
            restoreGuestDraft();
            notice('assessmentNotice');
        } catch (error) {
            notice('assessmentNotice', error.message || '问卷加载失败，请重试。', true);
            $('retryQuestionsBtn').hidden = false;
        } finally {
            state.questionLoading = false;
            $('questionLoading').hidden = true;
            renderAssessment();
        }
    }

    function applySavedAnswers(result) {
        state.assessment = result.assessment || null;
        state.revision = Number(state.assessment?.revision || 0);
        if (state.assessment) state.answers = copyAnswers(state.assessment.answers);
        const firstInvalid = state.questions.findIndex((question) => !validAnswer(question));
        state.wizardOpen = !state.assessment || firstInvalid >= 0;
        state.current = Math.max(0, firstInvalid);
        state.conflict = false;
        state.conflictResult = null;
        renderAssessment();
    }

    function renderPlan(plan) {
        state.plan = plan || null;
        $('pathPreview').hidden = !plan;
        if (!plan) return;
        const stats = plan.stats || {};
        const level = plan.level || {};
        const recommendations = Array.isArray(plan.recommendations) ? plan.recommendations : [];
        $('planContent').innerHTML = `
            <div class="plan-summary">
                <span class="plan-level">起步建议 · ${escapeHtml(level.label || '从简单项目开始')}</span>
                <p class="plan-summary-text">${escapeHtml(plan.summary)}</p>
                <p class="plan-source">根据问卷自述与实际项目记录推荐，不代表能力测评，也不会调用 AI。</p>
            </div>
            <div class="project-record-stats" aria-label="实战项目记录">
                <span><strong>${escapeHtml(stats.projects ?? 0)}</strong> 个项目</span>
                <span><strong>${escapeHtml(stats.delivered ?? 0)}</strong> 个已交付</span>
                <span><strong>${escapeHtml(stats.acceptance_runs ?? 0)}</strong> 次验收记录</span>
            </div>
            <div class="recommendation-grid">${recommendations.map(renderRecommendation).join('')}</div>
            ${recommendations.length ? '' : '<p class="muted">暂时没有可用项目，可以先到实战任务室浏览。</p>'}`;
    }

    function renderRecommendation(project, index) {
        const status = ['not_started', 'in_progress', 'delivered'].includes(project.status) ? project.status : 'not_started';
        const statusLabels = { not_started: '待开始', in_progress: '进行中', delivered: '已交付' };
        const levelLabels = { starter: '零基础', basic: '基础练习', applied: '综合应用' };
        const step = { not_started: 0, in_progress: 1, delivered: 2 }[status];
        const params = new URLSearchParams(project.project_id
            ? { project: project.project_id } : { scenario: project.scenario_id, from: 'learning-plan' });
        if (project.language) params.set('language', project.language);
        const action = project.project_id ? (status === 'delivered' ? '回看交付' : '继续项目') : '查看项目';
        const skills = Array.isArray(project.skills) ? project.skills : [];
        const skillLabels = {basics: '基础语法', loops: '循环遍历', strings: '字符串', lists: '列表', dicts: '字典', sorting: '排序', testing: '边界测试', business: '业务规则'};
        const duration = project.duration || (project.estimated_minutes ? `${project.estimated_minutes} 分钟` : '按自己的节奏完成');
        return `<article class="recommendation-card status-${status}">
            <div class="recommendation-topline"><span class="project-order">项目 ${index + 1}</span><span class="project-status">${statusLabels[status]}</span></div>
            <h3>${escapeHtml(project.title)}</h3>
            <p class="project-subtitle">${escapeHtml(project.subtitle)}</p>
            <div class="project-meta"><span><i class="far fa-clock" aria-hidden="true"></i> ${escapeHtml(duration)}</span><span>${escapeHtml(levelLabels[project.level] || project.level || '简单项目')}</span></div>
            <div class="project-skills" aria-label="练习技能">${skills.map((skill) => `<span>${escapeHtml(skillLabels[skill] || skill)}</span>`).join('')}</div>
            <p class="project-goal"><strong>练什么</strong> ${escapeHtml(project.learning_goal)}</p>
            <p class="project-reason"><strong>为什么推荐</strong> ${escapeHtml(project.reason)}</p>
            <ol class="project-progress" aria-label="实际项目进度：${statusLabels[status]}">
                ${['待开始', '进行中', '已交付'].map((label, position) => `<li class="${position === step ? 'is-current' : (position < step ? 'is-done' : '')}">${label}</li>`).join('')}
            </ol>
            <a class="project-action" href="/task-room.html?${escapeHtml(params.toString())}">${action} <i class="fas fa-arrow-right" aria-hidden="true"></i></a>
        </article>`;
    }

    async function loadLearningPlan({ restoreAnswers = false, forConflict = false } = {}) {
        await questionsReady;
        if (!state.questions.length || !state.authenticated || state.planLoading) return;
        state.planLoading = true;
        $('planLoadError').hidden = true;
        notice('planNotice', '正在同步实战任务室的项目进度…');
        updateControls();
        try {
            const response = await fetch('/api/learning-plan', { cache: 'no-store' });
            const packet = await response.json();
            const result = packet.data || packet;
            if (response.status === 401) {
                state.authenticated = false;
                saveGuestDraft();
                showLoginNotice('登录已失效，当前答案仍保留。');
                return;
            }
            if (!response.ok) throw new Error(UserSession.apiErrorMessage(packet, '学习计划暂时无法读取。'));
            if (forConflict) state.conflictResult = result;
            else if (restoreAnswers) applySavedAnswers(result);
            renderPlan(result.plan);
            notice('planNotice', '已同步最新项目进度。');
        } catch (error) {
            $('planLoadErrorText').textContent = error.message || '读取失败，已保留当前答案，请重试。';
            $('planLoadError').hidden = false;
            notice('planNotice', '同步失败，已保留当前推荐和答案。', true);
        } finally {
            state.planLoading = false;
            renderAssessment();
            updateControls();
        }
    }

    async function submitAssessment(event) {
        event?.preventDefault();
        if (busy() || state.conflict || !state.questions.length) return;
        const firstInvalid = state.questions.findIndex((question) => !validAnswer(question));
        if (firstInvalid >= 0) {
            goToQuestion(firstInvalid);
            return showQuestionError('请完成这道题后再保存。');
        }
        if (!state.authenticated) {
            saveGuestDraft();
            return showLoginNotice('请先登录再保存问卷和项目推荐，当前答案已在本次浏览中保留。');
        }
        state.submitting = true;
        notice('assessmentNotice', '正在保存问卷并整理项目推荐…');
        updateControls();
        try {
            const answers = Object.fromEntries(state.questions.map((question) => [question.id, state.answers[question.id]]));
            const response = await UserSession.csrfFetch('/api/learning-plan', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ answers, revision: state.revision })
            });
            const packet = await response.json();
            const result = packet.data || packet;
            if (response.status === 409) {
                state.conflict = true;
                state.conflictResult = null;
                notice('assessmentNotice', '保存时发现新版本。当前填写内容未被替换。', true);
                await loadLearningPlan({ forConflict: true });
                return;
            }
            if (!response.ok) throw new Error(UserSession.apiErrorMessage(packet, '问卷保存失败，请重试。'));
            applySavedAnswers(result);
            renderPlan(result.plan);
            notice('assessmentNotice', '问卷已保存。选择一个项目，查看要求后再开始。');
            notice('planNotice');
            try { sessionStorage.removeItem(GUEST_DRAFT_KEY); } catch (_) { /* Optional draft storage. */ }
        } catch (error) {
            if (error.code === 'AUTH_REQUIRED') {
                state.authenticated = false;
                saveGuestDraft();
                showLoginNotice('登录已失效，当前答案已保留，请登录后继续保存。');
            } else {
                notice('assessmentNotice', `${error.message || '保存失败'} 当前答案已保留，可以再次提交。`, true);
            }
        } finally {
            state.submitting = false;
            renderAssessment();
            updateControls();
        }
    }

    function initAssessment() {
        $('questionContainer').addEventListener('click', handleOptionSelect);
        $('assessmentForm').addEventListener('submit', submitAssessment);
        $('prevBtn').addEventListener('click', () => goToQuestion(state.current - 1));
        $('nextBtn').addEventListener('click', () => {
            if (!validAnswer(state.questions[state.current])) return showQuestionError('请先选择一项。');
            goToQuestion(state.current + 1);
        });
        $('retakeBtn').addEventListener('click', () => {
            state.answers = {};
            state.current = 0;
            state.wizardOpen = true;
            notice('assessmentNotice', '重新填写后保存会更新推荐；原问卷在保存成功前保留。');
            renderAssessment();
            $('currentQuestionTitle').focus({ preventScroll: true });
        });
        $('cancelRetakeBtn').addEventListener('click', () => {
            applySavedAnswers({ assessment: state.assessment });
            notice('assessmentNotice', '已返回原来的问卷结果。');
        });
        $('refreshPlanBtn').addEventListener('click', () => loadLearningPlan());
        $('retryPlanBtn').addEventListener('click', () => loadLearningPlan({ restoreAnswers: !state.assessment && !Object.keys(state.answers).length, forConflict: state.conflict }));
        $('retryQuestionsBtn').addEventListener('click', async () => {
            questionsReady = fetchQuestions();
            await questionsReady;
            if (state.authenticated) await loadLearningPlan({ restoreAnswers: true });
        });
        $('retryConflictBtn').addEventListener('click', () => loadLearningPlan({ forConflict: true }));
        $('useLatestAnswersBtn').addEventListener('click', () => {
            if (!state.conflictResult) return;
            applySavedAnswers(state.conflictResult);
            notice('assessmentNotice', '已读取最新保存的问卷；可以重新填写。');
        });
        $('keepDraftAnswersBtn').addEventListener('click', () => {
            if (!state.conflictResult) return;
            state.assessment = state.conflictResult.assessment || null;
            state.revision = Number(state.assessment?.revision || 0);
            state.conflict = false;
            state.conflictResult = null;
            notice('assessmentNotice', '已保留当前答案。请再次点击“保存并推荐简单项目”确认更新。');
            renderAssessment();
        });
    }

    async function fetchLearningOverview() {
        try {
            const response = await fetch('/api/learning_overview');
            const result = await response.json();
            if (!response.ok || !result.success) throw new Error('概览暂时不可用');
            $('totalSolved').textContent = result.data.total_solved;
            $('learningHours').textContent = result.data.learning_hours + 'h';
            $('accuracyRate').textContent = result.data.accuracy + '%';
            currentOverviewSignature = [result.data.total_solved, result.data.learning_hours, result.data.accuracy].join(':');
        } catch (_) {
            ['totalSolved', 'learningHours', 'accuracyRate'].forEach((id) => { $(id).textContent = '—'; });
        }
    }

    async function fetchLeaderboard() {
        const container = $('leaderboardContainer');
        try {
            const response = await fetch('/api/leaderboard');
            const result = await response.json();
            if (!response.ok) throw new Error('英雄榜暂时无法读取。');
            if (!result.success || !result.data?.length) {
                container.innerHTML = '<p class="muted">英雄榜正在等待第一位英雄的诞生！</p>';
                return;
            }
            container.innerHTML = `<table class="leaderboard-table"><thead><tr><th>排名</th><th>用户</th><th>解题数</th><th>积分</th><th>正确率</th><th>学习时长 (h)</th></tr></thead><tbody>${result.data.map((user) => `
                <tr><td class="rank">${escapeHtml(user.rank)}</td><td class="username">${escapeHtml(user.username)}</td><td>${escapeHtml(user.solved_count)}</td><td>${escapeHtml(user.points)}</td><td>${escapeHtml(user.accuracy)}%</td><td>${escapeHtml(user.learning_hours)}</td></tr>`).join('')}</tbody></table>`;
        } catch (error) {
            container.innerHTML = `<p class="error-message">${escapeHtml(error.message)}</p>`;
        }
    }

    function getAnalysisCacheKey() {
        return `aiLearningAnalysis:${currentAnalysisUserKey}:${currentOverviewSignature || 'unknown'}`;
    }

    function readCachedAiAnalysis() {
        try {
            const key = getAnalysisCacheKey();
            const cached = JSON.parse(localStorage.getItem(key) || 'null');
            if (!cached?.content || !cached.savedAt || Date.now() - cached.savedAt > AI_ANALYSIS_CACHE_TTL_MS) {
                localStorage.removeItem(key);
                return null;
            }
            return cached;
        } catch (_) { return null; }
    }

    function renderAiAnalysis(content = '', fromCache = false, error = '') {
        const container = $('aiAnalysisContainer');
        container.innerHTML = `<div class="card-body">
            <p class="muted ai-intro">按需分析最近的刷题记录。点击按钮会请求已配置的 AI 服务；上方项目推荐不调用 AI。</p>
            ${fromCache ? '<p class="cache-note">已展示本机缓存的最近一次分析，未发起新的 AI 请求。</p>' : ''}
            ${error ? `<p class="error-message" role="alert">${escapeHtml(error)}</p>` : ''}
            <div class="path-content" id="ai-stream-content"${content ? '' : ' hidden'}></div>
            <div class="analysis-cache-actions"><button type="button" class="refresh-analysis-btn" id="generateAiAnalysisBtn"${state.aiLoading ? ' disabled' : ''}>${state.aiLoading ? '正在生成…' : (content ? '重新生成 AI 分析' : '生成 AI 分析')}</button></div>
        </div>`;
        if (content) $('ai-stream-content').innerHTML = SafeContent.markdown(content);
        $('generateAiAnalysisBtn').addEventListener('click', fetchAiAnalysisStream);
    }

    async function fetchAiAnalysisStream() {
        if (!state.authenticated || state.aiLoading) return;
        state.aiLoading = true;
        renderAiAnalysis();
        const contentDiv = $('ai-stream-content');
        let fullContent = '';
        let reader;
        try {
            const response = await fetch('/api/ai_learning_analysis_stream');
            if (response.status === 401) throw new Error('登录已失效，请登录后重新生成。');
            if (!response.ok || !response.body) throw new Error('AI 分析暂时不可用，请稍后重试。');
            reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            const consumeLine = (line) => {
                if (!line.startsWith('data:')) return;
                const raw = line.substring(5).trim();
                if (!raw || raw === '[DONE]') return;
                let data;
                try { data = JSON.parse(raw); } catch (_) { return; }
                if (data.error) throw new Error(typeof data.error === 'string' ? data.error : 'AI 分析生成失败。');
                if (data.content) {
                    fullContent += data.content;
                    contentDiv.hidden = false;
                    contentDiv.innerHTML = SafeContent.markdown(fullContent);
                }
            };
            while (true) {
                const { done, value } = await reader.read();
                buffer += decoder.decode(value, { stream: !done });
                const lines = buffer.split('\n');
                buffer = lines.pop();
                lines.forEach(consumeLine);
                if (done) { if (buffer) consumeLine(buffer); break; }
            }
            if (!fullContent) throw new Error('AI 服务未返回分析内容，请重试。');
            try { localStorage.setItem(getAnalysisCacheKey(), JSON.stringify({ content: fullContent, savedAt: Date.now() })); } catch (_) { /* Optional cache. */ }
            state.aiLoading = false;
            renderAiAnalysis(fullContent);
        } catch (error) {
            if (reader) await reader.cancel().catch(() => {});
            state.aiLoading = false;
            renderAiAnalysis(fullContent, false, error.message || '生成失败，请重试。');
        }
    }

    function showGuestAnalysisState() {
        state.authenticated = false;
        ['totalSolved', 'accuracyRate', 'learningHours'].forEach((id) => { $(id).textContent = '—'; });
        $('aiAnalysisContainer').innerHTML = `<div class="card-body"><p class="muted">登录后可以查看自己的刷题记录，或主动生成 AI 学习分析。</p><a class="catalog-link" href="${escapeHtml(UserSession.loginUrl())}" data-return-to-current="true">登录后返回此页 <i class="fas fa-arrow-right" aria-hidden="true"></i></a></div>`;
    }

    document.addEventListener('DOMContentLoaded', () => {
        initAssessment();
        questionsReady = fetchQuestions();
        UserSession.init({
            showRecords: true,
            onRecordsClick: () => { window.location.href = '/practice.html'; },
            onAuthenticated: async (user) => {
                state.authenticated = true;
                currentAnalysisUserKey = user?.username || String(user?.id || 'user');
                await Promise.allSettled([fetchLearningOverview(), loadLearningPlan({ restoreAnswers: true })]);
                const cached = readCachedAiAnalysis();
                renderAiAnalysis(cached?.content || '', Boolean(cached));
            },
            onGuest: showGuestAnalysisState
        });
        fetchLeaderboard();
        // Browser history restoration syncs delivery progress without replacing an open draft.
        window.addEventListener('pageshow', (event) => { if (event.persisted && state.authenticated) loadLearningPlan(); });
    });
})();
