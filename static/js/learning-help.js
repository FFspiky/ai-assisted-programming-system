(() => {
    const labels = {1: '概念线索', 2: '定位与解释', 3: '局部修改', 4: '完整参考'};
    let state = {mode: 'learning', revision: -1, ready: false, level: 1, epoch: 0};
    let user = null, loading = false;
    const acknowledged = new Set();
    const modes = [...document.querySelectorAll('[data-help-mode]')];
    const levels = [...document.querySelectorAll('[data-help-select]')];
    const status = document.getElementById('helpSettingsStatus');
    const blocked = () => Boolean(window.PracticeTransfer?.blocksAI);

    function sync() {
        modes.forEach(select => { select.value = state.mode; select.disabled = blocked() || !user || !state.ready; });
        levels.forEach(select => { select.value = String(state.mode === 'free' ? 4 : state.level); select.disabled = blocked() || !state.ready || state.mode === 'free'; });
        document.getElementById('completionStatus').textContent = blocked() ? '本轮收起 AI 补全' : state.mode === 'free' && state.ready
            ? '自动补全已开启 · Tab 接受' : '自动补全已关闭';
    }
    function notify(type = 'practice:help-settings') {
        state.epoch += 1;
        sync();
        window.dispatchEvent(new CustomEvent(type, {detail: {...state}}));
    }
    function apply(data) {
        if (!['learning', 'free'].includes(data?.mode) || !Number.isInteger(data.revision)) throw new Error('帮助设置格式不正确');
        const changed = !state.ready || state.mode !== data.mode || state.revision !== data.revision;
        state = {...state, ...data, ready: true};
        status.textContent = '';
        if (changed) notify(); else sync();
    }
    async function load() {
        if (!user || loading) return;
        loading = true;
        try {
            const response = await fetch('/api/help-settings', {cache: 'no-store'});
            const result = await response.json();
            if (!response.ok || !result.success) throw new Error(UserSession.apiErrorMessage(result));
            apply(result.data);
        } catch (error) {
            state.ready = false;
            notify();
            status.textContent = '帮助设置读取失败，请刷新页面重试。';
        } finally { loading = false; }
    }
    modes.forEach(select => select.addEventListener('change', async () => {
        if (blocked()) { sync(); window.PracticeTransfer.notifyBlocked?.(); return; }
        const mode = select.value;
        state.ready = false;
        loading = true;
        notify();
        status.textContent = '正在切换…';
        try {
            const response = await UserSession.csrfFetch('/api/help-settings', {
                method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({mode})
            });
            const result = await response.json();
            if (!response.ok || !result.success) throw new Error(UserSession.apiErrorMessage(result));
            apply(result.data);
            try { localStorage.setItem('codelab:help-mode', String(Date.now())); } catch (_) { /* Sync again on focus. */ }
        } catch (error) {
            status.textContent = error.message;
        } finally {
            loading = false;
            if (!state.ready) load();
        }
    }));
    levels.forEach(select => select.addEventListener('change', () => {
        state.level = Number(select.value);
        notify('practice:help-level');
    }));
    window.addEventListener('practice:user', event => {
        user = event.detail;
        state.ready = false;
        notify();
        if (user) load();
    });
    window.addEventListener('auth:required', () => { user = null; state.ready = false; notify(); });
    window.addEventListener('focus', load);
    window.addEventListener('storage', event => { if (event.key === 'codelab:help-mode') load(); });
    window.addEventListener('practice:transfer-mode', () => notify());

    async function acknowledge(id) {
        if (!id || acknowledged.has(Number(id))) return;
        try {
            const response = await UserSession.csrfFetch(`/api/help/${id}/shown`, {method: 'POST'});
            if (response.ok) acknowledged.add(Number(id));
        } catch (_) { /* A display acknowledgment must not interrupt practice. */ }
    }
    function element(tag, text, className = '') {
        const node = document.createElement(tag);
        node.textContent = text;
        node.className = className;
        return node;
    }
    function render(record, target, focusEvidence) {
        const result = record.result;
        const card = element('article', '', 'finding-card help-result');
        card.dataset.helpStatus = result.status;
        if (result.status === 'insufficient_evidence') card.append(element('span', '公开证据不足', 'hypothesis-tag'));
        else if (record.level === 2) card.append(element('span', '可能原因', 'hypothesis-tag'));
        else card.append(element('span', record.level === 1 ? 'AI 线索 · 自主思考' : 'AI 建议 · 待验证', 'hypothesis-tag'));
        card.append(element('p', result.summary, 'diagnosis-summary'));
        if (result.explanation) card.append(element('p', result.explanation));
        if (focusEvidence && result.evidence_ids?.length) {
            const link = element('button', '查看依据' + (result.lines.length ? ' · 第 ' + result.lines.join('、') + ' 行' : ''), 'evidence-button evidence-link');
            link.type = 'button';
            link.addEventListener('click', () => focusEvidence(result.evidence_ids, result.lines));
            card.append(link);
        }
        if (result.code && !record.proposal) {
            card.append(element('pre', result.code, 'help-code'));
            card.append(element('p', '建议尚未运行，修改后请重新提交验证。', 'panel-note'));
        }
        window.PracticeReview?.attach(record, card);
        target.append(card);
    }
    window.LearningHelpUI = {get: () => ({...state, ready: state.ready && !blocked()}), labels, render, acknowledge};
    sync();
})();
