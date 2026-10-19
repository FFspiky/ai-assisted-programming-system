/* A related problem attempt keeps the ordinary editor and its language draft.
 * The server-owned attempt is the authority; a query string never proves one. */
(() => {
    'use strict';
    const byId = id => document.getElementById(id);
    const panel = byId('practiceTransfer');
    if (!panel) return;
    const language = byId('languageSelector');
    const editor = byId('codeInput');
    const params = new URLSearchParams(location.search);
    const sessionId = params.get('co_create_session') || params.get('learning_session');
    const attemptId = params.get('transfer_attempt');
    const requestedProblem = params.get('problem');
    const requestedLanguage = params.get('language');
    const validId = value => typeof value === 'string' && /^[a-zA-Z0-9_-]{1,100}$/.test(value);
    let eligible = validId(sessionId) && validId(attemptId) && !!requestedProblem
        && ['python', 'cpp'].includes(requestedLanguage);
    let active = false, pending = eligible, user = null, problem = null;
    let sequence = 0, record = null, linking = false, lastSubmission = null;
    let nonFresh = false;
    const queue = [];
    const endpoint = eligible ? `/api/co-create/sessions/${encodeURIComponent(sessionId)}/learning/transfer/${encodeURIComponent(attemptId)}` : '';
    const status = byId('transferStatus');
    const help = byId('transferHelpUsage');
    const retry = byId('transferLinkSubmission');
    const pet = byId('aiToggleBtn');
    const petLabel = pet?.getAttribute('aria-label');
    const apiError = (data, fallback) => window.UserSession?.apiErrorMessage(data, fallback) || fallback;

    function notifyBlocked() {
        if (!active && !pending) return;
        status.textContent = pending ? '正在确认这次关联练习，请稍候。'
            : '这次先按自己的思路尝试。需要帮助时可以退出普通练习，并如实记录帮助情况。';
    }
    window.PracticeTransfer = {
        get active() { return active; },
        get pending() { return pending; },
        get blocksAI() { return active || pending; },
        get context() {
            return active ? {session_id:sessionId, attempt_id:attemptId,
                problem_id:record.attempt.problem_id, language:record.attempt.language} : null;
        },
        notifyBlocked,
    };

    function mode(nextActive, nextPending) {
        const changed = active !== nextActive || pending !== nextPending;
        active = nextActive; pending = nextPending;
        document.body.classList.toggle('practice-transfer-active', active);
        panel.hidden = !active && !pending && !panel.dataset.notice;
        byId('transferActiveContent').hidden = !active;
        byId('transferPending').hidden = !pending;
        if (pet && active) {
            pet.setAttribute('aria-label', '达菲郁陪你独立尝试，聊天暂时收起');
            pet.setAttribute('aria-expanded', 'false');
        } else if (pet && petLabel) pet.setAttribute('aria-label', petLabel);
        updateRetry();
        if (changed) window.dispatchEvent(new CustomEvent('practice:transfer-mode', {detail:{active,pending}}));
    }
    function updateRetry() {
        retry.disabled = !active || !lastSubmission || linking;
        retry.textContent = linking ? '正在关联提交…' : queue.length ? '重试关联已完成的提交' : '保存帮助情况 / 重新关联';
        byId('transferFollowup').hidden = !active || !lastSubmission;
        byId('transferPhase').textContent = pending ? '正在确认' : !active ? '普通练习' : linking ? '正在关联' : queue.length ? '待关联复盘' : lastSubmission ? '已有正式提交' : '独立练习中';
        if(lastSubmission){
            const saved=record?.attempt.submissions?.find(s=>s.submission_id===lastSubmission);
            byId('transferSubmissionSummary').textContent=`正式提交 #${lastSubmission}${saved?.submission?.status?' · '+saved.submission.status:''} · ${queue.length?'正在等待关联':'判题结果以本次实际提交为准'}`;
        }
    }
    function ordinaryURL() {
        const url = new URL(location.href);
        for (const key of ['co_create_session','learning_session','transfer_attempt']) url.searchParams.delete(key);
        return url.pathname + url.search + url.hash;
    }
    function leave(message = '已回到普通练习。当前代码与本语言草稿保留。') {
        eligible = false; sequence += 1;
        panel.dataset.notice = 'true';
        mode(false, false);
        history.replaceState(null, '', ordinaryURL());
        byId('transferPending').hidden = true;
        status.textContent = message;
    }
    function fail(message) {
        eligible = false; sequence += 1;
        panel.dataset.notice = 'true'; mode(false, false);
        history.replaceState(null, '', ordinaryURL());
        status.textContent = `${message} 普通练习与原草稿仍可使用。`;
    }
    function problemChanged(data) {
        return data?.attempt?.status === 'target_changed'
            || data?.recap?.session?.problem_changed === true;
    }
    function matches(data) {
        return data && data.session_id === sessionId && data.attempt
            && !problemChanged(data)
            && String(data.attempt.id) === attemptId
            && data.attempt.problem_id === requestedProblem
            && data.attempt.language === requestedLanguage
            && data.source?.session_id === sessionId
            && data.source.language === requestedLanguage
            && Number.isInteger(data.revision) && data.revision >= 0
            && problem?.id === requestedProblem && language.value === requestedLanguage;
    }
    function setRecapLink(value) {
        const fallback = `/co-create.html?session=${encodeURIComponent(sessionId)}&problem=${encodeURIComponent(record.source.problem_id)}&language=${encodeURIComponent(requestedLanguage)}`;
        let target = new URL(fallback, location.origin);
        try {
            const supplied = new URL(value, location.origin);
            if (supplied.origin === location.origin && supplied.pathname === '/co-create.html') target = supplied;
        } catch (_) { /* Keep the known local workbench route. */ }
        byId('transferRecap').href = target.pathname + target.search + target.hash;
    }
    function warning() {
        byId('transferPriorWork').hidden = !nonFresh;
        byId('transferPriorBadge').hidden = !nonFresh;
        byId('transferPriorWork').textContent = '本题已有草稿或历史提交，原内容已保留。本轮并非全新起点，复盘时请一并说明。';
    }
    function inspectDraft() {
        try {
            const saved = JSON.parse(localStorage.getItem(`codelab:draft:v2:${user.id}:${requestedProblem}:${requestedLanguage}`) || 'null');
            if (saved && typeof saved.code === 'string' && saved.code.trim()) nonFresh = true;
        } catch (_) { /* Draft access must never block a valid attempt. */ }
        if (editor.value.trim() && editor.dataset.untouchedTemplate !== 'true') nonFresh = true;
        warning();
    }
    async function read() {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 15000);
        try {
            const response = await fetch(endpoint, {cache:'no-store',signal:controller.signal});
            const data = await response.json();
            if (!response.ok || !data.success) {
                const error = new Error(apiError(data, '关联练习读取失败。'));
                error.status = response.status;
                throw error;
            }
            return data.data;
        } finally { clearTimeout(timer); }
    }
    async function verify() {
        if (!eligible || !user || !problem || record || pending && panel.dataset.verifying) return;
        if (problem.id !== requestedProblem || language.value !== requestedLanguage) {
            leave('题目或语言已切换，已恢复普通练习；本次关联练习没有追加这次操作。');
            return;
        }
        const ticket = ++sequence;
        panel.dataset.verifying = 'true'; mode(false, true);
        try {
            const data = await read();
            if (ticket !== sequence || !eligible) return;
            if (problemChanged(data)) { fail('来源题或关联题的题面、用例已更新，本次尝试保留为历史记录。'); return; }
            if (!matches(data)) { fail('关联记录与当前题目、语言不匹配，未进入独立尝试。'); return; }
            record = data;
            byId('transferSource').textContent = `承接「${data.source.title}」`;
            byId('transferTarget').textContent = data.attempt.title;
            byId('transferLanguage').textContent = {python:'Python',cpp:'C++'}[requestedLanguage];
            setRecapLink(data.recap_url);
            const saved=(data.attempt.submissions || []).filter(s=>Number.isInteger(s.submission_id) && s.record_available!==false && s.submission).at(-1);
            if(saved){lastSubmission=saved.submission_id;help.value=['none','hint','full','unspecified'].includes(saved.help_usage)?saved.help_usage:'unspecified';}
            mode(true, false);
            status.textContent = saved?`已恢复本次尝试的正式提交 #${saved.submission_id}。可继续练习，或在结果下方补记帮助情况。`:'编写自己的实现，再正式提交。结果会关联到共创复盘。';
            inspectDraft();
            if (Number(data.attempt.existing_submission_count) > 0) { nonFresh = true; warning(); }
            // The ordinary latest-submission endpoint is read only. It never loads
            // code into the editor, and helps disclose an existing starting point.
            fetch(`/api/problems/${encodeURIComponent(requestedProblem)}/latest-submission?language=${encodeURIComponent(requestedLanguage)}`, {cache:'no-store'})
                .then(response => response.json()).then(result => {
                    if (ticket !== sequence || !active) return;
                    if (result.success && result.data?.submission_id) { nonFresh = true; warning(); }
                }).catch(() => { /* The attempt remains usable without this optional notice. */ });
            if (queue.length) drain();
        } catch (error) {
            if (ticket === sequence) fail(error.message || '暂时无法确认关联练习。');
        } finally { delete panel.dataset.verifying; }
    }
    async function linkOnce(id, helpUsage, ticket, retried = false) {
        const response = await UserSession.csrfFetch(`${endpoint}/submission`, {
            method:'POST', headers:{'Content-Type':'application/json'},
            body:JSON.stringify({revision:record.revision, submission_id:id, help_usage:helpUsage}),
        });
        const result = await response.json();
        if (ticket !== sequence || !active) return false;
        if (response.status === 409 && !retried) {
            const current = await read();
            if (ticket !== sequence || !active) return false;
            if (problemChanged(current)) {
                fail('来源题或关联题的题面、用例已更新，本次尝试保留为历史记录。');
                return false;
            }
            if (!matches(current)) throw new Error('关联记录已变化，请返回复盘查看。');
            record = current;
            return linkOnce(id, helpUsage, ticket, true);
        }
        if (!response.ok || !result.success) throw new Error(apiError(result, '关联提交失败。'));
        const data = result.data;
        if (Number.isInteger(data?.revision)) record.revision = data.revision;
        if (data?.attempt) record.attempt = data.attempt;
        return true;
    }
    async function drain() {
        if (!active || linking || !queue.length) return;
        const ticket = sequence;
        linking = true; updateRetry();
        try {
            while (active && ticket === sequence && queue.length) {
                const item = queue[0];
                status.textContent = `提交 #${item.id} 已完成判题，正在关联复盘…`;
                byId('transferFollowupStatus').textContent=status.textContent;
                if (!await linkOnce(item.id, item.helpUsage, ticket)) return;
                queue.shift();
                const labels = {none:'自述未使用帮助',hint:'自述使用线索或局部帮助',full:'自述看过完整参考',unspecified:'帮助情况尚未填写'};
                status.textContent = `提交 #${item.id} 已关联 · ${labels[item.helpUsage]}。判题以本次实际提交为准，不代表已掌握。`;
                byId('transferFollowupStatus').textContent=status.textContent;
            }
        } catch (error) {
            if (ticket === sequence && active){status.textContent = `判题结果已经保存，但关联未完成：${error.message} 可重试关联，无需重新提交判题。`;byId('transferFollowupStatus').textContent=status.textContent;}
        } finally { linking = false; updateRetry(); }
    }
    function enqueue(id, helpUsage = help.value) {
        if (!Number.isInteger(id) || id <= 0) return;
        lastSubmission = id;
        const waiting = queue.find(item => item.id === id);
        if (waiting) waiting.helpUsage = helpUsage;
        else queue.push({id, helpUsage});
        updateRetry();
        if (active) drain();
    }
    window.addEventListener('practice:user', event => {
        if (user && user.id !== event.detail?.id && (active || pending)) {
            user = event.detail; leave('登录账号已变化，已恢复普通练习。请从本人共创复盘重新进入。'); return;
        }
        user = event.detail;
        if (!user && eligible) { fail('登录后可从本人共创复盘进入关联练习。'); return; }
        verify();
    });
    window.addEventListener('practice:problem', event => {
        problem = event.detail;
        if ((active || pending) && problem?.id !== requestedProblem) {
            leave('题目已变化，已恢复普通练习。当前草稿保留。'); return;
        }
        verify();
    });
    language.addEventListener('change', () => {
        if (active || pending) leave('语言已切换，已恢复普通练习。各语言草稿分别保留；请回复盘重新选择独立尝试。');
    });
    window.addEventListener('auth:required', () => {
        if (active || pending) leave('登录状态已变化，已恢复普通练习。当前代码保留。');
    });
    window.addEventListener('practice:submission', event => {
        if (!eligible || !(active || pending)) return;
        const submission = event.detail;
        if (submission?.language && submission.language !== requestedLanguage) return;
        if (submission?.problem_id && submission.problem_id !== requestedProblem) return;
        if (language.value !== requestedLanguage || problem?.id !== requestedProblem) return;
        if(submission?.submission_id!==lastSubmission)help.value='unspecified';
        enqueue(submission?.submission_id);
    });
    retry.addEventListener('click', () => {
        if (!active || !lastSubmission || linking) return;
        enqueue(lastSubmission);
    });
    help.addEventListener('change', () => {
        if (!active) return;
        status.textContent = lastSubmission ? '帮助情况已选择。点击“保存帮助情况 / 重新关联”记录本人的自述。'
            : '帮助情况将在下一次正式提交时记录。这是本人自述，不证明站外无帮助。';
        byId('transferFollowupStatus').textContent=status.textContent;
    });
    byId('transferExit').addEventListener('click', () => leave());
    pet?.addEventListener('click', event => {
        if (!active && !pending) return;
        event.preventDefault(); event.stopImmediatePropagation(); notifyBlocked();
    }, true);
    // Capture existing AI entry activation as well as hiding it. Root controller
    // guards also prevent automatic completion and direct keyboard/function calls.
    document.addEventListener('click', event => {
        if (!active && !pending) return;
        if (!event.target.closest('#optimizeBtn,#coCreateBtn,#helpActions,#sendMessage,#attachPracticeContext')) return;
        event.preventDefault(); event.stopImmediatePropagation(); notifyBlocked();
    }, true);
    mode(false, pending);
})();
