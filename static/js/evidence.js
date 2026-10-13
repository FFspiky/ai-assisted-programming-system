(() => {
    const byId = id => document.getElementById(id);
    const editor = byId('codeInput');
    const language = byId('languageSelector');
    const cases = byId('evidenceCases');
    const diagnosisContent = byId('diagnosisContent');
    const helpButtons = [...document.querySelectorAll('[data-help-level]')];
    let historySequence = 0;
    let submission = null, user = null, userReady = false, problem = null;
    let controller = null, sequence = 0, restoreSequence = 0, edited = false;
    let activeLanguage = language.value;

    function node(tag, text, className = '') {
        const element = document.createElement(tag);
        if (text !== undefined) element.textContent = text;
        element.className = className;
        return element;
    }
    function draftKey(lang = activeLanguage) {
        return `codelab:draft:v2:${user?.id || 'guest'}:${getCurrentProblemId()}:${lang}`;
    }
    function saveDraft() {
        if (!userReady) return;
        try {
            localStorage.setItem(draftKey(), JSON.stringify({code: editor.value, input: byId('customInput').value}));
            byId('draftStatus').textContent = '草稿已保存';
        } catch (_) { byId('draftStatus').textContent = '浏览器无法保存草稿，请手动复制代码'; }
    }
    function restoreDraft() {
        try {
            const pending = JSON.parse(sessionStorage.getItem('codelab:login-draft') || 'null');
            if (user && pending && pending.problem === getCurrentProblemId() && pending.language === activeLanguage
                && (!pending.user_id || pending.user_id === user.id)) {
                localStorage.setItem(draftKey(), JSON.stringify({code:pending.code,input:pending.input}));
                sessionStorage.removeItem('codelab:login-draft');
            }
            const saved = JSON.parse(localStorage.getItem(draftKey()) || 'null');
            if (saved && typeof saved.code === 'string') {
                editor.value = saved.code;
                byId('customInput').value = saved.input || '';
                renderGhostLayer();
                byId('draftStatus').textContent = '已恢复本题草稿';
                return true;
            }
        } catch (_) { /* A broken draft must not prevent editing. */ }
        return false;
    }
    function markStale() {
        byId('evidenceStale').hidden = !submission || (editor.value === submission.code && language.value === submission.language);
        updateButtons();
    }
    function cancelPending() {
        sequence += 1;
        controller?.abort();
        controller = null;
        byId('cancelDiagnosisBtn').hidden = true;
        updateButtons();
    }
    function clearFocus() {
        cases.querySelectorAll('.is-selected').forEach(item => item.classList.remove('is-selected'));
        byId('submissionCode').querySelectorAll('.is-selected').forEach(item => item.classList.remove('is-selected'));
        byId('submissionCodePanel').open = false;
    }
    function focusEvidence(ids, lines) {
        cases.querySelectorAll('.case-card').forEach(card => card.classList.toggle('is-selected', ids.includes(card.dataset.caseId)));
        byId('submissionCodePanel').open = true;
        byId('submissionCode').querySelectorAll('.snapshot-line').forEach(line => line.classList.toggle('is-selected', lines.includes(Number(line.dataset.line))));
        const target = byId('submissionCode').querySelector('.is-selected');
        target?.scrollIntoView({behavior: 'smooth', block: 'nearest'});
        if (editor.value === submission.code && lines.length) {
            const chunks = editor.value.split('\n');
            const first = Math.min(...lines) - 1;
            const start = chunks.slice(0, first).reduce((sum, text) => sum + text.length + 1, 0);
            editor.focus({preventScroll: true});
            editor.setSelectionRange(start, start + chunks[first].length);
        }
    }
    function updateButtons() {
        const applicable = submission?.evidence && ['Wrong Answer', 'Runtime Error', 'Compile Error'].includes(submission.status);
        byId('helpActions').hidden = !applicable;
        const stale = submission && (editor.value !== submission.code || language.value !== submission.language);
        helpButtons.forEach(button => {
            button.disabled = !applicable || stale || !!controller || !LearningHelpUI.get().ready;
            button.title = stale ? '代码已修改，请重新提交后获取新提示' : '';
        });
    }
    function showHelp(record, open = false) {
        let details = diagnosisContent.querySelector(`[data-help-id="${record.id}"]`);
        if (!details) {
            details = node('details', undefined, 'help-history');
            details.dataset.helpId = String(record.id);
            const title = LearningHelpUI.labels[record.level];
            details.append(node('summary', title + ' · ' + (record.shown_at ? '已查看' : '已生成')));
            LearningHelpUI.render(record, details, focusEvidence);
            details.addEventListener('toggle', () => {
                if (details.open) {
                    LearningHelpUI.acknowledge(record.id);
                    details.querySelector('summary').textContent = title + ' · 已查看';
                }
            });
            diagnosisContent.append(details);
        }
        if (open) {
            diagnosisContent.querySelectorAll('details').forEach(item => { item.open = item === details; });
            details.open = true;
            LearningHelpUI.acknowledge(record.id);
        }
    }
    async function restoreHelp() {
        const ticket = ++historySequence;
        const id = submission?.submission_id, help = LearningHelpUI.get();
        if (!id || !help.ready) return;
        try {
            const response = await fetch(`/api/submissions/${id}/help`, {cache: 'no-store'});
            const result = await response.json();
            if (ticket !== historySequence || id !== submission?.submission_id || help.epoch !== LearningHelpUI.get().epoch) return;
            if (!response.ok || !result.success) throw new Error(UserSession.apiErrorMessage(result));
            result.data.records.forEach(record => showHelp(record));
        } catch (_) {
            if (ticket === historySequence) byId('diagnosisStatus').textContent = '历史提示暂时无法读取，可点击对应层级重试。';
        }
    }
    function showSubmission(data) {
        clearFocus();
        cancelPending();
        submission = data?.submission_id ? data : null;
        byId('submissionResults').hidden = !submission;
        cases.replaceChildren();
        diagnosisContent.replaceChildren();
        byId('submissionCode').replaceChildren();
        byId('submissionCodePanel').hidden = !submission;
        if (!submission) {
            byId('evidenceSummary').textContent = '';
            updateButtons();
            byId('diagnosisStatus').textContent = user ? '请先提交一段代码。' : '登录后可以保存提交并查看 AI 诊断。';
            markStale();
            return;
        }
        outputContent.replaceChildren();
        const evidence = submission.evidence;
        byId('evidenceSummary').textContent = evidence
            ? `提交 #${submission.submission_id} · ${submission.status} · 已执行 ${evidence.executed}/${evidence.total}，未执行 ${evidence.not_run}`
            : '这次历史提交没有证据快照，请重新提交。';
        (evidence?.cases || []).forEach(item => {
            const card = node('article', undefined, 'case-card ' + (item.passed ? 'case-pass' : 'case-fail'));
            card.dataset.caseId = item.id;
            card.append(node('h3', `用例 ${item.index} · ${item.status}`));
            if (item.is_public) {
                [['输入', item.input], ['预期输出', item.expected_output], ['实际输出', item.actual_output]].forEach(([label, value]) => {
                    const block = node('div', undefined, 'case-value');
                    block.append(node('span', label), node('pre', value || '（空）'));
                    card.append(block);
                });
                if (item.error) card.append(node('pre', item.error, 'case-error'));
                if (item.time != null) card.append(node('small', `执行服务总耗时 ${item.time} ms（含环境启动）`));
            } else card.append(node('p', '隐藏用例', 'panel-note'));
            cases.append(card);
        });
        submission.code.split('\n').forEach((text, index) => {
            const line = node('div', undefined, 'snapshot-line');
            line.dataset.line = String(index + 1);
            line.append(node('span', String(index + 1), 'line-number'), node('code', text || ' '));
            byId('submissionCode').append(line);
        });
        byId('diagnosisStatus').textContent = submission.status === 'Accepted' ? '全部用例通过。'
            : '需要帮助时，选择一个提示层级。';
        restoreHelp();
        markStale();
    }
    async function restoreSubmission() {
        const ticket = ++restoreSequence;
        if (!user || !problem) return;
        try {
            const response = await fetch(`/api/problems/${encodeURIComponent(problem.id)}/latest-submission?language=${encodeURIComponent(activeLanguage)}`);
            const result = await response.json();
            if (ticket !== restoreSequence || !result.success) return;
            showSubmission(result.data);
        } catch (_) { /* Editing remains usable when history cannot load. */ }
    }
    function ready() {
        if (!userReady || !problem) return;
        if (!edited) restoreDraft();
        restoreSubmission();
    }
    window.addEventListener('practice:user', event => { user = event.detail; userReady = true; ready(); });
    window.addEventListener('practice:problem', event => {
        problem = event.detail;
        ready();
    });
    window.addEventListener('practice:submission', event => { restoreSequence += 1; showSubmission(event.detail); });
    window.addEventListener('auth:required', () => {
        try {
            sessionStorage.setItem('codelab:login-draft', JSON.stringify({user_id:user?.id,problem:getCurrentProblemId(),language:activeLanguage,code:editor.value,input:byId('customInput').value}));
        } catch (_) { /* Keep the editor usable if browser storage is unavailable. */ }
    });
    editor.addEventListener('input', () => { edited = true; saveDraft(); markStale(); });
    byId('customInput').addEventListener('input', saveDraft);
    language.addEventListener('change', () => {
        saveDraft(); activeLanguage = language.value;
        cancelInlineCompletion();
        cancelPending(); showSubmission(null);
        editor.value = ''; byId('customInput').value = '';
        restoreDraft(); markStale(); restoreSubmission();
    });
    async function requestHelp(level) {
        if (!submission || !LearningHelpUI.get().ready) return;
        cancelPending();
        clearFocus();
        historySequence += 1;
        const ticket = sequence, id = submission.submission_id;
        const help = LearningHelpUI.get();
        const requestController = new AbortController();
        controller = requestController;
        const timer = setTimeout(() => requestController.abort(), 70000);
        updateButtons();
        byId('cancelDiagnosisBtn').hidden = false;
        byId('diagnosisStatus').textContent = `正在生成${LearningHelpUI.labels[level]}…`;
        try {
            const response = await UserSession.csrfFetch(`/api/submissions/${id}/help`, {
                method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({level}), signal: requestController.signal
            });
            const result = await response.json();
            if (ticket !== sequence || submission?.submission_id !== id || help.epoch !== LearningHelpUI.get().epoch) return;
            if (!response.ok || !result.success) throw new Error(UserSession.apiErrorMessage(result));
            showHelp(result.data, true);
            window.PracticeReview?.refresh();
            byId('diagnosisStatus').textContent = '已保存，可按需查看其他层级。';
        } catch (error) {
            if (ticket !== sequence) return;
            if (UserSession.handleAuthError(error, byId('diagnosisStatus'))) return;
            byId('diagnosisStatus').textContent = error.name === 'AbortError' ? '等待超时，可重试。已有代码和证据已保留。' : error.message;
        } finally {
            clearTimeout(timer);
            if (ticket === sequence && submission?.submission_id === id) {
                controller = null;
                updateButtons();
                byId('cancelDiagnosisBtn').hidden = true;
            }
        }
    }
    helpButtons.forEach(button => button.addEventListener('click', () => requestHelp(Number(button.dataset.helpLevel))));
    window.addEventListener('practice:help-settings', () => {
        clearFocus();
        cancelPending();
        historySequence += 1;
        diagnosisContent.replaceChildren();
        byId('diagnosisStatus').textContent = '';
        restoreHelp();
    });
    byId('cancelDiagnosisBtn').addEventListener('click', () => {
        cancelPending();
        byId('diagnosisStatus').textContent = '已取消等待。后台请求可能仍在完成，稍后可重试读取。';
    });
})();
